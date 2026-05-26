"""
GET /api/v1/result/{session_id} 테스트

- 분석 후 session_id로 결과 재조회
- 없는 session_id → 404
- 저장된 created_at 포함 확인
"""
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch
from app.main import app
from app.schemas.analysis import AnalyzeResponse, CoverageItem

MOCK_RESPONSE = AnalyzeResponse(
    session_id="result-test-session-001",
    is_claimable=True,
    estimated_payout=18500,
    breakdown={"본인부담금": 28500, "공제액": -10000},
    coverage_items=[
        CoverageItem(
            clause_id="hyundai-silson-3-2",
            policy_name="현대해상 실손의료비",
            article="제3조 ②항",
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
    "policy_ids": ["hyundai-silson-v4"],
}


@pytest.mark.asyncio
async def test_result_after_analyze():
    """analyze → 저장된 session_id로 result 조회 성공."""
    with patch(
        "app.api.v1.endpoints_analyze.run_rag_pipeline",
        new_callable=AsyncMock,
        return_value=MOCK_RESPONSE,
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            # 1. 분석 실행
            analyze_resp = await client.post("/api/v1/analyze/", json=ANALYZE_PAYLOAD)
            assert analyze_resp.status_code == 200
            session_id = analyze_resp.json()["session_id"]

            # 2. 결과 조회
            result_resp = await client.get(f"/api/v1/result/{session_id}")

    assert result_resp.status_code == 200
    data = result_resp.json()
    assert data["session_id"] == session_id
    assert data["is_claimable"] is True
    assert data["estimated_payout"] == 18500
    assert data["confidence"] == 0.92
    assert "created_at" in data
    assert data["created_at"] is not None
    assert len(data["coverage_items"]) == 1


@pytest.mark.asyncio
async def test_result_not_found():
    """존재하지 않는 session_id → 404 반환."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/result/nonexistent-session-xyz")

    assert resp.status_code == 404
    assert "nonexistent-session-xyz" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_result_coverage_items_structure():
    """coverage_items 내 각 항목 필드가 올바른지 확인."""
    with patch(
        "app.api.v1.endpoints_analyze.run_rag_pipeline",
        new_callable=AsyncMock,
        return_value=MOCK_RESPONSE,
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            analyze_resp = await client.post("/api/v1/analyze/", json=ANALYZE_PAYLOAD)
            session_id = analyze_resp.json()["session_id"]
            result_resp = await client.get(f"/api/v1/result/{session_id}")

    item = result_resp.json()["coverage_items"][0]
    assert "clause_id" in item
    assert "policy_name" in item
    assert "is_covered" in item
    assert "reason" in item
    assert "citation" in item
