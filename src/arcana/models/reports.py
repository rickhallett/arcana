from enum import StrEnum

from pydantic import BaseModel


class ClaimVerdict(StrEnum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    PARTIAL = "partial"


class Claim(BaseModel):
    text: str
    verdict: ClaimVerdict
    chunk_id: str
    explanation: str


class Briefing(BaseModel):
    question: str
    answer: str
    claims: list[Claim]
    confidence: float
    cost_usd: float
    duration_s: float
