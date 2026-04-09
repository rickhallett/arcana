from unittest.mock import AsyncMock

import httpx
import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager


@pytest.fixture
def app(tmp_path, monkeypatch):
    """Create a test FastAPI app with a temporary SQLite database.

    NATS dispatcher.connect() is patched to a no-op so tests don't require
    a live NATS server and the lifespan starts quickly.
    """
    db_path = tmp_path / "test_gateway.db"
    monkeypatch.setenv("ARCANA_DB_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.setenv("ARCANA_CHROMA_HOST", "")
    monkeypatch.setenv("ARCANA_UPLOADS_DIR", str(tmp_path / "uploads"))
    # Import inside fixture so env vars are set before Settings() is called
    from arcana.gateway.app import create_app
    application = create_app()
    # Patch connect on the dispatcher instance so lifespan doesn't block on NATS
    application.state.dispatcher.connect = AsyncMock(return_value=None)
    application.state.dispatcher.close = AsyncMock(return_value=None)
    return application


@pytest_asyncio.fixture
async def client(app):
    async with LifespanManager(app), httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_list_jobs_empty(client):
    response = await client.get("/api/jobs")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0


async def test_query_missing_question(client):
    response = await client.post("/api/query", json={})
    assert response.status_code == 400
    assert response.json()["error"] == "question is required"


async def test_query_empty_question(client):
    response = await client.post("/api/query", json={"question": ""})
    assert response.status_code == 400
    assert response.json()["error"] == "question is required"


async def test_get_job_not_found(client):
    response = await client.get("/api/jobs/nonexistent-job-id")
    assert response.status_code == 404
    assert response.json()["error"] == "not found"


async def test_upload_creates_job(client):
    content = b"%PDF-1.4 fake pdf content"
    response = await client.post(
        "/api/upload",
        files={"file": ("test.pdf", content, "application/pdf")},
    )
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "processing"


async def test_upload_job_appears_in_list(client):
    content = b"%PDF-1.4 fake pdf content"
    upload_resp = await client.post(
        "/api/upload",
        files={"file": ("report.pdf", content, "application/pdf")},
    )
    assert upload_resp.status_code == 200
    job_id = upload_resp.json()["job_id"]

    list_resp = await client.get("/api/jobs")
    assert list_resp.status_code == 200
    jobs = list_resp.json()
    ids = [j["id"] for j in jobs]
    assert job_id in ids


async def test_get_job_after_upload(client):
    content = b"%PDF-1.4 fake pdf content"
    upload_resp = await client.post(
        "/api/upload",
        files={"file": ("doc.pdf", content, "application/pdf")},
    )
    job_id = upload_resp.json()["job_id"]

    get_resp = await client.get(f"/api/jobs/{job_id}")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert "job" in data
    assert data["job"]["id"] == job_id
    assert data["job"]["filename"] == "doc.pdf"
    assert data["job"]["doc_type"] == "pdf"


async def test_upload_image_doc_type(client):
    content = b"\x89PNG\r\n\x1a\n fake png"
    response = await client.post(
        "/api/upload",
        files={"file": ("photo.png", content, "image/png")},
    )
    assert response.status_code == 200
    job_id = response.json()["job_id"]

    get_resp = await client.get(f"/api/jobs/{job_id}")
    assert get_resp.json()["job"]["doc_type"] == "image"
