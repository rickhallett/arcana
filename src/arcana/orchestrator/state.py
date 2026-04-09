from typing import TypedDict


class IngestState(TypedDict, total=False):
    job_id: str
    file_path: str
    file_checksum: str
    doc_type: str
    text: str
    title: str
    pages: int
    chunk_count: int
    collection: str
    status: str
    error: str


class QueryState(TypedDict, total=False):
    job_id: str
    question: str
    chunks: list[str]
    chunk_ids: list[str]
    distances: list[float]
    draft: str
    citations: list[dict]
    claims: list[dict]
    answer: str
    confidence: float
    cost_usd: float
    duration_s: float
    status: str
    error: str
