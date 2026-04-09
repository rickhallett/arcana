import uuid

import pytest

from arcana.store.vectors import VectorStore


@pytest.fixture
def store():
    """In-memory ephemeral VectorStore with a unique collection per test."""
    return VectorStore(collection_name=f"test_{uuid.uuid4().hex}")


def test_add_and_query(store):
    store.add_chunks(
        documents=["The quarterly revenue was $1 million.", "Costs rose by 15% year-on-year."],
        ids=["chunk-1", "chunk-2"],
        metadatas=[{"job_id": "job-a", "page": 1}, {"job_id": "job-a", "page": 2}],
    )
    results = store.query("What was the revenue?", n_results=1)
    assert len(results["ids"]) == 1
    assert "chunk-1" in results["ids"]
    assert len(results["documents"]) == 1
    assert "revenue" in results["documents"][0].lower()


def test_query_returns_metadata(store):
    store.add_chunks(
        documents=["Somatic breathwork improves vagal tone."],
        ids=["chunk-10"],
        metadatas=[{"job_id": "job-b", "page": 5, "doc_type": "pdf"}],
    )
    results = store.query("breathwork", n_results=1)
    assert len(results["metadatas"]) == 1
    meta = results["metadatas"][0]
    assert meta["job_id"] == "job-b"
    assert meta["page"] == 5
    assert meta["doc_type"] == "pdf"


def test_add_empty_chunks_is_noop(store):
    # Should not raise, should not add anything
    store.add_chunks(documents=[], ids=[], metadatas=[])
    assert store.count() == 0


def test_count_reflects_added_chunks(store):
    assert store.count() == 0
    store.add_chunks(
        documents=["First chunk.", "Second chunk.", "Third chunk."],
        ids=["c1", "c2", "c3"],
        metadatas=[{"job_id": "j1"}, {"job_id": "j1"}, {"job_id": "j1"}],
    )
    assert store.count() == 3


def test_query_with_filter(store):
    store.add_chunks(
        documents=["Alpha document about finance.", "Beta document about health."],
        ids=["alpha-1", "beta-1"],
        metadatas=[{"job_id": "job-alpha"}, {"job_id": "job-beta"}],
    )
    results = store.query(
        "document",
        n_results=10,
        where={"job_id": "job-alpha"},
    )
    assert all(id_.startswith("alpha") for id_ in results["ids"])
    assert "beta-1" not in results["ids"]


def test_query_distances_present(store):
    store.add_chunks(
        documents=["Kubernetes cluster management at scale."],
        ids=["kube-1"],
        metadatas=[{"job_id": "j-kube"}],
    )
    results = store.query("cluster", n_results=1)
    assert len(results["distances"]) == 1
    assert isinstance(results["distances"][0], float)


def test_in_memory_store_isolation():
    """Two independent in-memory stores share no state."""
    store_a = VectorStore(collection_name=f"test_{uuid.uuid4().hex}")
    store_b = VectorStore(collection_name=f"test_{uuid.uuid4().hex}")
    store_a.add_chunks(
        documents=["Only in store A"],
        ids=["a-only"],
        metadatas=[{"src": "a"}],
    )
    assert store_a.count() == 1
    assert store_b.count() == 0
