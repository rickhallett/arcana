import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def worker():
    with patch("arcana.workers.checker.ChatOpenAI"):
        from arcana.workers.checker import CheckerWorker
        return CheckerWorker(
            nats_url="nats://localhost:4222",
            subject="arcana.check",
            openai_api_key="test-key",
        )


async def test_handle_returns_claims(worker):
    claims_payload = {
        "claims": [
            {
                "text": "The sky is blue.",
                "verdict": "supported",
                "chunk_id": "chunk-a",
                "explanation": "Directly stated in chunk-a.",
            },
            {
                "text": "Water is purple.",
                "verdict": "unsupported",
                "chunk_id": "",
                "explanation": "No source supports this.",
            },
        ]
    }
    mock_response = MagicMock()
    mock_response.content = json.dumps(claims_payload)
    worker.llm.ainvoke = AsyncMock(return_value=mock_response)

    payload = {
        "job_id": "job-check-1",
        "draft": "The sky is blue. Water is purple.",
        "chunks": ["The sky is blue.", "Water is wet."],
        "chunk_ids": ["chunk-a", "chunk-b"],
    }
    result = await worker.handle(payload)

    assert result["job_id"] == "job-check-1"
    assert len(result["claims"]) == 2
    assert result["claims"][0]["verdict"] == "supported"
    assert result["claims"][1]["verdict"] == "unsupported"


async def test_handle_strips_markdown_fencing(worker):
    claims_payload = {
        "claims": [
            {"text": "Claim.", "verdict": "partial", "chunk_id": "c1", "explanation": "Partial."}
        ]
    }
    raw_json = json.dumps(claims_payload)
    mock_response = MagicMock()
    mock_response.content = f"```json\n{raw_json}\n```"
    worker.llm.ainvoke = AsyncMock(return_value=mock_response)

    payload = {
        "job_id": "job-check-2",
        "draft": "Some draft text.",
        "chunks": ["Source chunk."],
        "chunk_ids": ["c1"],
    }
    result = await worker.handle(payload)

    assert result["job_id"] == "job-check-2"
    assert len(result["claims"]) == 1
    assert result["claims"][0]["verdict"] == "partial"
