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

    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8080"]
    IMAGE_RETENTION_SECONDS: int = 30

    class Config:
        env_file = ".env"


settings = Settings()
