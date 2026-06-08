"""
카카오 i 오픈빌더 스킬 서버 (API v2)

오픈빌더에서 설정할 스킬 URL:
  POST https://<railway-url>/api/v1/kakao/skill

대화 흐름:
  [메인메뉴] → 보험금 분석 → 이미지 수신 → 약관 선택 → 처리 중 → 결과 확인
"""
import logging
import httpx
from fastapi import APIRouter, Depends, BackgroundTasks, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db, AsyncSessionLocal
from app.models.kakao_session import KakaoSession, KakaoState
from app.services.kakao import response_builder as rb

logger = logging.getLogger(__name__)
router = APIRouter()


# ── 헬퍼 ──────────────────────────────────────────────────────────────────────

async def _get_or_create_session(db: AsyncSession, kakao_uid: str) -> KakaoSession:
    result = await db.execute(
        select(KakaoSession).where(KakaoSession.kakao_user_id == kakao_uid)
    )
    session = result.scalar_one_or_none()
    if not session:
        session = KakaoSession(kakao_user_id=kakao_uid, state=KakaoState.idle)
        db.add(session)
        await db.flush()
    return session


def _extract_image_url(body: dict) -> str | None:
    """오픈빌더 요청에서 이미지 URL을 추출합니다."""
    action = body.get("action", {})
    params = action.get("params", {})

    # 오픈빌더 파라미터 타입별 시도
    for key in ("image", "secureImage", "photo", "file"):
        val = params.get(key)
        if isinstance(val, dict):
            return val.get("url") or val.get("imageUrl")
        if isinstance(val, str) and val.startswith("http"):
            return val

    # utterance가 이미지 URL인 경우 (일부 버전)
    utterance = body.get("userRequest", {}).get("utterance", "")
    if utterance.startswith("http") and any(ext in utterance for ext in (".jpg", ".jpeg", ".png", ".webp")):
        return utterance

    return None


# ── 백그라운드: OCR + RAG ──────────────────────────────────────────────────────

async def _run_analysis(kakao_uid: str, image_url: str, policy_ids: list[str]):
    """OCR → RAG 파이프라인을 백그라운드에서 실행하고 세션에 결과를 저장합니다."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(KakaoSession).where(KakaoSession.kakao_user_id == kakao_uid)
        )
        session = result.scalar_one_or_none()
        if not session:
            return

        try:
            session.state = KakaoState.processing
            await db.commit()

            # 1) 이미지 다운로드
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(image_url)
                resp.raise_for_status()
                image_bytes  = resp.content
                content_type = resp.headers.get("content-type", "image/jpeg").split(";")[0]

            # 2) OCR
            from app.services.ocr.clova_ocr import run_ocr
            raw_text = await run_ocr(image_bytes, content_type)

            # 3) 파싱
            from app.services.ocr.parser import parse_medical_document_async
            parsed = await parse_medical_document_async(raw_text)

            # 4) RAG 분석
            from app.services.rag.pipeline import run_rag_pipeline
            analysis = await run_rag_pipeline(
                parsed_doc=parsed,
                policy_ids=policy_ids,
            )

            # 5) 결과 저장
            session.result = {
                "is_claimable":     analysis.is_claimable,
                "estimated_payout": analysis.estimated_payout,
                "llm_summary":      analysis.llm_summary,
                "confidence":       analysis.confidence,
                "coverage_items":   [c.model_dump() for c in analysis.coverage_items],
                "breakdown":        analysis.breakdown,
            }
            session.state = KakaoState.done

        except Exception as e:
            logger.error("Kakao analysis failed for %s: %s", kakao_uid, e)
            session.state         = KakaoState.error
            session.error_message = str(e)[:400]

        await db.commit()


# ── 메인 스킬 엔드포인트 ───────────────────────────────────────────────────────

@router.post("/skill")
async def kakao_skill(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    body       = await request.json()
    user_req   = body.get("userRequest", {})
    utterance  = user_req.get("utterance", "").strip()
    kakao_uid  = user_req.get("user", {}).get("id", "unknown")

    logger.info("Kakao skill: uid=%s utterance=%r", kakao_uid, utterance[:80])

    session = await _get_or_create_session(db, kakao_uid)

    # ── 1) 메인 메뉴 트리거 ─────────────────────────────────────────────────
    if utterance in ("처음으로", "시작", "시작하기", "메인 메뉴", "홈", "/start"):
        session.state = KakaoState.idle
        session.image_url = None
        session.result = None
        await db.commit()
        return rb.main_menu()

    # ── 2) 보험금 분석 시작 ─────────────────────────────────────────────────
    if utterance in ("보험금 분석", "분석 시작", "보험 확인"):
        session.state     = KakaoState.wait_image
        session.image_url = None
        session.result    = None
        await db.commit()
        return rb.request_image()

    # ── 3) 취소 ─────────────────────────────────────────────────────────────
    if utterance == "취소":
        session.state = KakaoState.idle
        await db.commit()
        return rb.main_menu()

    # ── 4) 이미지 수신 (상태 무관, 이미지가 오면 처리) ──────────────────────
    image_url = _extract_image_url(body)
    if image_url:
        session.image_url = image_url
        session.state     = KakaoState.idle   # 약관 선택 대기
        session.result    = None
        await db.commit()
        return rb.select_policy()

    # ── 5) 약관 선택 ────────────────────────────────────────────────────────
    if utterance.startswith("약관선택:"):
        policy_code = utterance.split(":", 1)[1]
        if not session.image_url:
            return rb.request_image()

        if policy_code == "all":
            policy_ids = [pid for _, pid in rb.POLICY_OPTIONS]
        else:
            policy_ids = [policy_code]

        session.policy_ids = policy_ids
        session.state      = KakaoState.processing
        session.result     = None
        await db.commit()

        # 백그라운드 처리 시작
        background_tasks.add_task(
            _run_analysis, kakao_uid, session.image_url, policy_ids
        )
        return rb.processing_notice()

    # ── 6) 결과 확인 ─────────────────────────────────────────────────────────
    if utterance in ("결과 확인", "결과확인", "결과 보기"):
        if session.state == KakaoState.processing:
            return rb.text(
                "⏳ 아직 분석 중입니다.\n잠시 후 다시 확인해 주세요.",
                quick_replies=[rb.qr("🔎 결과 확인", "결과 확인"), *rb.BACK_QR],
            )
        if session.state == KakaoState.done and session.result:
            return rb.result_card(session.result)
        if session.state == KakaoState.error:
            msg = session.error_message or "분석 중 오류가 발생했습니다."
            return rb.error_msg(msg)
        # 분석 안 한 상태
        return rb.text(
            "분석 결과가 없습니다. 먼저 이미지를 전송해 주세요.",
            quick_replies=[rb.qr("📊 보험금 분석", "보험금 분석"), *rb.BACK_QR],
        )

    # ── 7) 최근 결과 ──────────────────────────────────────────────────────────
    if utterance in ("최근 결과", "이전 결과", "지난 결과"):
        if session.state == KakaoState.done and session.result:
            return rb.result_card(session.result)
        return rb.text(
            "최근 분석 결과가 없습니다.",
            quick_replies=[rb.qr("📊 보험금 분석", "보험금 분석"), *rb.BACK_QR],
        )

    # ── 8) 도움말 ─────────────────────────────────────────────────────────────
    if utterance in ("도움말", "help", "?", "사용법", "사용방법"):
        return rb.help_card()

    # ── 9) 이미지 대기 상태에서 텍스트 수신 ──────────────────────────────────
    if session.state == KakaoState.wait_image:
        return rb.text(
            "📷 이미지를 전송해 주세요.\n텍스트가 아닌 사진 파일을 보내주셔야 합니다.",
            quick_replies=rb.CANCEL_QR,
        )

    # ── 10) 기본 (폴백) ───────────────────────────────────────────────────────
    return rb.fallback()
