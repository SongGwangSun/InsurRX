"""의료 마이데이터 진료내역 대조 + 가입보험 자동 연결 테스트"""
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.services.ocr.parser import parse_medical_document


SAMPLE_WITH_NAME = """
서울내과의원
성명: 김민수
진료일: 2024-03-15
진료과: 내과
상병코드: J06.9
진단명: 급성상기도감염
본인부담금: 18,500원
"""


def test_parser_extracts_patient_name():
    doc = parse_medical_document(SAMPLE_WITH_NAME)
    assert doc.patient_name == "김민수"


async def _token(email="mduser@test.com"):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        reg = await c.post("/api/v1/auth/register", json={
            "name": "김민수", "email": email, "password": "pass1234"
        })
        return reg.json()["access_token"]


@pytest.mark.asyncio
async def test_verify_treatment_anonymous_verified_only():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        res = await c.post("/api/v1/mydata/verify-treatment", json={
            "patient_name": "김민수", "hospital": "서울내과의원", "treatment_date": "2024-03-15"
        })
    assert res.status_code == 200
    data = res.json()
    assert data["verified"] is True
    assert data["insurance_connected"] == 0   # 비로그인은 보험 연결 안 됨
    assert data["treatment"]["patient_name"] == "김민수"


@pytest.mark.asyncio
async def test_verify_treatment_not_matched_without_name():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        res = await c.post("/api/v1/mydata/verify-treatment", json={
            "patient_name": None, "hospital": "서울내과의원", "treatment_date": "2024-03-15"
        })
    assert res.status_code == 200
    assert res.json()["verified"] is False


@pytest.mark.asyncio
async def test_verify_treatment_logged_in_auto_connects_insurance():
    token = await _token()
    headers = {"Authorization": f"Bearer {token}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        res = await c.post("/api/v1/mydata/verify-treatment", headers=headers, json={
            "patient_name": "김민수", "hospital": "서울내과의원", "treatment_date": "2024-03-15"
        })
        assert res.status_code == 200
        data = res.json()
        assert data["verified"] is True
        assert data["insurance_connected"] >= 1
        assert len(data["policies"]) == data["insurance_connected"]

        # 연결된 보험이 마이데이터 목록 조회에도 나타나야 함
        listed = await c.get("/api/v1/mydata/policies", headers=headers)
        assert listed.status_code == 200
        assert len(listed.json()) >= 1
