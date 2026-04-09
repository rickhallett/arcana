from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def worker():
    with patch("arcana.workers.analyst.ChatAnthropic"):
        from arcana.workers.analyst import AnalystWorker
        return AnalystWorker(
            nats_url="nats://localhost:4222",
            subject="arcana.analyse",
            anthropic_api_key="test-key",
        )


async def test_handle_returns_draft_and_citations(worker):
    mock_response = MagicMock()
    mock_response.content = "The sky is blue [1]. Water is wet [2]."
    worker.llm.ainvoke = AsyncMock(return_value=mock_response)

    payload = {
        "job_id": "job-analyst-1",
        "question": "What colour is the sky?",
        "chunks": ["The sky is blue.", "Water is wet."],
        "chunk_ids": ["chunk-a", "chunk-b"],
    }
    result = await worker.handle(payload)

    assert result["job_id"] == "job-analyst-1"
    assert result["draft"] == "The sky is blue [1]. Water is wet [2]."
    assert len(result["citations"]) == 2
    assert result["citations"][0] == {"ref": 1, "chunk_id": "chunk-a"}
    assert result["citations"][1] == {"ref": 2, "chunk_id": "chunk-b"}


async def test_handle_citation_out_of_range_ignored(worker):
    mock_response = MagicMock()
    # [3] refers to a chunk index that doesn't exist (only 2 chunks)
    mock_response.content = "Answer based on [1] and [3]."
    worker.llm.ainvoke = AsyncMock(return_value=mock_response)

    payload = {
        "job_id": "job-analyst-2",
        "question": "Some question",
        "chunks": ["Chunk one text.", "Chunk two text."],
        "chunk_ids": ["id-1", "id-2"],
    }
    result = await worker.handle(payload)

    assert result["job_id"] == "job-analyst-2"
    # [3] should be silently dropped; only [1] is valid
    assert len(result["citations"]) == 1
    assert result["citations"][0] == {"ref": 1, "chunk_id": "id-1"}
