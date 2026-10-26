from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_optional_user
from app.database import get_db
from app.models.analysis_result import AnalysisResult
from app.schemas.analysis import AnalyzeRequest, AnalyzeResponse
from app.services.rag.pipeline import run_rag_pipeline
from app.services.user_policy_service import collect_policy_sources

router = APIRouter()


@router.post("/", response_model=AnalyzeResponse)
async def analyze_coverage(
    request: AnalyzeRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_optional_user),
):
    """파싱된 의료 문서 + (선택) JWT → 표준약관 RAG 보상 분석.

    표준약관(별표15)은 항상 검색하고, 회원이 업로드해 임베딩된 문서가 있으면 함께 검색합니다.
    """
    user_namespaces: list[str] = []
    if current_user:
        _, user_namespaces = await collect_policy_sources(db, current_user.id)

    result = await run_rag_pipeline(
        parsed_doc=request.parsed,
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
