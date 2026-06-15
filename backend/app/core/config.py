from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    APP_ENV: str = "development"
    SECRET_KEY: str = "change-me-in-production"

    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:5432/insurrx"

    VECTOR_DB_TYPE: str = "pinecone"
    PINECONE_API_KEY: str = ""
    PINECONE_INDEX: str = "insurrx-policies"
    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: int = 19530

    CLOVA_OCR_API_URL: str = ""
    CLOVA_OCR_SECRET_KEY: str = ""

    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    LLM_PROVIDER: str = "anthropic"
    LLM_MODEL: str = "claude-sonnet-4-6"

    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8080",
        "http://localhost:5500",   # VS Code Live Server
        "http://127.0.0.1:5500",
        "null",                    # file:// 로 열었을 때
        # 프로덕션 도메인
        "https://songgwangsun.github.io",
        "https://song2nes.com",
        "https://www.song2nes.com",
        "https://magnificent-celebration-production-2dd9.up.railway.app",
    ]
    IMAGE_RETENTION_SECONDS: int = 30

    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60              # 1시간 (액세스 토큰)
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30       # 로그인 유지 선택 시
    REFRESH_TOKEN_SHORT_DAYS: int = 1         # 로그인 유지 미선택 시

    # 비밀번호 재설정 메일 (Resend)
    RESEND_API_KEY: str = ""                                  # 비어 있으면 메일 미발송(개발 모드: 링크 로그 출력)
    MAIL_FROM: str = "InsurRX <onboarding@resend.dev>"        # 도메인 인증 후 noreply@song2nes.com 으로 교체
    FRONTEND_URL: str = "https://song2nes.com"               # 재설정 링크 베이스
    RESET_TOKEN_EXPIRE_MINUTES: int = 30

    class Config:
        env_file = ".env"


settings = Settings()
