import pytest
from datetime import date
from uuid import uuid4

from app.models.item import ClothingItem, ItemHistory, ItemStatus
from app.models.outfit import Outfit, OutfitItem, OutfitStatus, OutfitSource
from app.models.preference import UserPreference
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


@pytest.mark.asyncio
async def test_remove_wear_reverses_wash_cascade(db_session):
    """remove_wear must undo wears_since_wash/needs_wash/last_worn_at, not just wear_count."""
    u = await _user(db_session)
    d = date(2026, 7, 4)
    # wash_interval=1 so a single wear immediately flips needs_wash True.
    item = ClothingItem(id=uuid4(), user_id=u.id, image_path="z.jpg", type="pants",
                        status=ItemStatus.ready, wear_count=0, wash_interval=1)
    o = Outfit(id=uuid4(), user_id=u.id, occasion="casual", status=OutfitStatus.pending,
               source=OutfitSource.manual, scheduled_for=d)
    db_session.add_all([item, o]); await db_session.commit()
    db_session.add(OutfitItem(outfit_id=o.id, item_id=item.id, position=0)); await db_session.commit()

    await CalendarService(db_session).confirm(u, d)
    await db_session.refresh(item)
    assert item.wears_since_wash == 1
    assert item.needs_wash is True
    assert item.last_worn_at == d

    await CalendarService(db_session).remove_wear(u, d, o.id)
    await db_session.refresh(item)
    assert item.wears_since_wash == 0
    assert item.needs_wash is False
    assert item.last_worn_at is None


@pytest.mark.asyncio
async def test_log_wear_outfit_rejects_non_family_wearer(db_session):
    u = await _user(db_session)
    stranger = await _user(db_session)
    d = date(2026, 7, 4)
    o = await _outfit(db_session, u, scheduled_for=d)

    with pytest.raises(ValueError, match="family member"):
        await CalendarService(db_session).log_wear_outfit(u, d, o.id, stranger.id)


@pytest.mark.asyncio
async def test_auto_confirm_due_confirms_planned(db_session):
    from datetime import date
    from uuid import uuid4

    from app.models.item import ClothingItem, ItemStatus, ItemHistory
    from app.models.outfit import Outfit, OutfitItem, OutfitStatus, OutfitSource
    from app.services.calendar_service import CalendarService
    from sqlalchemy import select, func

    u = await _user(db_session)
    d = date(2026, 7, 4)
    item = ClothingItem(id=uuid4(), user_id=u.id, image_path="x.jpg", type="shirt",
                        status=ItemStatus.ready, wear_count=0)
    o = Outfit(id=uuid4(), user_id=u.id, occasion="casual", status=OutfitStatus.pending,
               source=OutfitSource.manual, scheduled_for=d)
    db_session.add_all([item, o]); await db_session.commit()
    db_session.add(OutfitItem(outfit_id=o.id, item_id=item.id, position=0)); await db_session.commit()

    n = await CalendarService(db_session).auto_confirm_due(u, d)
    await db_session.refresh(item); await db_session.refresh(o)
    assert n == 1
    assert o.worn_at == d
    assert item.wear_count == 1
    # idempotent
    assert await CalendarService(db_session).auto_confirm_due(u, d) == 0
    await db_session.refresh(item)
    assert item.wear_count == 1


@pytest.mark.asyncio
async def test_recently_worn_flags_within_window(db_session):
    from datetime import timedelta

    u = await _user(db_session)
    db_session.add(UserPreference(user_id=u.id, avoid_repeat_days=7)); await db_session.commit()
    shirt = ClothingItem(id=uuid4(), user_id=u.id, image_path="x", type="shirt", status=ItemStatus.ready)
    shoes = ClothingItem(id=uuid4(), user_id=u.id, image_path="y", type="shoes", status=ItemStatus.ready)
    db_session.add_all([shirt, shoes]); await db_session.commit()
    d = date(2026, 7, 10)
    db_session.add_all([
        ItemHistory(item_id=shirt.id, worn_at=d - timedelta(days=2)),
        ItemHistory(item_id=shoes.id, worn_at=d - timedelta(days=1)),
    ]); await db_session.commit()

    flagged = await CalendarService(db_session).recently_worn(u, [shirt.id, shoes.id], d)
    assert shirt.id in flagged
    assert shoes.id not in flagged   # shoes excluded
