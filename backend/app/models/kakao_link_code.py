from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, func
from app.database import Base


class KakaoLinkCode(Base):
    """웹 회원 ↔ 카카오톡 계정 연결용 1회용 코드. 웹 대시보드에서 발급 → 카톡에서 '연결 <코드>' 입력."""
    __tablename__ = "kakao_link_codes"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    user_id     = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    code_hash   = Column(String(64), nullable=False, unique=True, index=True)  # SHA-256 hex
    expires_at  = Column(DateTime(timezone=True), nullable=False)
    is_used     = Column(Boolean, default=False, nullable=False)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
