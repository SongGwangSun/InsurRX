"""
개인정보 보관 기한 정리와 회원 탈퇴 테스트
"""
from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.database import get_db
from app.main import app
from app.models.analysis_result import AnalysisResult
from app.models.login_history import LoginHistory
from app.models.user import User
from app.services.retention import purge_expired


def _result(session_id: str, user_id: int | None, created_at: datetime) -> AnalysisResult:
    return AnalysisResult(
        session_id=session_id, user_id=user_id, is_claimable=True, estimated_payout=18500,
        breakdown={}, coverage_items=[], confidence=0.9, llm_summary="급성상기도감염 통원",
        created_at=created_at,
    )


async def _db():
    gen = app.dependency_overrides[get_db]()
    return gen, await gen.__anext__()


async def _register(c: AsyncClient, email: str) -> str:
    res = await c.post("/api/v1/auth/register", json={"name": "탈퇴", "email": email, "password": "pass1234"})
    return res.json()["access_token"]


@pytest.mark.asyncio
async def test_purge_removes_only_expired_guest_results_and_old_logins():
    gen, db = await _db()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    user = User(email="keep@test.com", name="회원", password_hash="x")
    db.add(user)
    await db.flush()
    db.add_all([
        _result("guest-old", None, now - timedelta(hours=25)),
        _result("guest-new", None, now - timedelta(hours=1)),
        _result("member-old", user.id, now - timedelta(days=400)),
        LoginHistory(user_id=user.id, email="keep@test.com", status="success", created_at=now - timedelta(days=400)),
        LoginHistory(user_id=user.id, email="keep@test.com", status="success", created_at=now - timedelta(days=1)),
    ])
    await db.commit()

    counts = await purge_expired(db)

    assert counts == {"guest_results": 1, "login_history": 1}
    left = (await db.execute(select(AnalysisResult.session_id))).scalars().all()
    assert sorted(left) == ["guest-new", "member-old"]
    await gen.aclose()


@pytest.mark.asyncio
async def test_delete_me_requires_password_and_removes_member_data():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        token = await _register(c, "bye@test.com")
        headers = {"Authorization": f"Bearer {token}"}
        me = (await c.get("/api/v1/auth/me", headers=headers)).json()

        gen, db = await _db()
        db.add(_result("member-result", me["id"], datetime.now(timezone.utc).replace(tzinfo=None)))
        await db.commit()
        await gen.aclose()

        wrong = await c.request("DELETE", "/api/v1/auth/me", headers=headers, json={"password": "nope"})
        assert wrong.status_code == 400

        res = await c.request("DELETE", "/api/v1/auth/me", headers=headers, json={"password": "pass1234"})
        assert res.status_code == 204
        assert (await c.get("/api/v1/auth/me", headers=headers)).status_code == 401

    gen, db = await _db()
    assert (await db.execute(select(func.count()).select_from(AnalysisResult))).scalar() == 0
    assert (await db.execute(select(func.count()).select_from(User))).scalar() == 0
    await gen.aclose()
