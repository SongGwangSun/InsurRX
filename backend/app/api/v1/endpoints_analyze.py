from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.analysis import AnalyzeRequest, AnalyzeResponse
from app.services.rag.pipeline import run_rag_pipeline
from app.models.analysis_result import AnalysisResult
from app.services.user_policy_service import collect_policy_sources
from app.core.security import get_optional_user

router = APIRouter()


@router.post("/", response_model=AnalyzeResponse)
async def analyze_coverage(
    request: AnalyzeRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_optional_user),
):
    """파싱된 의료 문서 + (선택) JWT → 공개 약관 + 개인 보험증권 + 마이데이터 보험 통합 RAG.

    검색 우선순위:
    1. request.policy_ids       — 명시적으로 지정한 공개 약관
    2. 마이데이터 연결 보험·상품 연결 보험증권 — 해당 공개 약관 자동 포함
    3. 업로드 보험증권           — 임베딩 완료된 개인 문서 자동 포함
    """
    policy_ids    : list[str] = list(request.policy_ids)
    user_namespaces: list[str] = []

    if current_user:
        own_ids, user_namespaces = await collect_policy_sources(db, current_user.id)
        policy_ids += [pid for pid in own_ids if pid not in policy_ids]

    result = await run_rag_pipeline(
        parsed_doc=request.parsed,
        policy_ids=policy_ids,
        user_namespaces=user_namespaces,
    )

    row = AnalysisResult(
        session_id       = result.session_id,
        user_id          = current_user.id if current_user else None,
        is_claimable     = result.is_claimable,
        estimated_payout = result.estimated_payout,
        breakdown        = result.breakdown,
        coverage_items   = [item.model_dump() for item in result.coverage_items],
        confidence       = result.confidence,
        llm_summary      = result.llm_summary,
        llm_model        = result.llm_model,
        prompt_version   = result.prompt_version,
        latency_ms       = result.latency_ms,
        channel          = "web",
    )
    db.add(row)
    await db.commit()

    return result
