"""관리자 전용 — 회원·시스템 관리 엔드포인트."""
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List
from app.database import get_db
from app.models.user import User
from app.models.user_policy import UserPolicy
from app.models.analysis_result import AnalysisResult
from app.models.login_history import LoginHistory
from app.schemas.user import AdminUserResponse
from app.core.security import get_current_admin

router = APIRouter()

KST = timezone(timedelta(hours=9))


def _today_start() -> datetime:
    """KST 기준 오늘 0시를, DB 비교용 naive-UTC datetime으로 반환.

    created_at은 UTC로 저장되므로(Postgres timestamptz / SQLite UTC 문자열),
    KST 자정을 UTC로 변환한 뒤 tzinfo를 떼어 양쪽 DB에서 동일하게 비교한다.
    """
    now_kst = datetime.now(KST)
    start_kst = now_kst.replace(hour=0, minute=0, second=0, microsecond=0)
    return start_kst.astimezone(timezone.utc).replace(tzinfo=None)


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


# ── 오늘의 대시보드 (요약 + 항목별 목록) ──────────────────────────────────────

@router.get("/dashboard")
async def dashboard_summary(
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_admin),
):
    """오늘(KST) 핵심 지표 요약 — 카드 클릭 시 /dashboard/{metric}으로 목록 조회."""
    since = _today_start()

    new_signups = (await db.execute(
        select(func.count(User.id)).where(User.created_at >= since)
    )).scalar() or 0

    today_users = (await db.execute(
        select(func.count(func.distinct(LoginHistory.user_id)))
        .where(
            LoginHistory.created_at >= since,
            LoginHistory.status == "success",
            LoginHistory.user_id.isnot(None),
        )
    )).scalar() or 0

    login_success = (await db.execute(
        select(func.count(LoginHistory.id))
        .where(LoginHistory.created_at >= since, LoginHistory.status == "success")
    )).scalar() or 0

    login_failed = (await db.execute(
        select(func.count(LoginHistory.id))
        .where(LoginHistory.created_at >= since, LoginHistory.status == "failed")
    )).scalar() or 0

    return {
        "new_signups":   new_signups,
        "today_users":   today_users,
        "login_success": login_success,
        "login_failed":  login_failed,
    }


@router.get("/dashboard/{metric}")
async def dashboard_list(
    metric: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_admin),
):
    """대시보드 카드 항목별 상세 목록 (오늘, KST)."""
    since = _today_start()

    if metric == "new-signups":
        rows = (await db.execute(
            select(User).where(User.created_at >= since).order_by(User.created_at.desc())
        )).scalars().all()
        return [
            {
                "id": u.id, "name": u.name, "email": u.email,
                "is_admin": u.is_admin, "is_active": u.is_active,
                "created_at": u.created_at,
            }
            for u in rows
        ]

    if metric == "today-users":
        rows = (await db.execute(
            select(
                LoginHistory.user_id,
                func.count(LoginHistory.id),
                func.max(LoginHistory.created_at),
            )
            .where(
                LoginHistory.created_at >= since,
                LoginHistory.status == "success",
                LoginHistory.user_id.isnot(None),
            )
            .group_by(LoginHistory.user_id)
        )).all()
        user_ids = [r[0] for r in rows]
        users = {}
        if user_ids:
            ures = (await db.execute(select(User).where(User.id.in_(user_ids)))).scalars().all()
            users = {u.id: u for u in ures}
        out = []
        for uid, cnt, last in rows:
            u = users.get(uid)
            out.append({
                "id": uid,
                "name": u.name if u else "(삭제된 회원)",
                "email": u.email if u else "-",
                "login_count": cnt,
                "last_login": last,
            })
        out.sort(key=lambda x: x["last_login"], reverse=True)
        return out

    if metric in ("login-success", "login-failed"):
        status = "success" if metric == "login-success" else "failed"
        rows = (await db.execute(
            select(LoginHistory)
            .where(LoginHistory.created_at >= since, LoginHistory.status == status)
            .order_by(LoginHistory.created_at.desc())
            .limit(300)
        )).scalars().all()
        return [
            {
                "id": h.id, "email": h.email,
                "ip_address": h.ip_address, "device_type": h.device_type,
                "created_at": h.created_at,
            }
            for h in rows
        ]

    raise HTTPException(404, detail="알 수 없는 지표입니다.")
