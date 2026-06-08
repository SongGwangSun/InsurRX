from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.schemas.analysis import AnalyzeRequest, AnalyzeResponse
from app.services.rag.pipeline import run_rag_pipeline
from app.models.analysis_result import AnalysisResult
from app.models.user_policy import UserPolicy, PolicyStatus
from app.core.security import get_optional_user

router = APIRouter()


@router.post("/", response_model=AnalyzeResponse)
async def analyze_coverage(
    request: AnalyzeRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_optional_user),
):
    """파싱된 의료 문서 + (선택) JWT → 공개 약관 + 개인 보험증권 통합 RAG → 보상 분석.

    - 비로그인: request.policy_ids 로 공개 약관만 검색
    - 로그인:   공개 약관 + 사용자 업로드 보험증권(ready 상태) 함께 검색
    """
    # 로그인 사용자의 임베딩 완료 보험증권 네임스페이스 수집
    user_namespaces: list[str] = []
    if current_user:
        rows = await db.execute(
            select(UserPolicy).where(
                UserPolicy.user_id == current_user.id,
                UserPolicy.status == PolicyStatus.ready,
            )
        )
        user_namespaces = [p.vector_namespace for p in rows.scalars().all()]

    result = await run_rag_pipeline(
        parsed_doc=request.parsed,
        policy_ids=request.policy_ids,
        user_namespaces=user_namespaces,
    )

    # 결과 DB 저장
    row = AnalysisResult(
        session_id       = result.session_id,
        is_claimable     = result.is_claimable,
        estimated_payout = result.estimated_payout,
        breakdown        = result.breakdown,
        coverage_items   = [item.model_dump() for item in result.coverage_items],
        confidence       = result.confidence,
        llm_summary      = result.llm_summary,
    )
    db.add(row)
    await db.commit()

    return result
