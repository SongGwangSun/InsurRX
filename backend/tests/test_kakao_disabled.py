"""카카오 연동 비활성(기본값) 시 엔드포인트가 숨겨지는지 확인."""
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_kakao_endpoints_hidden_by_default():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        res = await c.post("/api/v1/kakao/skill", json={})
        assert res.status_code == 404

        reg = await c.post("/api/v1/auth/register", json={
            "name": "테스트", "email": "nokakao@test.com", "password": "test1234"
        })
        headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
        assert (await c.get("/api/v1/auth/kakao-link", headers=headers)).status_code == 404
        assert (await c.post("/api/v1/auth/kakao-link-code", headers=headers)).status_code == 404
