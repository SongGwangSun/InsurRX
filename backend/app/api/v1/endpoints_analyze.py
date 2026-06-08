from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.schemas.analysis import AnalyzeRequest, AnalyzeResponse
from app.services.rag.pipeline import run_rag_pipeline
from app.models.analysis_result import AnalysisResult
from app.models.user_policy import UserPolicy, PolicyStatus
from app.models.mydata_policy import UserMydataPolicy
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
    2. 마이데이터 연결 보험      — vector_policy_id 있는 보험 자동 포함
    3. 업로드 보험증권           — 임베딩 완료된 개인 문서 자동 포함
    """
    policy_ids    : list[str] = list(request.policy_ids)
    user_namespaces: list[str] = []

    if current_user:
        # ── 마이데이터 연결 보험 policy_ids 추가 ────────────────────────────
        mydata_rows = await db.execute(
            select(UserMydataPolicy).where(
                UserMydataPolicy.user_id == current_user.id,
                UserMydataPolicy.is_active == True,
                UserMydataPolicy.status == "정상",
                UserMydataPolicy.vector_policy_id.isnot(None),
            )
        )
        for mp in mydata_rows.scalars().all():
            if mp.vector_policy_id and mp.vector_policy_id not in policy_ids:
                policy_ids.append(mp.vector_policy_id)

        # ── 업로드 보험증권 네임스페이스 수집 ───────────────────────────────
        upload_rows = await db.execute(
            select(UserPolicy).where(
                UserPolicy.user_id == current_user.id,
                UserPolicy.status == PolicyStatus.ready,
            )
        )
        user_namespaces = [p.vector_namespace for p in upload_rows.scalars().all()]

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
    )
    db.add(row)
    await db.commit()

    return result
