from unittest.mock import MagicMock, patch

import pytest

from arcana.store.vectors import VectorStore


@pytest.fixture
def worker():
    with patch("arcana.workers.embedder.OpenAIEmbeddings"):
        from arcana.workers.embedder import EmbedderWorker
        w = EmbedderWorker(
            nats_url="nats://localhost:4222",
            subject="arcana.embed",
            openai_api_key="test-key",
        )
        # Use in-memory chroma so no filesystem required
        w.vector_store = VectorStore()
        return w


async def test_handle_text_returns_chunks(worker):
    text = " ".join(["word"] * 200)  # enough text to produce at least one chunk
    payload = {
        "job_id": "job-embed-1",
        "text": text,
        "title": "Test Doc",
        "doc_type": "pdf",
    }
    result = await worker.handle(payload)

    assert result["job_id"] == "job-embed-1"
    assert result["chunk_count"] > 0
    assert result["collection"] == VectorStore.COLLECTION_NAME
    # Verify data actually landed in the vector store
    assert worker.vector_store.count() == result["chunk_count"]


async def test_handle_empty_text_returns_zero_chunks(worker):
    payload = {
        "job_id": "job-embed-2",
        "text": "   ",
        "title": "Empty Doc",
        "doc_type": "pdf",
    }
    result = await worker.handle(payload)

    assert result["job_id"] == "job-embed-2"
    assert result["chunk_count"] == 0
    assert result["collection"] == VectorStore.COLLECTION_NAME


async def test_handle_short_text_produces_single_chunk(worker):
    payload = {
        "job_id": "job-embed-3",
        "text": "A short sentence.",
        "title": "Short Doc",
        "doc_type": "image",
    }
    result = await worker.handle(payload)

    assert result["chunk_count"] == 1
    assert result["collection"] == VectorStore.COLLECTION_NAME
