import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.api.v1.router import api_router
from app.core.config import settings
from app.database import create_tables, run_migrations, AsyncSessionLocal
import app.models.waitlist          # noqa: F401
import app.models.analysis_result   # noqa: F401
import app.models.prompt_template   # noqa: F401
import app.models.user              # noqa: F401
import app.models.insurer           # noqa: F401
import app.models.user_policy       # noqa: F401
import app.models.kakao_session     # noqa: F401
from app.services import prompt_service

_log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await create_tables()
        await run_migrations()
        async with AsyncSessionLocal() as db:
            await prompt_service.seed_and_load(db)
    except Exception as e:
        _log.warning("DB 초기화 실패 (기본값으로 동작): %s", e)
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
