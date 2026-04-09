from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel

if TYPE_CHECKING:
    from arcana.models.reports import Claim


class ExtractRequest(BaseModel):
    job_id: str
    file_path: str
    file_checksum: str
    doc_type: Literal["pdf", "image", "url"]


class ExtractResult(BaseModel):
    job_id: str
    text: str
    title: str
    pages: int
    doc_type: str


class EmbedRequest(BaseModel):
    job_id: str
    text: str
    title: str
    doc_type: str


class EmbedResult(BaseModel):
    job_id: str
    chunk_count: int
    collection: str


class AnalyseRequest(BaseModel):
    job_id: str
    question: str
    chunks: list[str]
    chunk_ids: list[str]


class AnalyseResult(BaseModel):
    job_id: str
    draft: str
    citations: list[dict]


class CheckRequest(BaseModel):
    job_id: str
    draft: str
    chunks: list[str]
    chunk_ids: list[str]


class CheckResult(BaseModel):
    job_id: str
    claims: list[Claim]


from arcana.models.reports import Claim  # noqa: E402

CheckResult.model_rebuild()
