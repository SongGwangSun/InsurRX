"""관리자 오늘 대시보드 — 요약 지표 및 항목별 목록 테스트"""
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.models.user import User
from app.database import get_db


async def _make_admin(db_override) -> str:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await c.post("/api/v1/auth/register", json={
            "name": "관리자", "email": "admin@test.com", "password": "admin1234"
        })
    async for session in db_override():
        from sqlalchemy import update as sa_update
        await session.execute(
            sa_update(User).where(User.email == "admin@test.com").values(is_admin=True)
        )
        await session.commit()
        break
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        res = await c.post("/api/v1/auth/login",
                           data={"username": "admin@test.com", "password": "admin1234"})
        return res.json()["access_token"]


@pytest.fixture
async def admin_token():
    return await _make_admin(app.dependency_overrides.get(get_db))


@pytest.mark.asyncio
async def test_dashboard_requires_admin():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        res = await c.get("/api/v1/admin/dashboard")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_dashboard_summary(admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        res = await c.get("/api/v1/admin/dashboard", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert set(data) == {"new_signups", "today_users", "login_success", "login_failed"}
    # 관리자가 오늘 가입·로그인했으므로 최소 1 이상
    assert data["new_signups"] >= 1
    assert data["today_users"] >= 1
    assert data["login_success"] >= 1


@pytest.mark.asyncio
async def test_dashboard_new_signups_list(admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        res = await c.get("/api/v1/admin/dashboard/new-signups", headers=headers)
    assert res.status_code == 200
    emails = [r["email"] for r in res.json()]
    assert "admin@test.com" in emails


@pytest.mark.asyncio
async def test_dashboard_today_users_list(admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        res = await c.get("/api/v1/admin/dashboard/today-users", headers=headers)
    assert res.status_code == 200
    rows = res.json()
    assert any(r["email"] == "admin@test.com" and r["login_count"] >= 1 for r in rows)


@pytest.mark.asyncio
async def test_dashboard_login_failed_list(admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        # 실패 로그인 1건 발생시키기
        await c.post("/api/v1/auth/login",
                     data={"username": "admin@test.com", "password": "wrongpass"})
        res = await c.get("/api/v1/admin/dashboard/login-failed", headers=headers)
    assert res.status_code == 200
    rows = res.json()
    assert len(rows) >= 1
    assert any(r["email"] == "admin@test.com" for r in rows)


@pytest.mark.asyncio
async def test_dashboard_unknown_metric(admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        res = await c.get("/api/v1/admin/dashboard/nonexistent", headers=headers)
    assert res.status_code == 404
