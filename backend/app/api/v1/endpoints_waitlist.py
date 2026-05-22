from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.waitlist import Waitlist
from app.schemas.waitlist import WaitlistCreate, WaitlistResponse

router = APIRouter()


@router.post("/", response_model=WaitlistResponse)
async def register_waitlist(body: WaitlistCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Waitlist).where(Waitlist.email == body.email))
    existing = result.scalar_one_or_none()
    if existing:
        return WaitlistResponse(message="이미 등록된 이메일입니다.", already_registered=True)

    db.add(Waitlist(email=body.email, source=body.source))
    await db.commit()
    return WaitlistResponse(message="대기열 등록 완료! 출시 알림을 드릴게요.")
