"""
사용자 보험증권 업로드 / 목록 / 삭제 엔드포인트 테스트
"""
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


async def _register_and_token(email: str, name: str = "테스터") -> str:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        res = await c.post("/api/v1/auth/register", json={
            "name": name, "email": email, "password": "pass1234"
        })
    return res.json()["access_token"]


@pytest.mark.asyncio
async def test_list_policies_empty():
    token = await _register_and_token("a@test.com")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        res = await c.get("/api/v1/my/policies/", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json() == []


@pytest.mark.asyncio
async def test_list_policies_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        res = await c.get("/api/v1/my/policies/")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_upload_policy_success():
    token = await _register_and_token("b@test.com")
    dummy_pdf = b"%PDF-1.4 fake content"

    with patch("app.services.user_policy_service.process_user_policy", new_callable=AsyncMock):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            res = await c.post(
                "/api/v1/my/policies/upload",
                headers={"Authorization": f"Bearer {token}"},
                files={"file": ("test.pdf", dummy_pdf, "application/pdf")},
            )
    assert res.status_code == 202
    data = res.json()
    assert data["original_name"] == "test.pdf"
    assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_upload_policy_invalid_type():
    token = await _register_and_token("c@test.com")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        res = await c.post(
            "/api/v1/my/policies/upload",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("test.txt", b"hello", "text/plain")},
        )
    assert res.status_code == 400
    assert "지원하지 않는" in res.json()["detail"]


@pytest.mark.asyncio
async def test_upload_and_delete_policy():
    token = await _register_and_token("d@test.com")
    dummy_img = b"\xff\xd8\xff" + b"\x00" * 100  # minimal JPEG header

    with patch("app.services.user_policy_service.process_user_policy", new_callable=AsyncMock):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            upload = await c.post(
                "/api/v1/my/policies/upload",
                headers={"Authorization": f"Bearer {token}"},
                files={"file": ("receipt.jpg", dummy_img, "image/jpeg")},
            )
            policy_id = upload.json()["policy_id"]

            # 목록 조회
            lst = await c.get("/api/v1/my/policies/", headers={"Authorization": f"Bearer {token}"})
            assert len(lst.json()) == 1

            # 삭제
            del_res = await c.delete(
                f"/api/v1/my/policies/{policy_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert del_res.status_code == 204

            # 삭제 후 목록 비어 있는지 확인
            lst2 = await c.get("/api/v1/my/policies/", headers={"Authorization": f"Bearer {token}"})
            assert lst2.json() == []


@pytest.mark.asyncio
async def test_cannot_access_other_user_policy():
    token_a = await _register_and_token("e@test.com", "유저A")
    token_b = await _register_and_token("f@test.com", "유저B")
    dummy_pdf = b"%PDF-1.4 fake"

    with patch("app.services.user_policy_service.process_user_policy", new_callable=AsyncMock):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            upload = await c.post(
                "/api/v1/my/policies/upload",
                headers={"Authorization": f"Bearer {token_a}"},
                files={"file": ("a.pdf", dummy_pdf, "application/pdf")},
            )
            policy_id = upload.json()["policy_id"]

            res = await c.get(
                f"/api/v1/my/policies/{policy_id}",
                headers={"Authorization": f"Bearer {token_b}"},
            )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_delete_ready_policy():
    """임베딩 완료(ready) 보험증권 삭제 — Pinecone 정리 분기를 거쳐도 204."""
    from sqlalchemy import update

    from app.database import get_db
    from app.models.user_policy import PolicyStatus, UserPolicy

    token = await _register_and_token("ready@test.com")
    headers = {"Authorization": f"Bearer {token}"}
    with patch("app.services.user_policy_service.process_user_policy", new_callable=AsyncMock):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            upload = await c.post(
                "/api/v1/my/policies/upload",
                headers=headers,
                files={"file": ("policy.pdf", b"%PDF-1.4 fake", "application/pdf")},
            )
            policy_id = upload.json()["policy_id"]

            gen = app.dependency_overrides[get_db]()
            db = await gen.__anext__()
            await db.execute(
                update(UserPolicy).where(UserPolicy.id == policy_id).values(status=PolicyStatus.ready)
            )
            await db.commit()
            await gen.aclose()

            del_res = await c.delete(f"/api/v1/my/policies/{policy_id}", headers=headers)
    assert del_res.status_code == 204
