"""
pytest 공통 픽스처 — 테스트용 인메모리 SQLite DB 설정
"""
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.database import Base, get_db
from app.main import app as fastapi_app   # 패키지명(app)과 구분하기 위해 별칭 사용

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="function", autouse=True)
async def test_db():
    """각 테스트마다 새 인메모리 DB + 전체 테이블을 생성합니다."""
    engine = create_async_engine(TEST_DB_URL, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    # 모든 모델 임포트 — Base.metadata에 테이블 등록 보장
    import app.models.waitlist          # noqa: F401
    import app.models.analysis_result   # noqa: F401
    import app.models.user              # noqa: F401
    import app.models.insurer           # noqa: F401
    import app.models.user_policy       # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    fastapi_app.dependency_overrides[get_db] = override_get_db

    yield

    fastapi_app.dependency_overrides.pop(get_db, None)
    await engine.dispose()
