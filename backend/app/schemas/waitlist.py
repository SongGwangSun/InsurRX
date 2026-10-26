
from pydantic import BaseModel, EmailStr


class WaitlistCreate(BaseModel):
    email: EmailStr
    source: str = "landing"
    usage_intent: str | None = None
    paid_intent: str | None = None
    price_range: str | None = None
    feedback: str | None = None


class WaitlistResponse(BaseModel):
    message: str
    already_registered: bool = False
