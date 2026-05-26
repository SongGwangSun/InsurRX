from sqlalchemy import Column, String, Boolean, Integer, Float, JSON, DateTime, func
from app.database import Base


class AnalysisResult(Base):
    """RAG 파이프라인 분석 결과를 세션 ID 기준으로 저장합니다."""
    __tablename__ = "analysis_results"

    session_id      = Column(String(36), primary_key=True)
    is_claimable    = Column(Boolean,    nullable=False)
    estimated_payout= Column(Integer,    nullable=False)
    breakdown       = Column(JSON,       nullable=False)   # dict
    coverage_items  = Column(JSON,       nullable=False)   # list[CoverageItem]
    confidence      = Column(Float,      nullable=False)
    llm_summary     = Column(String,     nullable=False)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
