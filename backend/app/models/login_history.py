from sqlalchemy import Column, Integer, String, DateTime, func, ForeignKey
from app.database import Base


class LoginHistory(Base):
    __tablename__ = "login_history"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    user_id     = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    email       = Column(String(255), nullable=True)          # 실패 시 어떤 이메일로 시도했는지 기록
    ip_address  = Column(String(45), nullable=True)           # IPv4 / IPv6
    user_agent  = Column(String(512), nullable=True)
    device_type = Column(String(50), nullable=True)           # Mobile / Desktop / Other
    status      = Column(String(20), nullable=False)          # success / failed
    created_at  = Column(DateTime(timezone=True), server_default=func.now(), index=True)
