import pytest
from unittest.mock import AsyncMock, patch
from app.schemas.upload import ParsedDocument, ParsedDrug
from app.schemas.analysis import AnalyzeResponse
from app.services.rag.pipeline import run_rag_pipeline, _build_query, _format_document_info


MOCK_LLM_RESULT = {
    "is_claimable": True,
    "estimated_payout": 18500,
    "breakdown": {"본인부담금": 28500, "공제액": -10000},
    "coverage_items": [
        {
            "clause_id": "hyundai-silson-3-2",
            "policy_name": "현대해상 실손의료비",
            "article": "제3조 ②항",
            "is_covered": True,
            "reason": "통원 의원급 해당",
            "citation": "통원의료비는 1회당 의원 1만원을 공제한 금액을 보상한다.",
        }
    ],
    "confidence": 0.92,
    "llm_summary": "실손의료비 통원 항목으로 약 ₩18,500 청구 가능합니다.",
}


def test_build_query():
    doc = ParsedDocument(
        icd_code="J06.9",
        diagnosis="급성상기도감염",
        department="내과",
        drugs=[ParsedDrug(name="아목시실린캡슐 500mg")],
    )
    query = _build_query(doc)
    assert "J06.9" in query
    assert "급성상기도감염" in query
    assert "아목시실린캡슐" in query


def test_format_document_info_with_nonbenefit():
    doc = ParsedDocument(
        hospital="강남의원",
        icd_code="L30.9",
        drugs=[
            ParsedDrug(name="레티놀크림", is_nonbenefit=True),
            ParsedDrug(name="항생제연고", is_nonbenefit=False),
        ],
    )
    info = _format_document_info(doc)
    assert "[비급여]" in info
    assert "항생제연고" in info


@pytest.mark.asyncio
async def test_run_rag_pipeline():
    doc = ParsedDocument(
        icd_code="J06.9",
        diagnosis="급성상기도감염",
        total_amount=28500,
    )
    with patch("app.services.rag.pipeline.get_query_embedding", new_callable=AsyncMock) as mock_embed, \
         patch("app.services.rag.pipeline.retrieve_relevant_clauses", new_callable=AsyncMock) as mock_retrieve, \
         patch("app.services.rag.pipeline.run_coverage_chain", new_callable=AsyncMock) as mock_chain:

        mock_embed.return_value = [0.1] * 1536
        mock_retrieve.return_value = []
        mock_chain.return_value = MOCK_LLM_RESULT

        result = await run_rag_pipeline(doc, policy_ids=["hyundai-silson-v4"])

    assert isinstance(result, AnalyzeResponse)
    assert result.is_claimable is True
    assert result.estimated_payout == 18500
    assert result.confidence == 0.92
    assert len(result.coverage_items) == 1
