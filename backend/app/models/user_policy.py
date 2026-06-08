from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, func, Enum
import enum
from app.database import Base


class PolicyStatus(str, enum.Enum):
    pending    = "pending"       # 업로드 완료, 임베딩 대기
    processing = "processing"    # 임베딩 진행 중
    ready      = "ready"         # 임베딩 완료, RAG 사용 가능
    failed     = "failed"        # 처리 실패


class UserPolicy(Base):
    """회원이 업로드한 개인 보험증권/약관 문서"""
    __tablename__ = "user_policies"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    user_id          = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id       = Column(Integer, ForeignKey("insurance_products.id", ondelete="SET NULL"), nullable=True)
    file_name        = Column(String(255), nullable=False)
    original_name    = Column(String(255), nullable=False)
    vector_namespace = Column(String(100), nullable=False)   # pinecone namespace
    chunk_count      = Column(Integer, default=0, nullable=False)
    status           = Column(Enum(PolicyStatus), default=PolicyStatus.pending, nullable=False)
    error_message    = Column(String(500), nullable=True)
    uploaded_at      = Column(DateTime(timezone=True), server_default=func.now())
