from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, func
from app.database import Base


class PasswordResetToken(Base):
    """비밀번호 재설정 1회용 토큰. 원문은 메일 링크로만 전달하고 DB엔 SHA-256 해시만 저장."""
    __tablename__ = "password_reset_tokens"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    user_id     = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash  = Column(String(64), nullable=False, unique=True, index=True)  # SHA-256 hex
    expires_at  = Column(DateTime(timezone=True), nullable=False)
    is_used     = Column(Boolean, default=False, nullable=False)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
