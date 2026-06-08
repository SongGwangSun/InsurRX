"""관리자 전용 — 회원·시스템 관리 엔드포인트."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List
from app.database import get_db
from app.models.user import User
from app.models.user_policy import UserPolicy
from app.models.analysis_result import AnalysisResult
from app.schemas.user import AdminUserResponse
from app.core.security import get_current_admin

router = APIRouter()


@router.get("/users", response_model=List[AdminUserResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_admin),
):
    """전체 회원 목록 (가입일 내림차순)."""
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()

    # 각 유저의 보험증권 수 / 분석 수 집계
    pol_counts = dict(
        (row[0], row[1]) for row in (
            await db.execute(
                select(UserPolicy.user_id, func.count(UserPolicy.id))
                .group_by(UserPolicy.user_id)
            )
        ).all()
    )
    ana_counts = dict(
        (row[0], row[1]) for row in (
            await db.execute(
                select(AnalysisResult.user_id, func.count(AnalysisResult.session_id))
                .where(AnalysisResult.user_id.isnot(None))
                .group_by(AnalysisResult.user_id)
            )
        ).all()
    )

    out = []
    for u in users:
        resp = AdminUserResponse.model_validate(u)
        resp.policy_count   = pol_counts.get(u.id, 0)
        resp.analysis_count = ana_counts.get(u.id, 0)
        out.append(resp)
    return out


@router.patch("/users/{user_id}/toggle-active", response_model=AdminUserResponse)
async def toggle_user_active(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_admin=Depends(get_current_admin),
):
    """회원 활성/비활성 토글."""
    if user_id == current_admin.id:
        raise HTTPException(400, detail="자기 자신의 계정은 비활성화할 수 없습니다.")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, detail="회원을 찾을 수 없습니다.")
    user.is_active = not user.is_active
    await db.commit()
    await db.refresh(user)
    resp = AdminUserResponse.model_validate(user)
    resp.policy_count = 0
    resp.analysis_count = 0
    return resp


@router.patch("/users/{user_id}/toggle-admin", response_model=AdminUserResponse)
async def toggle_user_admin(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_admin=Depends(get_current_admin),
):
    """관리자 권한 부여/회수."""
    if user_id == current_admin.id:
        raise HTTPException(400, detail="자기 자신의 관리자 권한은 변경할 수 없습니다.")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, detail="회원을 찾을 수 없습니다.")
    user.is_admin = not user.is_admin
    await db.commit()
    await db.refresh(user)
    resp = AdminUserResponse.model_validate(user)
    resp.policy_count = 0
    resp.analysis_count = 0
    return resp


@router.get("/stats")
async def system_stats(
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_admin),
):
    """시스템 통계 요약."""
    user_count     = (await db.execute(select(func.count(User.id)))).scalar()
    policy_count   = (await db.execute(select(func.count(UserPolicy.id)))).scalar()
    analysis_count = (await db.execute(select(func.count(AnalysisResult.session_id)))).scalar()
    claimable      = (await db.execute(
        select(func.count(AnalysisResult.session_id))
        .where(AnalysisResult.is_claimable == True)
    )).scalar()

    return {
        "total_users":     user_count,
        "total_policies":  policy_count,
        "total_analyses":  analysis_count,
        "claimable_count": claimable,
        "claimable_rate":  round(claimable / analysis_count * 100, 1) if analysis_count else 0,
    }
