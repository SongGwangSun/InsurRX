from sqlalchemy import Column, String, Boolean, Integer, Float, JSON, DateTime, func, ForeignKey
from app.database import Base


class AnalysisResult(Base):
    """RAG 파이프라인 분석 결과를 세션 ID 기준으로 저장합니다."""
    __tablename__ = "analysis_results"

    session_id      = Column(String(36), primary_key=True)
    user_id         = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    is_claimable    = Column(Boolean,    nullable=False)
    estimated_payout= Column(Integer,    nullable=False)
    breakdown       = Column(JSON,       nullable=False)
    coverage_items  = Column(JSON,       nullable=False)
    confidence      = Column(Float,      nullable=False)
    llm_summary     = Column(String,     nullable=False)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
