import pytest
from unittest.mock import AsyncMock, MagicMock

from arcana.orchestrator.ingest import build_ingest_graph
from arcana.orchestrator.nats_dispatch import DispatchError, NATSDispatcher


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_mock_dispatcher(subject_results: dict) -> NATSDispatcher:
    """Build a NATSDispatcher whose dispatch() is mocked per subject."""
    dispatcher = MagicMock(spec=NATSDispatcher)

    async def _dispatch(subject, payload, job_id, step, correlation_id):
        if subject in subject_results:
            result = subject_results[subject]
            if isinstance(result, Exception):
                raise result
            return result
        raise DispatchError(subject, job_id, 3, "no mock for subject")

    dispatcher.dispatch = AsyncMock(side_effect=_dispatch)
    return dispatcher


# ---------------------------------------------------------------------------
# Task 16: Ingestion Graph
# ---------------------------------------------------------------------------

class TestIngestGraph:
    async def test_full_pipeline_completes(self):
        dispatcher = make_mock_dispatcher({
            "arcana.extract": {"text": "doc text", "title": "My Doc", "pages": 10},
            "arcana.embed": {"chunk_count": 5, "collection": "arcana_docs"},
        })

        graph = build_ingest_graph(dispatcher)
        initial: dict = {
            "job_id": "job-001",
            "file_path": "/tmp/doc.pdf",
            "file_checksum": "abc123",
            "doc_type": "pdf",
        }
        result = await graph.ainvoke(initial)

        assert result["status"] == "completed"
        assert result["text"] == "doc text"
        assert result["title"] == "My Doc"
        assert result["pages"] == 10
        assert result["chunk_count"] == 5
        assert result["collection"] == "arcana_docs"

    async def test_extract_failure_short_circuits(self):
        dispatcher = make_mock_dispatcher({
            "arcana.extract": DispatchError("arcana.extract", "job-002", 3, "timeout"),
        })

        graph = build_ingest_graph(dispatcher)
        initial: dict = {
            "job_id": "job-002",
            "file_path": "/tmp/bad.pdf",
            "file_checksum": "bad",
            "doc_type": "pdf",
        }
        result = await graph.ainvoke(initial)

        assert result["status"] == "failed"
        assert "arcana.extract" in result["error"]
        # embed should never have been called
        subjects_called = [
            call.kwargs.get("subject") or call.args[0]
            for call in dispatcher.dispatch.call_args_list
        ]
        assert "arcana.embed" not in subjects_called
