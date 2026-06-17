"""마이데이터 보험 계약 연동 엔드포인트."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List

from app.database import get_db
from app.models.user import User
from app.models.mydata_policy import UserMydataPolicy
from app.schemas.mydata import (
    MydataConsentRequest, MydataPolicyResponse, MydataConnectResult,
    TreatmentVerifyRequest, TreatmentRecord, TreatmentVerifyResult,
)
from app.core.security import get_current_user, get_optional_user

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


# ── 진료내역 대조 + 가입보험 자동 연결 ─────────────────────────────────────────

@router.post("/verify-treatment", response_model=TreatmentVerifyResult)
async def verify_treatment(
    body: TreatmentVerifyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_optional_user),
):
    """OCR로 인식한 환자·병원·조제일자로 의료 마이데이터 진료내역을 대조한다.

    1) 의료 마이데이터에서 일치하는 진료/조제 내역 확인
    2) (로그인 + 기존 연결 없음) 확인된 환자 신원으로 금융 마이데이터의
       가입 보험을 자동 연결 → 이후 보상 분석에 자동 반영
    """
    from app.services.mydata.medical_provider import fetch_treatment
    from app.services.mydata.provider import fetch_policies

    found = await fetch_treatment(body.patient_name, body.hospital, body.treatment_date)
    if not found["matched"]:
        return TreatmentVerifyResult(verified=False, message=found["reason"])

    rec = found["record"]
    result = TreatmentVerifyResult(
        verified=True,
        message=f"의료 마이데이터에서 진료내역을 확인했습니다. ({rec['source']})",
        treatment=TreatmentRecord(
            patient_name=rec["patient_name"],
            hospital=rec["hospital"],
            treatment_date=rec.get("treatment_date"),
            source=rec["source"],
        ),
    )

    # 비로그인은 진료내역 확인까지만 (보험 저장 불가)
    if current_user is None:
        result.message += " 로그인하면 가입 보험을 자동 연결해 분석에 반영할 수 있습니다."
        return result

    # 이미 연결된 마이데이터 보험이 있으면 덮어쓰지 않고 그대로 반영
    existing = (await db.execute(
        select(UserMydataPolicy).where(
            UserMydataPolicy.user_id == current_user.id,
            UserMydataPolicy.is_active == True,
        )
    )).scalars().all()
    if existing:
        result.insurance_connected = len(existing)
        result.policies = [_to_response(p) for p in existing]
        result.message += f" 이미 연결된 가입 보험 {len(existing)}건이 분석에 반영됩니다."
        return result

    # 확인된 환자 신원(이름 + 마이데이터 생년월일)으로 금융 마이데이터 보험 조회
    birth = body.birth_date or rec.get("birth_date")
    try:
        raw_policies = await fetch_policies(rec["patient_name"], birth)
    except ValueError:
        raw_policies = []

    saved = []
    for pol in raw_policies:
        row = UserMydataPolicy(
            user_id=current_user.id,
            org_code=pol["org_code"], org_name=pol["org_name"],
            policy_number=pol["policy_number"], insurance_name=pol["insurance_name"],
            product_type=pol["product_type"], premium=pol.get("premium"),
            coverage_start=pol.get("coverage_start"), coverage_end=pol.get("coverage_end"),
            status=pol.get("status", "정상"), vector_policy_id=pol.get("vector_policy_id"),
        )
        db.add(row)
        saved.append(row)
    await db.commit()
    for row in saved:
        await db.refresh(row)

    result.insurance_connected = len(saved)
    result.policies = [_to_response(p) for p in saved]
    if saved:
        result.message += f" 가입 보험 {len(saved)}건을 분석에 자동 연결했습니다."
    return result


# ── 동기화 (재연결) ───────────────────────────────────────────────────────────────

@router.post("/sync", response_model=MydataConnectResult)
async def sync_mydata(
    body: MydataConsentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """연결된 마이데이터 정보를 최신 상태로 동기화합니다."""
    return await connect_mydata(body, db, current_user)
