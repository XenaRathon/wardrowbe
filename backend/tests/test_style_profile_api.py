from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.services.ai_service import AIDisabledError
from app.style_rules import palette_for


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
async def test_put_style_profile_derives_palette_from_color_season(client, auth_headers):
    """When the client saves a color_season without an explicit palette (the frontend
    can't compute the season->palette map -- that's backend-only), the backend must
    derive it via style_rules.palette_for so downstream colour-season scoring can fire."""
    r = await client.put("/api/v1/style-profile", headers=auth_headers,
                         json={"color_season": "soft-autumn", "season_confirmed": True})
    assert r.status_code == 200

    g = await client.get("/api/v1/style-profile", headers=auth_headers)
    body = g.json()
    assert body["palette"] == palette_for("soft-autumn")
    assert body["palette"] != []


@pytest.mark.asyncio
async def test_put_style_profile_respects_explicit_palette(client, auth_headers):
    """If the client DOES pass an explicit palette, it must be respected as-is,
    not overwritten by the derived season->palette lookup."""
    r = await client.put("/api/v1/style-profile", headers=auth_headers,
                         json={"color_season": "soft-autumn", "palette": ["olive"],
                               "season_confirmed": True})
    assert r.status_code == 200

    g = await client.get("/api/v1/style-profile", headers=auth_headers)
    assert g.json()["palette"] == ["olive"]


@pytest.mark.asyncio
async def test_draft_returns_advisory_labels(client, auth_headers):
    with patch("app.services.style_service.StyleService._call_model",
               new=AsyncMock(return_value={"color_season": "cool-winter", "kibbe_lean": "dramatic"})):
        r = await client.post("/api/v1/style-profile/draft", headers=auth_headers,
                              json={"hints": {"undertone": "cool", "contrast": "high"}})
    assert r.status_code == 200
    assert r.json()["color_season"] == "cool-winter"


@pytest.mark.asyncio
async def test_draft_ai_failure_returns_503_not_500(client, auth_headers):
    """When every AI endpoint is unreachable, _call_model's raw httpx error must be
    translated to a clean 503 (StyleDraftError), not bubble up as an unhandled 500."""
    with patch(
        "app.services.style_service.StyleService._call_model",
        new=AsyncMock(side_effect=httpx.RequestError("connection refused")),
    ):
        r = await client.post(
            "/api/v1/style-profile/draft",
            headers=auth_headers,
            json={"hints": {"undertone": "cool"}},
        )
    assert r.status_code == 503
    assert "AI" in r.json()["detail"]


@pytest.mark.asyncio
async def test_draft_defers_cleanly_when_capability_disabled(client, auth_headers):
    """If the relevant capability (vision, since an image is supplied) is disabled,
    the route should defer via AIDisabledError -> 503, not attempt the AI call at all."""
    with (
        patch(
            "app.services.style_service.require_internal_ai",
            side_effect=AIDisabledError("Internal AI vision is disabled"),
        ) as mock_guard,
        patch(
            "app.services.style_service.StyleService._call_model",
            new=AsyncMock(),
        ) as mock_call,
    ):
        r = await client.post(
            "/api/v1/style-profile/draft",
            headers=auth_headers,
            json={"hints": {}, "image_b64": "Zm9v"},
        )
    assert r.status_code == 503
    mock_guard.assert_called_once_with("vision")
    mock_call.assert_not_called()


@pytest.mark.asyncio
async def test_guidance_uses_rules(client, auth_headers, test_user, db_session):
    test_user.body_measurements = {"bust": 88, "waist": 72, "hips": 104, "shoulders": 86}  # pear
    await db_session.commit()
    from unittest.mock import AsyncMock, patch
    with patch("app.services.style_service.StyleService._call_model_text",
               new=AsyncMock(return_value="You're a pear — emphasise the waist and shoulders.")):
        r = await client.get("/api/v1/style-profile/guidance", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    # structured guidance is deterministic from the rule base, not the LLM
    assert "a-line" in body["recommended"].get("silhouette", [])
    assert isinstance(body["summary"], str) and body["summary"]


@pytest.mark.asyncio
async def test_draft_capability_guard_uses_vision_for_image_and_text_otherwise(client, auth_headers):
    """require_internal_ai must be called with 'vision' when an image is provided and
    'text' otherwise, so a vision-disabled/text-enabled config can't slip through."""
    with (
        patch(
            "app.services.style_service.require_internal_ai",
        ) as mock_guard,
        patch(
            "app.services.style_service.StyleService._call_model",
            new=AsyncMock(return_value={"color_season": "cool-winter", "kibbe_lean": "dramatic"}),
        ),
    ):
        r = await client.post(
            "/api/v1/style-profile/draft",
            headers=auth_headers,
            json={"hints": {}, "image_b64": "Zm9v"},
        )
        assert r.status_code == 200
        mock_guard.assert_called_once_with("vision")

        mock_guard.reset_mock()
        r = await client.post(
            "/api/v1/style-profile/draft",
            headers=auth_headers,
            json={"hints": {"undertone": "cool"}},
        )
        assert r.status_code == 200
        mock_guard.assert_called_once_with("text")
