from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.api.v1.router import api_router
from app.core.config import settings
from app.database import create_tables, run_migrations
import app.models.waitlist          # noqa: F401 — register model for table creation
import app.models.analysis_result   # noqa: F401 — register model for table creation


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await create_tables()
        await run_migrations()
    except Exception as e:
        # DB 연결 실패 시 앱을 종료하지 않고 경고만 출력
        import logging
        logging.getLogger(__name__).warning(f"DB 테이블 생성/마이그레이션 실패 (나중에 재시도): {e}")
    yield


app = FastAPI(
    title="InsurRX API",
    description="처방전/영수증 기반 AI 보험 보상 확인 서비스",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "InsurRX"}
