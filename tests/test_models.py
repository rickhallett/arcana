import json

import pytest

from arcana.models.events import (
    AnalyseRequest,
    AnalyseResult,
    CheckRequest,
    CheckResult,
    EmbedRequest,
    EmbedResult,
    ExtractRequest,
    ExtractResult,
)
from arcana.models.reports import Briefing, Claim, ClaimVerdict

# --- ClaimVerdict ---

def test_claim_verdict_values():
    assert ClaimVerdict.SUPPORTED == "supported"
    assert ClaimVerdict.UNSUPPORTED == "unsupported"
    assert ClaimVerdict.PARTIAL == "partial"
    assert set(ClaimVerdict) == {
        ClaimVerdict.SUPPORTED,
        ClaimVerdict.UNSUPPORTED,
        ClaimVerdict.PARTIAL,
    }


# --- Claim ---

def test_claim_round_trip():
    claim = Claim(
        text="The sky is blue.",
        verdict=ClaimVerdict.SUPPORTED,
        chunk_id="chunk-001",
        explanation="Matched by chunk-001.",
    )
    serialised = claim.model_dump_json()
    restored = Claim.model_validate_json(serialised)
    assert restored == claim
    assert restored.verdict == ClaimVerdict.SUPPORTED


# --- Briefing ---

def test_briefing_round_trip():
    briefing = Briefing(
        question="What is the capital of France?",
        answer="Paris.",
        claims=[
            Claim(
                text="Paris is the capital.",
                verdict=ClaimVerdict.SUPPORTED,
                chunk_id="chunk-002",
                explanation="Directly stated in source.",
            )
        ],
        confidence=0.97,
        cost_usd=0.002,
        duration_s=1.4,
    )
    data = json.loads(briefing.model_dump_json())
    restored = Briefing.model_validate(data)
    assert restored.question == briefing.question
    assert restored.confidence == pytest.approx(0.97)
    assert restored.claims[0].verdict == ClaimVerdict.SUPPORTED


# --- ExtractRequest / ExtractResult ---

def test_extract_request_round_trip():
    req = ExtractRequest(
        job_id="job-001",
        file_path="/uploads/report.pdf",
        file_checksum="abc123",
        doc_type="pdf",
    )
    restored = ExtractRequest.model_validate_json(req.model_dump_json())
    assert restored == req
    assert restored.doc_type == "pdf"


def test_extract_result_round_trip():
    result = ExtractResult(
        job_id="job-001",
        text="Full extracted text here.",
        title="Annual Report 2025",
        pages=42,
        doc_type="pdf",
    )
    restored = ExtractResult.model_validate_json(result.model_dump_json())
    assert restored == result
    assert restored.pages == 42


# --- EmbedRequest / EmbedResult ---

def test_embed_request_round_trip():
    req = EmbedRequest(
        job_id="job-002",
        text="Some document text.",
        title="My Doc",
        doc_type="pdf",
    )
    restored = EmbedRequest.model_validate_json(req.model_dump_json())
    assert restored == req


def test_embed_result_round_trip():
    result = EmbedResult(job_id="job-002", chunk_count=15, collection="arcana-main")
    restored = EmbedResult.model_validate_json(result.model_dump_json())
    assert restored == result
    assert restored.chunk_count == 15


# --- AnalyseRequest / AnalyseResult ---

def test_analyse_request_round_trip():
    req = AnalyseRequest(
        job_id="job-003",
        question="What are the key risks?",
        chunks=["chunk text one", "chunk text two"],
        chunk_ids=["c-1", "c-2"],
    )
    restored = AnalyseRequest.model_validate_json(req.model_dump_json())
    assert restored == req
    assert len(restored.chunks) == 2


def test_analyse_result_round_trip():
    result = AnalyseResult(
        job_id="job-003",
        draft="The key risks are liquidity and leverage.",
        citations=[{"chunk_id": "c-1", "quote": "liquidity risk"}],
    )
    restored = AnalyseResult.model_validate_json(result.model_dump_json())
    assert restored == result
    assert restored.citations[0]["chunk_id"] == "c-1"


# --- CheckRequest / CheckResult ---

def test_check_request_round_trip():
    req = CheckRequest(
        job_id="job-004",
        draft="Draft answer text.",
        chunks=["supporting chunk"],
        chunk_ids=["c-10"],
    )
    restored = CheckRequest.model_validate_json(req.model_dump_json())
    assert restored == req


def test_check_result_round_trip():
    result = CheckResult(
        job_id="job-004",
        claims=[
            Claim(
                text="Draft answer text.",
                verdict=ClaimVerdict.PARTIAL,
                chunk_id="c-10",
                explanation="Only partially supported.",
            )
        ],
    )
    restored = CheckResult.model_validate_json(result.model_dump_json())
    assert restored == result
    assert restored.claims[0].verdict == ClaimVerdict.PARTIAL


# --- doc_type literal validation ---

def test_extract_request_invalid_doc_type():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ExtractRequest(
            job_id="job-bad",
            file_path="/uploads/x.txt",
            file_checksum="xyz",
            doc_type="word",  # not in Literal["pdf", "image", "url"]
        )
