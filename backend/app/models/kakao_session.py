from sqlalchemy import Column, Integer, String, JSON, DateTime, ForeignKey, func, Enum
import enum
from app.database import Base


class KakaoState(str, enum.Enum):
    idle              = "idle"               # 대기 (메인 메뉴)
    wait_image        = "wait_image"         # 분석용 이미지 대기 중
    wait_policy_image = "wait_policy_image"  # 보험증권 이미지 대기 중
    processing        = "processing"         # OCR/RAG 처리 중
    done              = "done"               # 결과 준비 완료
    error             = "error"              # 오류


class KakaoSession(Base):
    """카카오 챗봇 대화 세션 — kakao_user_id 기준으로 상태 유지."""
    __tablename__ = "kakao_sessions"

    kakao_user_id = Column(String(100), primary_key=True)   # 오픈빌더 userRequest.user.id
    user_id       = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)  # 연결된 회원 (카카오 전용 회원 포함)
    state         = Column(String(20), default=KakaoState.idle, nullable=False)
    image_url     = Column(String(1000), nullable=True)      # 사용자가 전송한 첫 이미지 URL (하위 호환)
    image_urls    = Column(JSON, nullable=True)              # 사용자가 전송한 이미지 URL 목록 (여러 장)
    policy_ids    = Column(JSON, nullable=True)              # 선택한 공개 약관 ID 목록
    result        = Column(JSON, nullable=True)              # 분석 결과 캐시
    error_message = Column(String(500), nullable=True)
    updated_at    = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
