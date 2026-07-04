import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_get_style_profile(client, auth_headers, test_user, db_session):
    test_user.body_measurements = {"bust": 94, "waist": 68, "hips": 96, "shoulders": 94, "height": 168}
    await db_session.commit()
    r = await client.get("/api/v1/style-profile", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["body_shape"] == "hourglass"


@pytest.mark.asyncio
async def test_put_style_profile_saves_confirmed(client, auth_headers):
    r = await client.put("/api/v1/style-profile", headers=auth_headers,
                         json={"color_season": "soft-autumn", "palette": ["olive"], "season_confirmed": True})
    assert r.status_code == 200
    g = await client.get("/api/v1/style-profile", headers=auth_headers)
    assert g.json()["color_season"] == "soft-autumn" and g.json()["season_confirmed"] is True


@pytest.mark.asyncio
async def test_draft_returns_advisory_labels(client, auth_headers):
    with patch("app.services.style_service.StyleService._call_model",
               new=AsyncMock(return_value={"color_season": "cool-winter", "kibbe_lean": "dramatic"})):
        r = await client.post("/api/v1/style-profile/draft", headers=auth_headers,
                              json={"hints": {"undertone": "cool", "contrast": "high"}})
    assert r.status_code == 200
    assert r.json()["color_season"] == "cool-winter"
