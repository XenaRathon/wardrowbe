import pytest
from datetime import date
from uuid import uuid4

from app.models.item import ClothingItem, ItemHistory, ItemStatus
from app.models.outfit import Outfit, OutfitItem, OutfitStatus, OutfitSource
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


@pytest.mark.asyncio
async def test_confirm_logs_items(db_session):
    from sqlalchemy import select, func

    u = await _user(db_session)
    d = date(2026, 7, 4)
    item = ClothingItem(id=uuid4(), user_id=u.id, image_path="x.jpg", type="shirt",
                        status=ItemStatus.ready, wear_count=0)
    o = Outfit(id=uuid4(), user_id=u.id, occasion="casual", status=OutfitStatus.pending,
               source=OutfitSource.manual, scheduled_for=d)
    db_session.add_all([item, o]); await db_session.commit()
    db_session.add(OutfitItem(outfit_id=o.id, item_id=item.id, position=0)); await db_session.commit()

    await CalendarService(db_session).confirm(u, d)
    await db_session.refresh(item); await db_session.refresh(o)
    assert o.worn_at == d
    assert item.wear_count == 1
    n = (await db_session.execute(
        select(func.count()).select_from(ItemHistory).where(ItemHistory.item_id == item.id)
    )).scalar()
    assert n == 1
    # idempotent
    await CalendarService(db_session).confirm(u, d)
    await db_session.refresh(item)
    assert item.wear_count == 1


@pytest.mark.asyncio
async def test_remove_wear_reverses_cascade(db_session):
    from sqlalchemy import select, func

    u = await _user(db_session)
    d = date(2026, 7, 4)
    item = ClothingItem(id=uuid4(), user_id=u.id, image_path="y.jpg", type="pants",
                        status=ItemStatus.ready, wear_count=0)
    o = Outfit(id=uuid4(), user_id=u.id, occasion="casual", status=OutfitStatus.pending,
               source=OutfitSource.manual, scheduled_for=d)
    db_session.add_all([item, o]); await db_session.commit()
    db_session.add(OutfitItem(outfit_id=o.id, item_id=item.id, position=0)); await db_session.commit()

    await CalendarService(db_session).confirm(u, d)
    await db_session.refresh(item)
    assert item.wear_count == 1

    await CalendarService(db_session).remove_wear(u, d, o.id)
    await db_session.refresh(item); await db_session.refresh(o)
    assert o.worn_at is None
    assert item.wear_count == 0
    n = (await db_session.execute(
        select(func.count()).select_from(ItemHistory).where(ItemHistory.item_id == item.id)
    )).scalar()
    assert n == 0
