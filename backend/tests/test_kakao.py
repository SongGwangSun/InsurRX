"""카카오 스킬 서버 엔드포인트 테스트."""
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

BASE = "/api/v1/kakao/skill"

def _req(utterance: str, uid: str = "test_kakao_user", params: dict | None = None) -> dict:
    body: dict = {
        "version": "2.0",
        "userRequest": {
            "utterance": utterance,
            "user": {"id": uid, "type": "accountId"},
        },
        "action": {"name": "test", "params": params or {}, "id": "block_1"},
        "bot":    {"id": "bot_1", "name": "InsurRX"},
    }
    return body


async def _skill(utterance: str, uid: str = "test_user", params: dict | None = None) -> dict:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        res = await c.post(BASE, json=_req(utterance, uid, params))
    assert res.status_code == 200
    return res.json()


@pytest.mark.asyncio
async def test_main_menu():
    data = await _skill("처음으로")
    outputs = data["template"]["outputs"]
    assert len(outputs) == 1
    assert "basicCard" in outputs[0]
    assert "InsurRX" in outputs[0]["basicCard"]["title"]


@pytest.mark.asyncio
async def test_request_image():
    data = await _skill("보험금 분석", uid="u1")
    output = data["template"]["outputs"][0]
    assert "simpleText" in output
    assert "사진" in output["simpleText"]["text"]


@pytest.mark.asyncio
async def test_fallback():
    data = await _skill("이상한 입력입니다 asdf")
    output = data["template"]["outputs"][0]
    assert "simpleText" in output


@pytest.mark.asyncio
async def test_help():
    data = await _skill("도움말")
    output = data["template"]["outputs"][0]
    assert "basicCard" in output
    assert "도움말" in output["basicCard"]["title"] or "가이드" in output["basicCard"]["title"]


@pytest.mark.asyncio
async def test_cancel():
    # 분석 시작 → 취소 → 메인 메뉴 복귀
    await _skill("보험금 분석", uid="u_cancel")
    data = await _skill("취소", uid="u_cancel")
    output = data["template"]["outputs"][0]
    assert "basicCard" in output
    assert "InsurRX" in output["basicCard"]["title"]


@pytest.mark.asyncio
async def test_no_result_without_analysis():
    data = await _skill("결과 확인", uid="u_no_result")
    output = data["template"]["outputs"][0]
    assert "simpleText" in output
    assert "없" in output["simpleText"]["text"]


@pytest.mark.asyncio
async def test_policy_selection_without_image():
    # 이미지 없이 약관 선택 시 이미지 요청 응답
    data = await _skill("약관선택:hyundai-silson-v4", uid="u_no_img")
    output = data["template"]["outputs"][0]
    assert "simpleText" in output
    assert "사진" in output["simpleText"]["text"]
