import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch
from app.main import app
from app.schemas.analysis import AnalyzeResponse, CoverageItem

MOCK_ANALYZE_RESPONSE = AnalyzeResponse(
    session_id="test-session-123",
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


@pytest.mark.asyncio
async def test_health_check():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_analyze_endpoint():
    payload = {
        "parsed": {
            "icd_code": "J06.9",
            "diagnosis": "급성상기도감염",
            "total_amount": 28500,
            "drugs": [],
        },
        "policy_ids": ["hyundai-silson-v4"],
    }
    with patch("app.api.v1.endpoints_analyze.run_rag_pipeline", new_callable=AsyncMock) as mock_pipeline:
        mock_pipeline.return_value = MOCK_ANALYZE_RESPONSE
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/analyze/", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["is_claimable"] is True
    assert data["estimated_payout"] == 18500


@pytest.mark.asyncio
async def test_upload_invalid_file_type():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/upload/",
            files={"file": ("test.txt", b"hello", "text/plain")},
        )
    assert response.status_code == 400
