from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_get_buy_advisor(client, auth_headers, test_user):
    with patch("app.services.buy_advisor_service.BuyAdvisorService._owned_types",
               new=AsyncMock(return_value=["t-shirt"] * 5 + ["sneakers"])):
        r = await client.get("/api/v1/buy-advisor", headers=auth_headers)
    assert r.status_code == 200
    assert "recommendations" in r.json()


@pytest.mark.asyncio
async def test_post_size_measurement_fallback(client, auth_headers, test_user, db_session):
    test_user.body_measurements = {"chest": 96}
    await db_session.commit()
    with patch("app.services.buy_advisor_service.BuyAdvisorService._fetch_page",
               new=AsyncMock(return_value=None)):
        r = await client.post("/api/v1/buy-advisor/size", headers=auth_headers,
                             json={"product_url": "http://x/p"})
    assert r.status_code == 200
    assert r.json()["source"] == "measurement"
