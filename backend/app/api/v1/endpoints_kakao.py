"""
카카오 i 오픈빌더 스킬 서버 (API v2)

오픈빌더에서 설정할 스킬 URL:
  POST https://<railway-url>/api/v1/kakao/skill

대화 흐름:
  [메인메뉴] → 보험금 분석 → 이미지 수신(처방전·영수증·약봉투, 여러 장) → 약관 선택 → 처리 중 → 결과 확인
  [메인메뉴] → 내 보험 ─┬ 보험증권 등록 → 증권 사진 수신 → 백그라운드 OCR·임베딩
                        ├ 약관 연결 → 보험사 선택 → 상품 선택
                        └ 계정 연결 → '연결 <코드>' 입력 (웹 대시보드에서 코드 발급)
"""
import json
import logging
import re

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.database import AsyncSessionLocal, get_db
from app.models.analysis_result import AnalysisResult
from app.models.insurer import InsuranceProduct, Insurer
from app.models.kakao_session import KakaoSession, KakaoState
from app.models.user import User
from app.models.user_policy import PolicyStatus, UserPolicy
from app.services.kakao import response_builder as rb
from app.services.kakao.account import (
    get_or_create_kakao_user,
    is_kakao_only_user,
    link_kakao_account,
)

logger = logging.getLogger(__name__)


def require_kakao_enabled() -> None:
    """카카오 연동이 꺼져 있으면 엔드포인트를 404로 숨긴다."""
    if not settings.KAKAO_ENABLED:
        raise HTTPException(404, detail="Not Found")


router = APIRouter(dependencies=[Depends(require_kakao_enabled)])

MAX_ANALYSIS_IMAGES = 5
MAX_POLICY_IMAGES   = 10

LINK_PATTERN = re.compile(r'^연결\s*([A-Za-z0-9-]{6,12})$')


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


def _urls_from_value(val) -> list[str]:
    """오픈빌더 파라미터 값 하나에서 이미지 URL 목록을 추출합니다.

    지원 형태:
      - "https://..."                                   (일반 이미지 파라미터)
      - {"url": ...} / {"imageUrl": ...}
      - {"secureUrls": "List(https://a, https://b)"}    (보안 이미지 플러그인)
      - 위 dict가 JSON 문자열로 온 경우
    """
    if isinstance(val, str):
        s = val.strip()
        if s.startswith("{"):
            try:
                return _urls_from_value(json.loads(s))
            except ValueError:
                return []
        if s.startswith("List(") and s.endswith(")"):
            s = s[5:-1]
        return [u.strip() for u in s.split(",") if u.strip().startswith("http")]
    if isinstance(val, dict):
        for key in ("secureUrls", "url", "imageUrl"):
            if val.get(key):
                return _urls_from_value(val[key])
    if isinstance(val, list):
        return [u for v in val for u in _urls_from_value(v)]
    return []


def _extract_image_urls(body: dict) -> list[str]:
    """오픈빌더 요청에서 이미지 URL 목록을 추출합니다 (여러 장 지원)."""
    action = body.get("action", {})

    # 이미지·보안이미지 파라미터 (블록에서 지정한 파라미터명과 무관하게 탐색)
    for container in (action.get("params", {}), action.get("detailParams", {})):
        for val in container.values():
            if isinstance(val, dict) and "origin" in val:   # detailParams 형식
                val = val.get("origin")
            urls = _urls_from_value(val)
            if urls:
                return list(dict.fromkeys(urls))

    # utterance가 이미지 URL인 경우 (일부 버전)
    utterance = body.get("userRequest", {}).get("utterance", "")
    if utterance.startswith("http") and any(ext in utterance for ext in (".jpg", ".jpeg", ".png", ".webp")):
        return [utterance]

    return []


async def _download_images(urls: list[str]) -> list[tuple[bytes, str]]:
    images = []
    async with httpx.AsyncClient(timeout=15) as client:
        for url in urls:
            resp = await client.get(url)
            resp.raise_for_status()
            images.append((resp.content, resp.headers.get("content-type", "image/jpeg").split(";")[0]))
    return images


async def _list_my_policies(db: AsyncSession, user_id: int | None) -> list[UserPolicy]:
    if not user_id:
        return []
    result = await db.execute(
        select(UserPolicy).where(UserPolicy.user_id == user_id).order_by(UserPolicy.uploaded_at.desc())
    )
    return list(result.scalars().all())


async def _has_own_sources(db: AsyncSession, user_id: int | None) -> bool:
    if not user_id:
        return False
    from app.services.user_policy_service import collect_policy_sources
    policy_ids, namespaces = await collect_policy_sources(db, user_id)
    return bool(policy_ids or namespaces)


# ── 백그라운드: OCR + RAG ──────────────────────────────────────────────────────

async def _run_analysis(kakao_uid: str, image_urls: list[str], policy_ids: list[str]):
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
            images = await _download_images(image_urls)

            # 2) OCR + 파싱 (장별) → 3) 병합
            from app.services.ocr.clova_ocr import run_ocr
            from app.services.ocr.parser import (
                merge_parsed_documents,
                parse_medical_document_async,
            )
            docs = []
            for image_bytes, content_type in images:
                raw_text = await run_ocr(image_bytes, content_type)
                docs.append(await parse_medical_document_async(raw_text))
            parsed = merge_parsed_documents(docs)

            # 4) RAG 분석 — 회원이면 내 보험(연결 약관 + 업로드 증권) 포함
            user_namespaces: list[str] = []
            if session.user_id:
                from app.services.user_policy_service import collect_policy_sources
                own_ids, user_namespaces = await collect_policy_sources(db, session.user_id)
                policy_ids = policy_ids + [pid for pid in own_ids if pid not in policy_ids]

            from app.services.rag.pipeline import run_rag_pipeline
            analysis = await run_rag_pipeline(
                parsed_doc=parsed,
                policy_ids=policy_ids,
                user_namespaces=user_namespaces,
            )

            # 5) 결과 저장
            session.result = {
                "is_claimable":     analysis.is_claimable,
                "estimated_payout": analysis.estimated_payout,
                "llm_summary":      analysis.llm_summary,
                "confidence":       analysis.confidence,
                "coverage_items":   [c.model_dump() for c in analysis.coverage_items],
                "breakdown":        analysis.breakdown,
                "doc_types":        parsed.doc_types,
            }
            db.add(AnalysisResult(
                session_id       = analysis.session_id,
                user_id          = session.user_id,
                is_claimable     = analysis.is_claimable,
                estimated_payout = analysis.estimated_payout,
                breakdown        = analysis.breakdown,
                coverage_items   = [c.model_dump() for c in analysis.coverage_items],
                confidence       = analysis.confidence,
                llm_summary      = analysis.llm_summary,
                llm_model        = analysis.llm_model,
                prompt_version   = analysis.prompt_version,
                latency_ms       = analysis.latency_ms,
                channel          = "kakao",
            ))
            session.state = KakaoState.done

        except Exception as e:
            logger.error("Kakao analysis failed for %s: %s", kakao_uid, e)
            session.state         = KakaoState.error
            session.error_message = str(e)[:400]

        await db.commit()


async def _register_policy(policy_id: int, image_urls: list[str]):
    """증권 사진을 즉시 내려받아(카카오 이미지 URL은 임시) OCR → 임베딩합니다."""
    from app.services.user_policy_service import process_user_policy_images
    async with AsyncSessionLocal() as db:
        try:
            images = await _download_images(image_urls)
        except Exception as e:
            logger.error("Kakao policy download failed (policy %d): %s", policy_id, e)
            policy = await db.get(UserPolicy, policy_id)
            if policy:
                policy.status = PolicyStatus.failed
                policy.error_message = f"이미지 다운로드 실패: {e}"[:500]
                await db.commit()
            return
        await process_user_policy_images(db, policy_id, images)


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
        session.image_urls = None
        session.result = None
        await db.commit()
        return rb.main_menu()

    # ── 2) 보험금 분석 시작 ─────────────────────────────────────────────────
    if utterance in ("보험금 분석", "분석 시작", "보험 확인"):
        session.state      = KakaoState.wait_image
        session.image_url  = None
        session.image_urls = None
        session.result     = None
        await db.commit()
        return rb.request_image()

    # ── 3) 취소 ─────────────────────────────────────────────────────────────
    if utterance == "취소":
        session.state = KakaoState.idle
        await db.commit()
        return rb.main_menu()

    # ── 4) 이미지 수신 ──────────────────────────────────────────────────────
    image_urls = _extract_image_urls(body)
    if image_urls:
        # 4-1) 보험증권 등록 대기 중이면 증권으로 등록
        if session.state == KakaoState.wait_policy_image:
            image_urls = image_urls[:MAX_POLICY_IMAGES]
            from app.services.user_policy_service import new_user_namespace
            user = await get_or_create_kakao_user(db, session)
            policy = UserPolicy(
                user_id=user.id,
                file_name="",
                original_name=f"카카오톡 보험증권 ({len(image_urls)}장)",
                vector_namespace=new_user_namespace(user.id),
                status=PolicyStatus.pending,
            )
            db.add(policy)
            session.state = KakaoState.idle
            await db.commit()
            background_tasks.add_task(_register_policy, policy.id, image_urls)
            return rb.policy_registering(len(image_urls))

        # 4-2) 그 외에는 분석용 문서(처방전·영수증·약봉투) → 약관 선택 대기
        image_urls = image_urls[:MAX_ANALYSIS_IMAGES]
        session.image_urls = image_urls
        session.image_url  = image_urls[0]
        session.state      = KakaoState.idle
        session.result     = None
        await db.commit()
        return rb.select_policy(len(image_urls), await _has_own_sources(db, session.user_id))

    # ── 5) 약관 선택 ────────────────────────────────────────────────────────
    if utterance.startswith("약관선택:"):
        policy_code = utterance.split(":", 1)[1]
        urls = session.image_urls or ([session.image_url] if session.image_url else [])
        if not urls:
            return rb.request_image()

        if policy_code == "all":
            policy_ids = [pid for _, pid in rb.POLICY_OPTIONS]
        elif policy_code == "mine":
            policy_ids = []   # 내 보험은 _run_analysis에서 자동 포함
        else:
            policy_ids = [policy_code]

        session.policy_ids = policy_ids
        session.state      = KakaoState.processing
        session.result     = None
        await db.commit()

        # 백그라운드 처리 시작
        background_tasks.add_task(_run_analysis, kakao_uid, urls, policy_ids)
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

    # ── 7-1) 실제 결과와 차이 날 때 안내 ────────────────────────────────────────
    if utterance in ("결과가 다를 때", "이의 신청", "이의신청", "결과가 달라요"):
        return rb.payout_dispute_guide()

    # ── 8) 내 보험 관리 ───────────────────────────────────────────────────────
    if utterance in ("내 보험", "내 보험 관리", "내보험", "보험 목록"):
        if session.state == KakaoState.wait_policy_image:
            session.state = KakaoState.idle
            await db.commit()
        policies = await _list_my_policies(db, session.user_id)
        linked_web = False
        if session.user_id:
            owner = await db.get(User, session.user_id)
            linked_web = bool(owner and not is_kakao_only_user(owner))
        return rb.my_insurance(
            [{"name": p.original_name, "status": getattr(p.status, "value", p.status)} for p in policies],
            linked_web,
        )

    if utterance in ("보험증권 등록", "증권 등록", "증권등록"):
        session.state = KakaoState.wait_policy_image
        await db.commit()
        return rb.request_policy_image()

    if utterance in ("약관 연결", "약관연결"):
        result = await db.execute(
            select(Insurer.id, Insurer.name).where(Insurer.is_active == True).order_by(Insurer.id)
        )
        return rb.select_insurer([tuple(r) for r in result.all()])

    if utterance.startswith("보험사:"):
        insurer = await db.get(Insurer, _int_or_zero(utterance.split(":", 1)[1]))
        if not insurer:
            return rb.fallback()
        result = await db.execute(
            select(InsuranceProduct.id, InsuranceProduct.name).where(
                InsuranceProduct.insurer_id == insurer.id,
                InsuranceProduct.is_active == True,
            ).order_by(InsuranceProduct.id)
        )
        return rb.select_product(insurer.name, [tuple(r) for r in result.all()])

    if utterance.startswith("상품연결:"):
        product = await db.get(InsuranceProduct, _int_or_zero(utterance.split(":", 1)[1]))
        if not product or not product.is_active:
            return rb.fallback()
        insurer = await db.get(Insurer, product.insurer_id)
        name = f"{insurer.name if insurer else ''} {product.name}".strip()
        user = await get_or_create_kakao_user(db, session)

        dup = await db.execute(
            select(UserPolicy.id).where(
                UserPolicy.user_id == user.id,
                UserPolicy.product_id == product.id,
                UserPolicy.vector_namespace == "",
            ).limit(1)
        )
        if dup.first():
            await db.commit()
            return rb.product_linked(name, bool(product.vector_policy_id), already=True)

        # 파일 없이 상품만 연결 — 공개 약관(vector_policy_id)을 RAG에 포함시키는 용도
        db.add(UserPolicy(
            user_id=user.id,
            product_id=product.id,
            file_name="",
            original_name=f"{name} (약관 연결)",
            vector_namespace="",
            status=PolicyStatus.ready,
        ))
        await db.commit()
        return rb.product_linked(name, bool(product.vector_policy_id))

    # ── 9) 계정 연결 ──────────────────────────────────────────────────────────
    if utterance in ("계정 연결", "계정연결", "웹 연결"):
        return rb.link_guide()

    m = LINK_PATTERN.match(utterance)
    if m:
        user = await link_kakao_account(db, session, m.group(1))
        return rb.link_result(user is not None, user.name if user else "")

    # ── 10) 도움말 ────────────────────────────────────────────────────────────
    if utterance in ("도움말", "help", "?", "사용법", "사용방법"):
        return rb.help_card()

    # ── 11) 이미지 대기 상태에서 텍스트 수신 ─────────────────────────────────
    if session.state == KakaoState.wait_image:
        return rb.text(
            "📷 이미지를 전송해 주세요.\n텍스트가 아닌 사진 파일을 보내주셔야 합니다.",
            quick_replies=rb.CANCEL_QR,
        )
    if session.state == KakaoState.wait_policy_image:
        return rb.text(
            "📄 보험증권 사진을 전송해 주세요.",
            quick_replies=rb.CANCEL_QR,
        )

    # ── 12) 기본 (폴백) ───────────────────────────────────────────────────────
    return rb.fallback()


def _int_or_zero(raw: str) -> int:
    return int(raw) if raw.strip().isdigit() else 0
