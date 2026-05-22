import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch, MagicMock
from app.main import app


@pytest.mark.asyncio
async def test_waitlist_register_success():
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None

    with patch("app.api.v1.endpoints_waitlist.get_db") as mock_get_db:
        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result
        mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_get_db.return_value.__aexit__ = AsyncMock(return_value=False)

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[__import__('app.database', fromlist=['get_db']).get_db] = override_get_db

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/waitlist/",
                json={"email": "test@example.com", "source": "landing"},
            )

        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["already_registered"] is False
    assert "완료" in data["message"]


@pytest.mark.asyncio
async def test_waitlist_invalid_email():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/waitlist/",
            json={"email": "not-an-email", "source": "landing"},
        )
    assert response.status_code == 422
