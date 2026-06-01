from pydantic import BaseModel, EmailStr
from typing import Optional


class WaitlistCreate(BaseModel):
    email: EmailStr
    source: str = "landing"
    usage_intent: Optional[str] = None
    paid_intent: Optional[str] = None
    price_range: Optional[str] = None
    feedback: Optional[str] = None


class WaitlistResponse(BaseModel):
    message: str
    already_registered: bool = False
