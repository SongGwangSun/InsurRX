from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.analysis import AnalyzeRequest, AnalyzeResponse
from app.services.rag.pipeline import run_rag_pipeline
from app.models.analysis_result import AnalysisResult

router = APIRouter()


@router.post("/", response_model=AnalyzeResponse)
async def analyze_coverage(
    request: AnalyzeRequest,
    db: AsyncSession = Depends(get_db),
):
    """파싱된 의료 문서 + 사용자 보험 정보 → RAG 파이프라인 → 보상 여부·예상 금액 반환.
    분석 결과는 session_id로 DB에 저장되어 /result/{session_id} 로 재조회 가능합니다.
    """
    result = await run_rag_pipeline(
        parsed_doc=request.parsed,
        policy_ids=request.policy_ids,
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
