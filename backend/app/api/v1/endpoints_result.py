from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.analysis_result import AnalysisResult
from app.schemas.result import ResultResponse
from app.schemas.analysis import CoverageItem

router = APIRouter()


@router.get("/{session_id}", response_model=ResultResponse)
async def get_result(
    session_id: str = Path(..., description="분석 세션 ID (POST /analyze 응답의 session_id)"),
    db: AsyncSession = Depends(get_db),
):
    """세션 ID로 이전 분석 결과를 조회합니다."""
    stmt = select(AnalysisResult).where(AnalysisResult.session_id == session_id)
    row = (await db.execute(stmt)).scalar_one_or_none()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"session_id '{session_id}'에 해당하는 분석 결과가 없습니다.",
        )

    return ResultResponse(
        session_id       = row.session_id,
        is_claimable     = row.is_claimable,
        estimated_payout = row.estimated_payout,
        breakdown        = row.breakdown,
        coverage_items   = [CoverageItem(**item) for item in row.coverage_items],
        confidence       = row.confidence,
        llm_summary      = row.llm_summary,
        created_at       = row.created_at.isoformat(),
    )
