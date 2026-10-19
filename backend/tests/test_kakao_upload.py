"""카카오톡 보험증권 등록·약관 연결·계정 연결·약봉투 분석 테스트."""
import json

import pytest
from httpx import AsyncClient, ASGITransport

from app.api.v1 import endpoints_kakao
from app.database import get_db
from app.main import app
from app.schemas.upload import ParsedDocument, ParsedDrug

BASE = "/api/v1/kakao/skill"


def _req(utterance: str, uid: str, params: dict | None = None) -> dict:
    return {
        "version": "2.0",
        "userRequest": {"utterance": utterance, "user": {"id": uid, "type": "accountId"}},
        "action": {"name": "test", "params": params or {}, "id": "block_1"},
        "bot": {"id": "bot_1", "name": "InsurRX"},
    }


async def _skill(c: AsyncClient, utterance: str, uid: str, params: dict | None = None) -> dict:
    res = await c.post(BASE, json=_req(utterance, uid, params))
    assert res.status_code == 200
    return res.json()


def _text(data: dict) -> str:
    out = data["template"]["outputs"][0]
    return out.get("simpleText", {}).get("text") or out["basicCard"]["description"]


async def _db():
    gen = app.dependency_overrides[get_db]()
    return gen, await gen.__anext__()


async def _seed_product(vector_policy_id: str | None = "hyundai-silson-v4") -> tuple[int, int]:
    from app.models.insurer import Insurer, InsuranceProduct
    gen, db = await _db()
    insurer = Insurer(name="현대해상", code="hyundai")
    db.add(insurer)
    await db.flush()
    product = InsuranceProduct(insurer_id=insurer.id, name="실손의료보험", product_code="Hi2204",
                               product_type="실손", vector_policy_id=vector_policy_id)
    db.add(product)
    await db.commit()
    ids = (insurer.id, product.id)
    await gen.aclose()
    return ids


@pytest.fixture
def no_background(monkeypatch):
    """백그라운드 OCR·임베딩·분석이 실제 외부 API를 호출하지 않도록 막는다."""
    calls = []

    async def fake_register(policy_id, urls):
        calls.append(("register", policy_id, urls))

    async def fake_analysis(uid, urls, policy_ids):
        calls.append(("analysis", uid, urls, policy_ids))

    monkeypatch.setattr(endpoints_kakao, "_register_policy", fake_register)
    monkeypatch.setattr(endpoints_kakao, "_run_analysis", fake_analysis)
    return calls


# ── 이미지 URL 추출 ────────────────────────────────────────────────────────────

def test_extract_secure_image_json_string():
    secure = json.dumps({"privacyAgreement": "Y", "imageQuantity": "2",
                         "secureUrls": "List(https://a.kakao.com/1.jpg, https://a.kakao.com/2.jpg)"})
    body = _req("", "u", {"secureimage": secure})
    assert endpoints_kakao._extract_image_urls(body) == [
        "https://a.kakao.com/1.jpg", "https://a.kakao.com/2.jpg"]


def test_extract_image_from_detail_params_and_plain():
    body = _req("", "u")
    body["action"]["detailParams"] = {"photo": {"origin": "https://x.com/p.png", "value": "x"}}
    assert endpoints_kakao._extract_image_urls(body) == ["https://x.com/p.png"]
    assert endpoints_kakao._extract_image_urls(_req("", "u", {"image": {"url": "https://x.com/a.jpg"}})) == [
        "https://x.com/a.jpg"]
    assert endpoints_kakao._extract_image_urls(_req("안녕", "u", {"sys_text": "hello"})) == []


# ── 보험증권 등록 ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_policy_image_registration_creates_kakao_user(no_background):
    uid = "k_policy"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        data = await _skill(c, "보험증권 등록", uid)
        assert "보험증권 사진" in _text(data)

        data = await _skill(c, "", uid, {"image": "List(https://k.com/1.jpg, https://k.com/2.jpg)"})
        assert "2장" in _text(data)

        data = await _skill(c, "내 보험", uid)
        assert "카카오톡 보험증권 (2장)" in _text(data)

    assert no_background[0][0] == "register"
    assert no_background[0][2] == ["https://k.com/1.jpg", "https://k.com/2.jpg"]


@pytest.mark.asyncio
async def test_analysis_image_goes_to_policy_selection(no_background):
    uid = "k_analysis"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await _skill(c, "보험금 분석", uid)
        data = await _skill(c, "", uid, {"image": "List(https://k.com/rx.jpg, https://k.com/env.jpg)"})
        assert "2장" in _text(data)
        data = await _skill(c, "약관선택:all", uid)
        assert "분석" in _text(data)

    kind, _, urls, _ = no_background[0]
    assert kind == "analysis"
    assert urls == ["https://k.com/rx.jpg", "https://k.com/env.jpg"]


# ── 약관 연결 ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_link_product_terms_and_collect_sources():
    insurer_id, product_id = await _seed_product()
    uid = "k_terms"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        data = await _skill(c, "약관 연결", uid)
        assert f"보험사:{insurer_id}" in [q["messageText"] for q in data["template"]["quickReplies"]]

        data = await _skill(c, f"보험사:{insurer_id}", uid)
        assert f"상품연결:{product_id}" in [q["messageText"] for q in data["template"]["quickReplies"]]

        data = await _skill(c, f"상품연결:{product_id}", uid)
        assert "연결되어" in _text(data)
        data = await _skill(c, f"상품연결:{product_id}", uid)
        assert "이미 연결" in _text(data)

    from app.models.kakao_session import KakaoSession
    from app.services.user_policy_service import collect_policy_sources
    gen, db = await _db()
    session = await db.get(KakaoSession, uid)
    policy_ids, namespaces = await collect_policy_sources(db, session.user_id)
    await gen.aclose()
    assert policy_ids == ["hyundai-silson-v4"]
    assert namespaces == []   # 빈 네임스페이스(공개 약관 기본)는 절대 포함하지 않음


# ── 계정 연결 ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_kakao_account_link_moves_policies_to_web_user():
    _, product_id = await _seed_product()
    uid = "k_link"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await _skill(c, f"상품연결:{product_id}", uid)   # 카카오 전용 회원 생성

        reg = await c.post("/api/v1/auth/register", json={
            "name": "김연결", "email": "link@test.com", "password": "pass1234"})
        headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

        assert (await c.get("/api/v1/auth/kakao-link", headers=headers)).json() == {"linked": False}
        code = (await c.post("/api/v1/auth/kakao-link-code", headers=headers)).json()["code"]

        data = await _skill(c, "연결 WRONG123", uid)
        assert "올바르지 않거나" in _text(data)

        data = await _skill(c, f"연결 {code.lower()}", uid)
        assert "김연결" in _text(data)

        # 1회용 코드
        assert "올바르지 않거나" in _text(await _skill(c, f"연결 {code}", uid))

        assert (await c.get("/api/v1/auth/kakao-link", headers=headers)).json() == {"linked": True}
        policies = (await c.get("/api/v1/my/policies/", headers=headers)).json()
        assert [p["original_name"] for p in policies] == ["현대해상 실손의료보험 (약관 연결)"]

        data = await _skill(c, "내 보험", uid)
        assert "웹 계정과 연결" in _text(data)


# ── 약봉투 인식·병합 ───────────────────────────────────────────────────────────

def test_detect_doc_type():
    from app.services.ocr.parser import detect_doc_type
    envelope = "행복약국\n조제일자 2026-10-01\n아목시실린 500mg\n1일 3회 식후 30분 복용\n복약안내"
    assert detect_doc_type(envelope) == "pill_envelope"
    assert detect_doc_type("처 방 전\n교부번호 2026-0001\nJ06.9 급성상기도감염") == "prescription"
    assert detect_doc_type("진료비 영수증\n진찰료 12,000\n수납금액 5,000") == "receipt"
    assert detect_doc_type("아무 내용 없음") is None


def test_merge_prescription_and_envelope():
    from app.services.ocr.parser import merge_parsed_documents
    envelope = ParsedDocument(hospital="행복약국", doc_types=["pill_envelope"], total_amount=3000,
                              drugs=[ParsedDrug(name="아목시실린 500mg"), ParsedDrug(name="타이레놀")])
    rx = ParsedDocument(hospital="서울의원", icd_code="J06.9", diagnosis="급성상기도감염",
                        doc_types=["prescription"], drugs=[ParsedDrug(name="아목시실린500mg")])
    merged = merge_parsed_documents([envelope, rx])
    assert merged.hospital == "서울의원"
    assert merged.icd_code == "J06.9"
    assert merged.total_amount == 3000
    assert [d.name for d in merged.drugs] == ["아목시실린500mg", "타이레놀"]
    assert merged.doc_types == ["pill_envelope", "prescription"]


def test_pill_envelope_only_result_adds_notice():
    from app.services.kakao import response_builder as rb
    data = rb.result_card({"is_claimable": True, "estimated_payout": 3000, "llm_summary": "청구 가능",
                           "confidence": 0.5, "doc_types": ["pill_envelope"]})
    outputs = data["template"]["outputs"]
    assert len(outputs) == 2
    assert "약제비 영수증" in outputs[1]["simpleText"]["text"]

    data = rb.result_card({"is_claimable": True, "estimated_payout": 3000, "llm_summary": "청구 가능",
                           "confidence": 0.5, "doc_types": ["pill_envelope", "prescription"]})
    assert len(data["template"]["outputs"]) == 1


def test_pipeline_document_info_flags_envelope_only():
    from app.services.rag.pipeline import _format_document_info
    info = _format_document_info(ParsedDocument(doc_types=["pill_envelope"], drugs=[ParsedDrug(name="타이레놀")]))
    assert "문서 종류: 약봉투" in info
    assert "진단명·상병코드가 없음" in info


# ── 개인정보 마스킹 ────────────────────────────────────────────────────────────

def test_mask_personal_info():
    from app.services.user_policy_service import mask_personal_info
    masked = mask_personal_info("피보험자 홍길동 900101-1234567 연락처 010-1234-5678")
    assert "1234567" not in masked
    assert "900101-*******" in masked
    assert "010-****-5678" in masked
