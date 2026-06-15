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


@pytest.mark.asyncio
async def test_forgot_password_no_enumeration():
    """가입되지 않은 이메일이어도 동일한 200을 반환해야 한다(계정 존재 노출 방지)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        res = await c.post("/api/v1/auth/forgot-password", json={"email": "nobody@test.com"})
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_forgot_then_reset_full_flow(caplog, monkeypatch):
    import logging, re
    from app.core.config import settings
    # 메일 키 없이 dev 모드 → 재설정 링크가 로그로 출력됨
    monkeypatch.setattr(settings, "RESEND_API_KEY", "")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await c.post("/api/v1/auth/register", json={
            "name": "재설정", "email": "reset@test.com", "password": "oldpass1"
        })
        with caplog.at_level(logging.INFO):
            fp = await c.post("/api/v1/auth/forgot-password", json={"email": "reset@test.com"})
        assert fp.status_code == 200

        m = re.search(r"reset_token=([\w\-]+)", caplog.text)
        assert m, "dev 로그에서 재설정 토큰을 찾지 못함"
        token = m.group(1)

        res = await c.post("/api/v1/auth/reset-password", json={
            "token": token, "new_password": "newpass1"
        })
        assert res.status_code == 200

        # 새 비밀번호로는 로그인 성공, 기존 비밀번호로는 실패
        ok = await c.post("/api/v1/auth/login",
                          data={"username": "reset@test.com", "password": "newpass1"})
        old = await c.post("/api/v1/auth/login",
                           data={"username": "reset@test.com", "password": "oldpass1"})
        # 이미 사용한 토큰 재사용은 거부
        reuse = await c.post("/api/v1/auth/reset-password", json={
            "token": token, "new_password": "another1"
        })
    assert ok.status_code == 200
    assert old.status_code == 401
    assert reuse.status_code == 400


@pytest.mark.asyncio
async def test_reset_password_invalid_token():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        res = await c.post("/api/v1/auth/reset-password", json={
            "token": "completely-invalid-token", "new_password": "newpass1"
        })
    assert res.status_code == 400
    assert "유효하지 않" in res.json()["detail"]


@pytest.mark.asyncio
async def test_reset_password_too_short():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        res = await c.post("/api/v1/auth/reset-password", json={
            "token": "any-token", "new_password": "123"
        })
    assert res.status_code == 400
    assert "6자 이상" in res.json()["detail"]
