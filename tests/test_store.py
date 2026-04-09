import pytest

from arcana.store.database import Database
from arcana.store.documents import DocumentStore


@pytest.fixture
async def store(db):
    ds = DocumentStore(db)
    await ds.init_schema()
    return ds


async def test_create_job(store):
    job = await store.create_job(job_type="ingest", filename="doc.pdf", doc_type="pdf")
    assert job is not None
    assert job["job_type"] == "ingest"
    assert job["status"] == "pending"
    assert job["filename"] == "doc.pdf"
    assert job["doc_type"] == "pdf"
    assert "id" in job
    assert "created_at" in job
    assert "updated_at" in job


async def test_get_job(store):
    job = await store.create_job(job_type="ingest")
    fetched = await store.get_job(job["id"])
    assert fetched is not None
    assert fetched["id"] == job["id"]
    assert fetched["job_type"] == "ingest"


async def test_get_job_missing_returns_none(store):
    result = await store.get_job("nonexistent-id")
    assert result is None


async def test_update_job_status(store):
    job = await store.create_job(job_type="ingest")
    await store.update_job_status(job["id"], "running", step="extracting")
    updated = await store.get_job(job["id"])
    assert updated["status"] == "running"
    assert updated["current_step"] == "extracting"
    assert updated["updated_at"] >= job["updated_at"]


async def test_update_job_status_no_step(store):
    job = await store.create_job(job_type="ingest")
    await store.update_job_status(job["id"], "completed")
    updated = await store.get_job(job["id"])
    assert updated["status"] == "completed"
    assert updated["current_step"] is None


async def test_create_query_job(store):
    job = await store.create_query_job(question="What is the revenue?")
    assert job is not None
    assert job["job_type"] == "query"
    assert job["question"] == "What is the revenue?"
    assert job["status"] == "pending"


async def test_save_and_get_report(store):
    job = await store.create_job(job_type="ingest")
    await store.save_report(
        job_id=job["id"],
        answer="Revenue was $1M",
        claims_json='[{"text": "Revenue was $1M", "page": 1}]',
        confidence=0.92,
        cost_usd=0.003,
        duration_s=4.5,
    )
    report = await store.get_report(job["id"])
    assert report is not None
    assert report["job_id"] == job["id"]
    assert report["answer"] == "Revenue was $1M"
    assert report["confidence"] == pytest.approx(0.92)
    assert report["cost_usd"] == pytest.approx(0.003)
    assert report["duration_s"] == pytest.approx(4.5)


async def test_get_report_missing_returns_none(store):
    result = await store.get_report("nonexistent-job-id")
    assert result is None


async def test_list_jobs(store):
    await store.create_job(job_type="ingest")
    await store.create_job(job_type="query", question="Q1?")
    await store.create_job(job_type="ingest")
    jobs = await store.list_jobs()
    assert len(jobs) == 3
    # Most recent first
    assert jobs[0]["created_at"] >= jobs[1]["created_at"]


async def test_list_jobs_respects_limit(store):
    for i in range(5):
        await store.create_job(job_type="ingest")
    jobs = await store.list_jobs(limit=3)
    assert len(jobs) == 3


async def test_list_incomplete_jobs(store):
    j1 = await store.create_job(job_type="ingest")
    j2 = await store.create_job(job_type="ingest")
    j3 = await store.create_job(job_type="ingest")

    await store.update_job_status(j1["id"], "running", step="extracting")
    await store.update_job_status(j2["id"], "completed")
    # j3 stays pending

    incomplete = await store.list_incomplete_jobs()
    ids = [j["id"] for j in incomplete]
    assert j1["id"] in ids
    assert j2["id"] not in ids
    assert j3["id"] not in ids


async def test_database_conn_raises_before_init(tmp_path):
    db = Database(f"sqlite+aiosqlite:///{tmp_path}/uninit.db")
    with pytest.raises(RuntimeError, match="not initialised"):
        _ = db.conn
