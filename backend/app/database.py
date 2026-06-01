from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=settings.APP_ENV == "development")

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def run_migrations():
    """기존 테이블에 신규 컬럼을 안전하게 추가 (idempotent)."""
    survey_columns = [
        ("usage_intent", "VARCHAR(64)"),
        ("paid_intent",  "VARCHAR(64)"),
        ("price_range",  "VARCHAR(32)"),
        ("feedback",     "TEXT"),
    ]
    async with engine.begin() as conn:
        from sqlalchemy import text
        dialect = engine.dialect.name  # 'postgresql' or 'sqlite'
        for col, col_type in survey_columns:
            if dialect == "postgresql":
                sql = f"ALTER TABLE waitlist ADD COLUMN IF NOT EXISTS {col} {col_type}"
                await conn.execute(text(sql))
            else:  # sqlite — IF NOT EXISTS 미지원, 오류 무시
                try:
                    await conn.execute(text(f"ALTER TABLE waitlist ADD COLUMN {col} {col_type}"))
                except Exception:
                    pass
