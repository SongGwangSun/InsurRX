import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_optional_user
from app.database import get_db
from app.schemas.analysis import AnalyzeRequest, AnalyzeResponse
from app.services.rag.pipeline import run_rag_pipeline
from app.services.user_policy_service import collect_policy_sources

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/", response_model=AnalyzeResponse)
async def analyze_coverage(
    request: AnalyzeRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_optional_user),
):
    """파싱된 의료 문서 + (선택) JWT → 표준약관 RAG 보상 분석.

    표준약관(별표15)은 항상 검색하고, 회원이 업로드해 임베딩된 문서가 있으면 함께 검색합니다.
    결과는 DB에 저장하지 않습니다 (조회 이력은 사용자 기기에 저장).
    """
    user_namespaces: list[str] = []
    if current_user:
        _, user_namespaces = await collect_policy_sources(db, current_user.id)

    result = await run_rag_pipeline(
        parsed_doc=request.parsed,
        user_namespaces=user_namespaces,
    )

    # 진료 정보가 담긴 결과는 서버에 저장하지 않고 응답으로만 돌려준다.
    # 조회 이력은 사용자 기기(브라우저)에 저장된다 — 서버에는 개인을 알 수 없는 처리 지표만 로그로 남긴다.
    logger.info(
        "analyze done: claimable=%s model=%s prompt=%s latency_ms=%s",
        result.is_claimable, result.llm_model, result.prompt_version, result.latency_ms,
    )
    return result
