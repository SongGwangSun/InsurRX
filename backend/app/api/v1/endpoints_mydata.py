"""마이데이터 보험 계약 연동 엔드포인트."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List

from app.database import get_db
from app.models.user import User
from app.models.mydata_policy import UserMydataPolicy
from app.schemas.mydata import MydataConsentRequest, MydataPolicyResponse, MydataConnectResult
from app.core.security import get_current_user

router = APIRouter()


def _to_response(p: UserMydataPolicy) -> MydataPolicyResponse:
    resp = MydataPolicyResponse.model_validate(p)
    resp.has_rag_data = bool(p.vector_policy_id)
    return resp


# ── 마이데이터 동의 및 연결 ─────────────────────────────────────────────────────

@router.post("/connect", response_model=MydataConnectResult)
async def connect_mydata(
    body: MydataConsentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """마이데이터 동의 후 보험 계약 목록을 가져와 저장합니다.

    실제 운영: 마이데이터 표준 OAuth 2.0 동의 완료 콜백에서 호출
    현재: 이름+생년월일 기반 Mock 데이터
    """
    from app.services.mydata.provider import fetch_policies

    try:
        raw_policies = await fetch_policies(body.name, body.birth_date)
    except ValueError as e:
        raise HTTPException(400, detail=str(e))

    # 기존 마이데이터 연결 보험 모두 비활성화 (새로 동기화)
    await db.execute(
        delete(UserMydataPolicy).where(UserMydataPolicy.user_id == current_user.id)
    )
    await db.flush()

    saved = []
    for pol in raw_policies:
        row = UserMydataPolicy(
            user_id        = current_user.id,
            org_code       = pol["org_code"],
            org_name       = pol["org_name"],
            policy_number  = pol["policy_number"],
            insurance_name = pol["insurance_name"],
            product_type   = pol["product_type"],
            premium        = pol.get("premium"),
            coverage_start = pol.get("coverage_start"),
            coverage_end   = pol.get("coverage_end"),
            status         = pol.get("status", "정상"),
            vector_policy_id = pol.get("vector_policy_id"),
        )
        db.add(row)
        saved.append(row)

    await db.commit()
    for row in saved:
        await db.refresh(row)

    policies_resp = [_to_response(p) for p in saved]
    rag_count = sum(1 for p in saved if p.vector_policy_id)

    return MydataConnectResult(
        connected_count=len(saved),
        policies=policies_resp,
        message=(
            f"{len(saved)}개 보험 계약이 연결되었습니다. "
            f"(이 중 {rag_count}개는 AI 분석에 즉시 활용 가능합니다)"
        ),
    )


# ── 연결된 보험 목록 ─────────────────────────────────────────────────────────────

@router.get("/policies", response_model=List[MydataPolicyResponse])
async def list_mydata_policies(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(UserMydataPolicy)
        .where(UserMydataPolicy.user_id == current_user.id,
               UserMydataPolicy.is_active == True)
        .order_by(UserMydataPolicy.connected_at.desc())
    )
    return [_to_response(p) for p in result.scalars().all()]


# ── 개별 보험 연결 해제 ──────────────────────────────────────────────────────────

@router.delete("/policies/{policy_id}", status_code=204)
async def disconnect_policy(
    policy_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(UserMydataPolicy).where(
            UserMydataPolicy.id == policy_id,
            UserMydataPolicy.user_id == current_user.id,
        )
    )
    pol = result.scalar_one_or_none()
    if not pol:
        raise HTTPException(404, detail="보험 계약을 찾을 수 없습니다.")
    await db.delete(pol)
    await db.commit()


# ── 전체 연결 해제 ────────────────────────────────────────────────────────────────

@router.delete("/disconnect", status_code=204)
async def disconnect_all(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await db.execute(
        delete(UserMydataPolicy).where(UserMydataPolicy.user_id == current_user.id)
    )
    await db.commit()


# ── 동기화 (재연결) ───────────────────────────────────────────────────────────────

@router.post("/sync", response_model=MydataConnectResult)
async def sync_mydata(
    body: MydataConsentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """연결된 마이데이터 정보를 최신 상태로 동기화합니다."""
    return await connect_mydata(body, db, current_user)
