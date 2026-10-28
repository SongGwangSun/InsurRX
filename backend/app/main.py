import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.models.analysis_result
import app.models.insurer
import app.models.kakao_link_code
import app.models.kakao_session
import app.models.login_history
import app.models.mydata_policy
import app.models.password_reset_token
import app.models.prompt_template
import app.models.refresh_token
import app.models.user
import app.models.user_policy
import app.models.waitlist
from app.api.v1.router import api_router
from app.core.config import settings
from app.database import AsyncSessionLocal, create_tables, run_migrations
from app.services import prompt_service
from app.services.retention import run_periodic_purge

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
    purge_task = asyncio.create_task(run_periodic_purge(AsyncSessionLocal))
    yield
    purge_task.cancel()


app = FastAPI(
    title="InsurRX API",
    description="영수증·처방전 기반 실손보험 예상 환급금 조회 서비스",
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
