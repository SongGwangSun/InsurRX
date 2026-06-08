"""
보험사 / 보험 상품 CRUD 엔드포인트 테스트
"""
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from app.main import app
from app.models.user import User
from app.core.security import hash_password
from app.database import get_db


async def _make_admin(db_override) -> str:
    """관리자 계정을 직접 DB에 생성하고 토큰을 반환합니다."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        # 일반 가입 후 DB에서 is_admin 수동 업데이트
        reg = await c.post("/api/v1/auth/register", json={
            "name": "관리자", "email": "admin@test.com", "password": "admin1234"
        })
        token = reg.json()["access_token"]

    # dependency override 내의 세션으로 is_admin 플래그 설정
    async for session in db_override():
        from sqlalchemy import update as sa_update
        await session.execute(
            sa_update(User).where(User.email == "admin@test.com").values(is_admin=True)
        )
        await session.commit()
        break

    # 다시 로그인해서 is_admin=True 가 담긴 토큰 획득
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        res = await c.post("/api/v1/auth/login",
                           data={"username": "admin@test.com", "password": "admin1234"})
        return res.json()["access_token"]


@pytest.fixture
async def admin_token():
    db_override = app.dependency_overrides.get(get_db)
    return await _make_admin(db_override)


@pytest.mark.asyncio
async def test_list_insurers_empty():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        res = await c.get("/api/v1/insurers/")
    assert res.status_code == 200
    assert res.json() == []


@pytest.mark.asyncio
async def test_create_insurer_requires_admin():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        # 비로그인 시도
        res = await c.post("/api/v1/insurers/", json={"name": "현대해상", "code": "hyundai"})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_create_and_list_insurer(admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        # 생성
        res = await c.post("/api/v1/insurers/", json={"name": "현대해상", "code": "hyundai"}, headers=headers)
        assert res.status_code == 201
        ins_id = res.json()["id"]

        # 목록 조회
        res2 = await c.get("/api/v1/insurers/")
        assert len(res2.json()) == 1
        assert res2.json()[0]["name"] == "현대해상"


@pytest.mark.asyncio
async def test_create_product(admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        ins = await c.post("/api/v1/insurers/", json={"name": "삼성화재", "code": "samsung"}, headers=headers)
        ins_id = ins.json()["id"]

        res = await c.post(f"/api/v1/insurers/{ins_id}/products", json={
            "name": "실손의료보험", "product_code": "SM2401", "product_type": "실손"
        }, headers=headers)
        assert res.status_code == 201
        assert res.json()["product_code"] == "SM2401"

        # 목록에 상품 포함 확인
        ins_list = await c.get("/api/v1/insurers/")
        products = ins_list.json()[0]["products"]
        assert len(products) == 1


@pytest.mark.asyncio
async def test_update_insurer(admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        ins = await c.post("/api/v1/insurers/", json={"name": "AXA", "code": "axa"}, headers=headers)
        ins_id = ins.json()["id"]

        res = await c.patch(f"/api/v1/insurers/{ins_id}", json={"name": "AXA손해보험"}, headers=headers)
        assert res.status_code == 200
        assert res.json()["name"] == "AXA손해보험"


@pytest.mark.asyncio
async def test_delete_insurer(admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        ins = await c.post("/api/v1/insurers/", json={"name": "메리츠", "code": "meritz"}, headers=headers)
        ins_id = ins.json()["id"]

        res = await c.delete(f"/api/v1/insurers/{ins_id}", headers=headers)
        assert res.status_code == 204

        res2 = await c.get("/api/v1/insurers/")
        assert res2.json() == []
