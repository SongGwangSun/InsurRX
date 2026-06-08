"""마이데이터 연동 엔드포인트 테스트."""
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

BASE = "/api/v1/mydata"


async def _register_and_token(email: str) -> str:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        res = await c.post("/api/v1/auth/register", json={
            "name": "테스터", "email": email, "password": "pass1234"
        })
    return res.json()["access_token"]


@pytest.mark.asyncio
async def test_connect_mydata_success():
    token = await _register_and_token("md1@test.com")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        res = await c.post(
            f"{BASE}/connect",
            json={"name": "홍길동", "birth_date": "19900101"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert res.status_code == 200
    data = res.json()
    assert data["connected_count"] >= 1
    assert len(data["policies"]) == data["connected_count"]
    assert "연결되었습니다" in data["message"]


@pytest.mark.asyncio
async def test_connect_same_name_birth_deterministic():
    """같은 이름+생년월일은 항상 동일한 보험 목록을 반환합니다."""
    token = await _register_and_token("md2@test.com")
    payload = {"name": "이순신", "birth_date": "19800515"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r1 = await c.post(f"{BASE}/connect", json=payload, headers={"Authorization": f"Bearer {token}"})
        r2 = await c.post(f"{BASE}/connect", json=payload, headers={"Authorization": f"Bearer {token}"})
    names1 = sorted(p["insurance_name"] for p in r1.json()["policies"])
    names2 = sorted(p["insurance_name"] for p in r2.json()["policies"])
    assert names1 == names2


@pytest.mark.asyncio
async def test_list_policies_after_connect():
    token = await _register_and_token("md3@test.com")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await c.post(f"{BASE}/connect",
                     json={"name": "김유신", "birth_date": "19950320"},
                     headers={"Authorization": f"Bearer {token}"})
        res = await c.get(f"{BASE}/policies", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert len(res.json()) >= 1


@pytest.mark.asyncio
async def test_list_policies_empty_before_connect():
    token = await _register_and_token("md4@test.com")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        res = await c.get(f"{BASE}/policies", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json() == []


@pytest.mark.asyncio
async def test_disconnect_policy():
    token = await _register_and_token("md5@test.com")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        conn = await c.post(f"{BASE}/connect",
                            json={"name": "강감찬", "birth_date": "19881201"},
                            headers={"Authorization": f"Bearer {token}"})
        policy_id = conn.json()["policies"][0]["id"]

        del_res = await c.delete(f"{BASE}/policies/{policy_id}",
                                 headers={"Authorization": f"Bearer {token}"})
        assert del_res.status_code == 204

        lst = await c.get(f"{BASE}/policies", headers={"Authorization": f"Bearer {token}"})
        ids = [p["id"] for p in lst.json()]
        assert policy_id not in ids


@pytest.mark.asyncio
async def test_disconnect_all():
    token = await _register_and_token("md6@test.com")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await c.post(f"{BASE}/connect",
                     json={"name": "세종대왕", "birth_date": "20000701"},
                     headers={"Authorization": f"Bearer {token}"})
        del_res = await c.delete(f"{BASE}/disconnect", headers={"Authorization": f"Bearer {token}"})
        assert del_res.status_code == 204
        lst = await c.get(f"{BASE}/policies", headers={"Authorization": f"Bearer {token}"})
        assert lst.json() == []


@pytest.mark.asyncio
async def test_invalid_birth_date():
    token = await _register_and_token("md7@test.com")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        res = await c.post(f"{BASE}/connect",
                           json={"name": "홍길동", "birth_date": "abcd"},
                           headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_has_rag_data_flag():
    """vector_policy_id 있는 보험은 has_rag_data=True."""
    token = await _register_and_token("md8@test.com")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        conn = await c.post(f"{BASE}/connect",
                            json={"name": "홍길동", "birth_date": "19900101"},
                            headers={"Authorization": f"Bearer {token}"})
    policies = conn.json()["policies"]
    rag_policies = [p for p in policies if p["has_rag_data"]]
    # 홍길동/19900101은 결정론적이므로 RAG 데이터 있는 보험이 최소 1개
    assert len(rag_policies) >= 1
    for p in rag_policies:
        assert p["vector_policy_id"] is not None
