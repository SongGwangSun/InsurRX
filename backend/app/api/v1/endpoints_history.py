from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from app.database import get_db
from app.models.analysis_result import AnalysisResult
from app.schemas.result import AnalysisResultResponse
from app.core.security import get_current_user

router = APIRouter()


@router.get("/", response_model=List[AnalysisResultResponse])
async def list_my_analyses(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """로그인 사용자의 과거 분석 결과 목록 (최신순)."""
    result = await db.execute(
        select(AnalysisResult)
        .where(AnalysisResult.user_id == current_user.id)
        .order_by(AnalysisResult.created_at.desc())
        .limit(limit)
    )
    return result.scalars().all()


@router.delete("/{session_id}", status_code=204)
async def delete_analysis(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await db.execute(
        select(AnalysisResult).where(
            AnalysisResult.session_id == session_id,
            AnalysisResult.user_id == current_user.id,
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(404, detail="분석 결과를 찾을 수 없습니다.")
    await db.delete(row)
    await db.commit()
