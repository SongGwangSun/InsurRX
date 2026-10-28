"""
개인정보 보관 기한 관리

- 비로그인 분석 결과: GUEST_RESULT_RETENTION_HOURS가 지나면 삭제 (진단명·병원명이 요약에 들어갈 수 있음)
- 로그인 이력(IP·브라우저 정보): LOGIN_HISTORY_RETENTION_DAYS가 지나면 삭제
- 회원 분석 결과는 본인이 삭제하거나 탈퇴할 때까지 보관
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.analysis_result import AnalysisResult
from app.models.login_history import LoginHistory

logger = logging.getLogger(__name__)

PURGE_INTERVAL_SECONDS = 6 * 60 * 60


async def purge_expired(db: AsyncSession, now: datetime | None = None) -> dict[str, int]:
    """보관 기한이 지난 데이터를 지우고 테이블별 삭제 건수를 돌려줍니다."""
    # created_at과 같은 형식(UTC, tz 없음)으로 비교 — endpoints_admin과 동일
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).replace(tzinfo=None)
    guest_cutoff = now - timedelta(hours=settings.GUEST_RESULT_RETENTION_HOURS)
    login_cutoff = now - timedelta(days=settings.LOGIN_HISTORY_RETENTION_DAYS)

    guest = await db.execute(
        delete(AnalysisResult).where(
            AnalysisResult.user_id.is_(None),
            AnalysisResult.created_at < guest_cutoff,
        )
    )
    logins = await db.execute(delete(LoginHistory).where(LoginHistory.created_at < login_cutoff))
    await db.commit()

    counts = {"guest_results": guest.rowcount or 0, "login_history": logins.rowcount or 0}
    if any(counts.values()):
        logger.info("보관 기한 경과 데이터 삭제: %s", counts)
    return counts


async def run_periodic_purge(session_factory) -> None:
    """앱이 떠 있는 동안 PURGE_INTERVAL_SECONDS마다 purge_expired를 실행합니다."""
    while True:
        try:
            async with session_factory() as db:
                await purge_expired(db)
        except Exception as e:  # 한 번 실패해도 다음 주기에 다시 시도
            logger.warning("보관 기한 정리 실패: %s", e)
        await asyncio.sleep(PURGE_INTERVAL_SECONDS)
