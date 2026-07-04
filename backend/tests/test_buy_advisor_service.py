from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_recommendations_returns_search_links(db_session, test_user):
    from app.services.buy_advisor_service import BuyAdvisorService
    # give the user a lopsided closet via the service's item query — or patch analyze_gaps
    with patch("app.services.buy_advisor_service.BuyAdvisorService._owned_types",
               new=AsyncMock(return_value=["t-shirt"] * 6 + ["sneakers", "sneakers"])):
        recs = await BuyAdvisorService(db_session).recommendations(test_user)
    assert recs and recs[0]["search_links"]
    assert recs[0]["search_links"][0]["url"].startswith("http")


@pytest.mark.asyncio
async def test_size_for_url_falls_back_on_fetch_failure(db_session, test_user):
    from app.services.buy_advisor_service import BuyAdvisorService
    test_user.body_measurements = {"chest": 96, "waist": 84}
    svc = BuyAdvisorService(db_session)
    with patch.object(svc, "_fetch_page", new=AsyncMock(return_value=None)):
        out = await svc.size_for_url(test_user, "http://x/product")
    assert out["source"] == "measurement"
    assert out["size"] in {"XS", "S", "M", "L", "XL"}


@pytest.mark.asyncio
async def test_size_for_url_uses_chart_when_parsed(db_session, test_user):
    from app.services.buy_advisor_service import BuyAdvisorService
    test_user.body_measurements = {"chest": 96, "waist": 84}
    svc = BuyAdvisorService(db_session)
    chart = {"S": {"chest": 88}, "M": {"chest": 96}, "L": {"chest": 104}}
    with patch.object(svc, "_fetch_page", new=AsyncMock(return_value="<html>chart</html>")), \
         patch.object(svc, "_parse_chart", new=AsyncMock(return_value=chart)):
        out = await svc.size_for_url(test_user, "http://x/product")
    assert out["source"] == "chart"
    assert out["size"] == "M"        # 96 matches M exactly
