import asyncio
import json
import time

from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse

from arcana.log import log
from arcana.orchestrator.ingest import build_ingest_graph
from arcana.orchestrator.query import build_query_graph

router = APIRouter()

# Module-level set to hold strong references to background tasks (prevents GC before completion)
_background_tasks: set = set()


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/api/jobs")
async def list_jobs(request: Request):
    doc_store = request.app.state.doc_store
    jobs = await doc_store.list_jobs()
    return jobs


@router.post("/api/upload")
async def upload_document(request: Request, file: UploadFile = File(...)):  # noqa: B008
    doc_store = request.app.state.doc_store
    file_store = request.app.state.file_store
    dispatcher = request.app.state.dispatcher
    content = await file.read()
    filename = file.filename or "unknown"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    doc_type_map = {"pdf": "pdf", "png": "image", "jpg": "image", "jpeg": "image"}
    doc_type = doc_type_map.get(ext, "pdf")
    job = await doc_store.create_job(
        job_type="ingest",
        file_path="",
        file_checksum="",
        filename=filename,
        doc_type=doc_type,
    )
    file_path, checksum = file_store.save(job["id"], content, filename)
    await doc_store.update_job_status(job["id"], "processing", step="extract")
    graph = build_ingest_graph(dispatcher)
    initial_state = {
        "job_id": job["id"],
        "file_path": file_path,
        "file_checksum": checksum,
        "doc_type": doc_type,
        "status": "pending",
    }
    task = asyncio.create_task(_run_ingest(graph, initial_state, doc_store))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return {"job_id": job["id"], "status": "processing"}


async def _run_ingest(graph, state, doc_store):
    try:
        result = await graph.ainvoke(state)
        status = result.get("status", "failed")
        log("ingest", "info", "ingest_complete", {
            "job_id": state["job_id"], "status": status,
            "chunk_count": result.get("chunk_count"),
            "error": result.get("error"),
        })
        if status == "completed" and result.get("text"):
            await doc_store.save_extracted_text(
                job_id=state["job_id"],
                title=result.get("title", "Untitled"),
                text=result["text"],
                pages=result.get("pages", 0),
            )
        await doc_store.update_job_status(state["job_id"], status)
    except Exception as e:
        log("ingest", "error", "ingest_exception", {
            "job_id": state["job_id"], "error": str(e),
        })
        await doc_store.update_job_status(state["job_id"], "failed")


@router.post("/api/query")
async def submit_query(request: Request):
    body = await request.json()
    question = body.get("question", "")
    if not question:
        return JSONResponse({"error": "question is required"}, status_code=400)
    doc_store = request.app.state.doc_store
    dispatcher = request.app.state.dispatcher
    vector_store = request.app.state.vector_store
    job = await doc_store.create_query_job(question=question)
    await doc_store.update_job_status(job["id"], "processing", step="retrieve")
    graph = build_query_graph(dispatcher, vector_store)
    start = time.time()
    try:
        result = await graph.ainvoke(
            {"job_id": job["id"], "question": question, "status": "pending"}
        )
    except Exception as e:
        log("query", "error", "query_exception", {
            "job_id": job["id"], "error": str(e),
        })
        await doc_store.update_job_status(job["id"], "failed")
        return JSONResponse(
            {"job_id": job["id"], "status": "failed", "error": str(e), "report": None},
            status_code=200,
        )
    duration = time.time() - start
    status = result.get("status", "failed")

    if status in ("completed", "failed"):
        answer = result.get("answer") or result.get("draft", "")
        if answer:
            await doc_store.save_report(
                job_id=job["id"],
                answer=answer,
                claims_json=json.dumps(result.get("claims", [])),
                confidence=result.get("confidence", 0.0),
                cost_usd=result.get("cost_usd", 0.0),
                duration_s=round(duration, 2),
            )
        await doc_store.update_job_status(job["id"], status)

    report = await doc_store.get_report(job["id"])
    return {
        "job_id": job["id"],
        "status": status,
        "error": result.get("error"),
        "report": report,
    }


@router.get("/api/jobs/{job_id}")
async def get_job(request: Request, job_id: str):
    doc_store = request.app.state.doc_store
    job = await doc_store.get_job(job_id)
    if not job:
        return JSONResponse({"error": "not found"}, status_code=404)
    report = await doc_store.get_report(job_id)
    return {"job": job, "report": report}


@router.get("/api/jobs/{job_id}/text")
async def get_job_text(request: Request, job_id: str):
    doc_store = request.app.state.doc_store
    job = await doc_store.get_job(job_id)
    if not job:
        return JSONResponse({"error": "not found"}, status_code=404)
    extracted = await doc_store.get_extracted_text(job_id)
    if not extracted:
        return JSONResponse({"error": "no extracted text for this job"}, status_code=404)
    return {
        "job_id": job_id,
        "title": extracted["title"],
        "text": extracted["text"],
        "pages": extracted["pages"],
    }


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    templates = request.app.state.templates
    return templates.TemplateResponse(request, "documents.html")


@router.get("/query", response_class=HTMLResponse)
async def query_page(request: Request):
    templates = request.app.state.templates
    return templates.TemplateResponse(request, "query.html")


@router.get("/pipeline", response_class=HTMLResponse)
async def pipeline_page(request: Request):
    templates = request.app.state.templates
    return templates.TemplateResponse(request, "pipeline.html")
