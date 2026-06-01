from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from app.database import get_db
from app.models.waitlist import Waitlist
from app.schemas.waitlist import WaitlistCreate, WaitlistResponse
from typing import List, Optional
import os

router = APIRouter()


@router.post("/", response_model=WaitlistResponse)
async def register_waitlist(body: WaitlistCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Waitlist).where(Waitlist.email == body.email))
    existing = result.scalar_one_or_none()

    if existing:
        # 설문 데이터가 새로 들어온 경우 업데이트
        survey_fields = ("usage_intent", "paid_intent", "price_range", "feedback")
        has_new_survey = any(getattr(body, f) for f in survey_fields)
        if has_new_survey:
            for f in survey_fields:
                val = getattr(body, f)
                if val is not None:
                    setattr(existing, f, val)
            await db.commit()
        return WaitlistResponse(message="이미 등록된 이메일입니다.", already_registered=True)

    db.add(Waitlist(
        email=body.email,
        source=body.source,
        usage_intent=body.usage_intent,
        paid_intent=body.paid_intent,
        price_range=body.price_range,
        feedback=body.feedback,
    ))
    await db.commit()
    return WaitlistResponse(message="대기열 등록 완료! 출시 알림을 드릴게요.")


@router.get("/responses")
async def get_waitlist_responses(
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
):
    """설문 응답 조회 (최신순)."""
    result = await db.execute(
        select(Waitlist).order_by(Waitlist.created_at.desc()).limit(limit)
    )
    rows = result.scalars().all()
    return [
        {
            "email": r.email,
            "usage_intent": r.usage_intent,
            "paid_intent": r.paid_intent,
            "price_range": r.price_range,
            "feedback": r.feedback,
            "source": r.source,
            "created_at": r.created_at,
        }
        for r in rows
    ]


@router.get("/schema-check")
async def schema_check(db: AsyncSession = Depends(get_db)):
    """waitlist 테이블 컬럼 목록 확인."""
    result = await db.execute(text(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_name = 'waitlist' ORDER BY ordinal_position"
    ))
    return {"columns": [{"name": r[0], "type": r[1]} for r in result.fetchall()]}
