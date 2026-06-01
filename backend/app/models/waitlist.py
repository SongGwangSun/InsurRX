from sqlalchemy import Column, String, DateTime, Text, func
import uuid
from app.database import Base


class Waitlist(Base):
    __tablename__ = "waitlist"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(320), unique=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    source = Column(String(64), default="landing")
    usage_intent = Column(String(64), nullable=True)   # definitely / maybe / unsure / no
    paid_intent = Column(String(64), nullable=True)    # yes_paid / depends_price / free_only / not_interested
    price_range = Column(String(32), nullable=True)    # free / low / mid / high
    feedback = Column(Text, nullable=True)
