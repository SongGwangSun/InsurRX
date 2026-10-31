"""
분석 결과 저장 위치 테스트

- POST /analyze 결과는 서버 DB에 저장하지 않는다 (조회 이력은 사용자 기기에 저장)
- GET /result/{session_id}는 서버에 남아 있는 결과(카카오·전환 전 웹)만 조회
- 없는 session_id → 404
"""
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.database import get_db
from app.main import app
from app.models.analysis_result import AnalysisResult
from app.schemas.analysis import AnalyzeResponse, CoverageItem

MOCK_RESPONSE = AnalyzeResponse(
    session_id="result-test-session-001",
    is_claimable=True,
    estimated_payout=18500,
    breakdown={"본인부담금": 28500, "공제액": -10000},
    coverage_items=[
        CoverageItem(
            clause_id="std-silson-basic-3",
            policy_name="실손의료보험 표준약관",
            article="제3조",
            is_covered=True,
            reason="통원 의원급 해당",
            citation="통원의료비는 1회당 의원 1만원을 공제한 금액을 보상한다.",
        )
    ],
    confidence=0.92,
    llm_summary="실손의료비 통원 항목으로 약 ₩18,500 청구 가능합니다.",
)

ANALYZE_PAYLOAD = {
    "parsed": {
        "icd_code": "J06.9",
        "diagnosis": "급성상기도감염",
        "total_amount": 28500,
        "drugs": [],
    },
}


async def _insert(resp: AnalyzeResponse, channel: str = "kakao") -> None:
    gen = app.dependency_overrides[get_db]()
    db = await gen.__anext__()
    db.add(AnalysisResult(
        session_id=resp.session_id,
        is_claimable=resp.is_claimable,
        estimated_payout=resp.estimated_payout,
        breakdown=resp.breakdown,
        coverage_items=[item.model_dump() for item in resp.coverage_items],
        confidence=resp.confidence,
        llm_summary=resp.llm_summary,
        llm_model=resp.llm_model,
        prompt_version=resp.prompt_version,
        latency_ms=resp.latency_ms,
        channel=channel,
    ))
    await db.commit()
    await gen.aclose()


@pytest.mark.asyncio
async def test_analyze_does_not_store_result():
    """웹 분석 결과는 응답으로만 돌려주고 DB에 남기지 않는다."""
    resp = MOCK_RESPONSE.model_copy(update={"session_id": str(uuid.uuid4())})
    with patch(
        "app.api.v1.endpoints_analyze.run_rag_pipeline",
        new_callable=AsyncMock,
        return_value=resp,
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            analyze_resp = await client.post("/api/v1/analyze/", json=ANALYZE_PAYLOAD)
            assert analyze_resp.status_code == 200
            assert analyze_resp.json()["estimated_payout"] == 18500

            result_resp = await client.get(f"/api/v1/result/{resp.session_id}")
            assert result_resp.status_code == 404

    gen = app.dependency_overrides[get_db]()
    db = await gen.__anext__()
    count = (await db.execute(
        select(func.count()).select_from(AnalysisResult).where(AnalysisResult.session_id == resp.session_id)
    )).scalar()
    await gen.aclose()
    assert count == 0


@pytest.mark.asyncio
async def test_result_not_found():
    """존재하지 않는 session_id → 404."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/result/nonexistent-session-xyz")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_result_returns_stored_row():
    """서버에 남아 있는 결과(카카오)는 coverage_items 구조와 추적 정보를 포함해 조회된다."""
    stored = MOCK_RESPONSE.model_copy(update={
        "session_id": str(uuid.uuid4()),
        "llm_model": "gpt-4o",
        "prompt_version": "abc123def456",
        "latency_ms": 2100,
    })
    await _insert(stored)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        result_resp = await client.get(f"/api/v1/result/{stored.session_id}")

    assert result_resp.status_code == 200
    data = result_resp.json()
    assert data["session_id"] == stored.session_id
    assert data["estimated_payout"] == 18500
    assert "created_at" in data
    item = data["coverage_items"][0]
    for key in ("clause_id", "policy_name", "is_covered", "reason", "citation"):
        assert key in item
    assert data["llm_model"] == "gpt-4o"
    assert data["prompt_version"] == "abc123def456"
    assert data["latency_ms"] == 2100
