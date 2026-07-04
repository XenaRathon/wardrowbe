import pytest
from datetime import date
from uuid import uuid4

from app.models.outfit import Outfit, OutfitStatus, OutfitSource
from app.models.user import User
from app.services.calendar_service import CalendarService


async def _user(db):
    u = User(id=uuid4(), external_id=f"e{uuid4()}", email=f"{uuid4()}@e.com", display_name="U",
             timezone="UTC", is_active=True, onboarding_completed=True)
    db.add(u); await db.commit(); await db.refresh(u); return u


async def _outfit(db, user, *, scheduled_for=None, worn_at=None):
    o = Outfit(id=uuid4(), user_id=user.id, occasion="casual",
               status=OutfitStatus.pending, source=OutfitSource.manual,
               scheduled_for=scheduled_for, worn_at=worn_at)
    db.add(o); await db.commit(); await db.refresh(o); return o


@pytest.mark.asyncio
async def test_get_range_primary_and_extras(db_session):
    u = await _user(db_session)
    d = date(2026, 7, 4)
    planned = await _outfit(db_session, u, scheduled_for=d, worn_at=d)  # confirmed plan
    extra = await _outfit(db_session, u, worn_at=d)                      # gym fit
    recs = await CalendarService(db_session).get_range(u, d, d)
    day = next(r for r in recs if r["date"] == d)
    assert day["primary"]["id"] == planned.id
    assert extra.id in [e["id"] for e in day["extras"]]
