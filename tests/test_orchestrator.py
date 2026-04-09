from unittest.mock import AsyncMock, MagicMock

from arcana.orchestrator.ingest import build_ingest_graph
from arcana.orchestrator.nats_dispatch import DispatchError, NATSDispatcher
from arcana.orchestrator.query import build_query_graph

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


# ---------------------------------------------------------------------------
# Task 17: Query Graph
# ---------------------------------------------------------------------------

def make_mock_vector_store(chunks: list[str], ids: list[str], distances: list[float]):
    """Build a synchronous mock VectorStore."""
    vs = MagicMock()
    vs.query = MagicMock(return_value={
        "ids": ids,
        "documents": chunks,
        "metadatas": [{} for _ in chunks],
        "distances": distances,
    })
    return vs


def make_empty_vector_store():
    vs = MagicMock()
    vs.query = MagicMock(return_value={
        "ids": [], "documents": [], "metadatas": [], "distances": [],
    })
    return vs


class TestQueryGraph:
    async def test_full_query_pipeline_completes(self):
        chunks = ["chunk A", "chunk B", "chunk C"]
        ids = ["id-1", "id-2", "id-3"]
        distances = [0.1, 0.2, 0.3]

        dispatcher = make_mock_dispatcher({
            "arcana.analyse": {
                "draft": "The answer is 42.",
                "citations": [{"id": "id-1", "text": "chunk A"}],
            },
            "arcana.check": {
                "claims": [
                    {"claim": "answer is 42", "verdict": "supported"},
                    {"claim": "secondary claim", "verdict": "supported"},
                ],
            },
        })
        vs = make_mock_vector_store(chunks, ids, distances)
        graph = build_query_graph(dispatcher, vs)

        initial: dict = {
            "job_id": "q-001",
            "question": "What is the answer?",
        }
        result = await graph.ainvoke(initial)

        assert result["status"] == "completed"
        assert result["answer"] == "The answer is 42."
        assert len(result["claims"]) == 2
        assert result["confidence"] == 1.0  # 2 supported / 2 total
        assert result["chunks"] == chunks
        assert result["chunk_ids"] == ids

    async def test_no_results_path(self):
        vs = make_empty_vector_store()
        dispatcher = make_mock_dispatcher({})  # should not be called
        graph = build_query_graph(dispatcher, vs)

        initial: dict = {
            "job_id": "q-002",
            "question": "Something with no matching docs?",
        }
        result = await graph.ainvoke(initial)

        assert result["status"] == "completed"
        assert result["answer"] == "No relevant documents found for this question."
        assert result["confidence"] == 0.0
        assert result["claims"] == []
        # dispatcher should never have been called
        dispatcher.dispatch.assert_not_called()

    async def test_analyse_failure_short_circuits(self):
        chunks = ["chunk X"]
        ids = ["id-x"]
        vs = make_mock_vector_store(chunks, ids, [0.1])

        dispatcher = make_mock_dispatcher({
            "arcana.analyse": DispatchError("arcana.analyse", "q-003", 3, "worker down"),
        })
        graph = build_query_graph(dispatcher, vs)

        initial: dict = {
            "job_id": "q-003",
            "question": "Will this fail?",
        }
        result = await graph.ainvoke(initial)

        assert result["status"] == "failed"
        assert "arcana.analyse" in result["error"]
        # check and synthesise should not run
        subjects_called = [
            call.kwargs.get("subject") or call.args[0]
            for call in dispatcher.dispatch.call_args_list
        ]
        assert "arcana.check" not in subjects_called
