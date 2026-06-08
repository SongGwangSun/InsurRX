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
    migrations = [
        # table,                 column,             type
        ("waitlist",             "usage_intent",     "VARCHAR(64)"),
        ("waitlist",             "paid_intent",      "VARCHAR(64)"),
        ("waitlist",             "price_range",      "VARCHAR(32)"),
        ("waitlist",             "feedback",         "TEXT"),
        ("insurance_products",   "vector_policy_id", "VARCHAR(100)"),
        ("analysis_results",     "user_id",          "INTEGER"),
    ]
    async with engine.begin() as conn:
        from sqlalchemy import text
        dialect = engine.dialect.name
        for table, col, col_type in migrations:
            if dialect == "postgresql":
                await conn.execute(text(
                    f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {col_type}"
                ))
            else:
                try:
                    await conn.execute(text(
                        f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"
                    ))
                except Exception:
                    pass
