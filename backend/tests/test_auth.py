"""
회원가입 / 로그인 / 내 정보 엔드포인트 테스트
"""
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_register_success():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        res = await c.post("/api/v1/auth/register", json={
            "name": "홍길동", "email": "hong@test.com", "password": "pass1234"
        })
    assert res.status_code == 201
    data = res.json()
    assert "access_token" in data
    assert data["user"]["email"] == "hong@test.com"
    assert data["user"]["is_admin"] is False


@pytest.mark.asyncio
async def test_register_duplicate_email():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await c.post("/api/v1/auth/register", json={
            "name": "홍길동", "email": "dup@test.com", "password": "pass1234"
        })
        res = await c.post("/api/v1/auth/register", json={
            "name": "홍길동2", "email": "dup@test.com", "password": "pass5678"
        })
    assert res.status_code == 400
    assert "이미 등록된" in res.json()["detail"]


@pytest.mark.asyncio
async def test_login_success():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await c.post("/api/v1/auth/register", json={
            "name": "이순신", "email": "lee@test.com", "password": "mypassword"
        })
        res = await c.post(
            "/api/v1/auth/login",
            data={"username": "lee@test.com", "password": "mypassword"},
        )
    assert res.status_code == 200
    assert "access_token" in res.json()


@pytest.mark.asyncio
async def test_login_wrong_password():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await c.post("/api/v1/auth/register", json={
            "name": "김유신", "email": "kim@test.com", "password": "correct"
        })
        res = await c.post(
            "/api/v1/auth/login",
            data={"username": "kim@test.com", "password": "wrong"},
        )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_me_authenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        reg = await c.post("/api/v1/auth/register", json={
            "name": "강감찬", "email": "kang@test.com", "password": "pass0000"
        })
        token = reg.json()["access_token"]
        res = await c.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["email"] == "kang@test.com"


@pytest.mark.asyncio
async def test_me_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        res = await c.get("/api/v1/auth/me")
    assert res.status_code == 401
