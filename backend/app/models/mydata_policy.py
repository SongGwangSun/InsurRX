from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, func
from app.database import Base


class UserMydataPolicy(Base):
    """마이데이터로 연결된 사용자 보험 계약 정보.

    실제 마이데이터 표준 API(금융위)의 보험 계약 조회 응답 구조를 따릅니다.
    vector_policy_id: Pinecone에 등록된 약관이 있으면 RAG 분석에 자동 포함됩니다.
    """
    __tablename__ = "user_mydata_policies"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    user_id          = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # 마이데이터 표준 API 필드
    org_code         = Column(String(20),  nullable=False)   # 보험사 기관 코드
    org_name         = Column(String(100), nullable=False)   # 보험사명
    policy_number    = Column(String(50),  nullable=False)   # 증권번호
    insurance_name   = Column(String(200), nullable=False)   # 보험상품명
    product_type     = Column(String(50),  nullable=False)   # 보험 종류 (실손/암/치아 등)
    premium          = Column(Integer,     nullable=True)    # 월 보험료 (원)
    coverage_start   = Column(String(10),  nullable=True)    # 보장 시작일 YYYY-MM-DD
    coverage_end     = Column(String(10),  nullable=True)    # 보장 종료일 YYYY-MM-DD
    status           = Column(String(20),  default="정상",   nullable=False)  # 정상/실효/해지

    # RAG 연동 필드
    vector_policy_id = Column(String(100), nullable=True)    # Pinecone policy_id (있으면 RAG 자동 포함)

    connected_at     = Column(DateTime(timezone=True), server_default=func.now())
    is_active        = Column(Boolean, default=True, nullable=False)
