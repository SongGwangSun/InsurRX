from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship
from app.database import Base


class Insurer(Base):
    """보험사 (예: 현대해상, 삼성화재)"""
    __tablename__ = "insurers"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    name       = Column(String(100), unique=True, nullable=False)
    code       = Column(String(20),  unique=True, nullable=False)   # 식별 코드 (예: hyundai)
    logo_url   = Column(String(500), nullable=True)
    is_active  = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    products = relationship("InsuranceProduct", back_populates="insurer", cascade="all, delete-orphan")


class InsuranceProduct(Base):
    """보험 상품 (예: 현대해상 실손의료보험 Hi2204)"""
    __tablename__ = "insurance_products"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    insurer_id   = Column(Integer, ForeignKey("insurers.id", ondelete="CASCADE"), nullable=False)
    name         = Column(String(200), nullable=False)
    product_code = Column(String(50),  nullable=False)   # 예: Hi2204
    product_type = Column(String(50),  nullable=False)   # 실손/암/치아/어린이/종신 등
    description  = Column(String(500), nullable=True)
    is_active    = Column(Boolean, default=True, nullable=False)
    created_at   = Column(DateTime(timezone=True), server_default=func.now())

    insurer = relationship("Insurer", back_populates="products")
