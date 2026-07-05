from datetime import date
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.item import ClothingItem, ItemHistory, ItemStatus
from app.models.outfit import Outfit, OutfitItem, OutfitSource, OutfitStatus
from app.models.user import User
from app.services.item_service import ItemService


async def _user(db):
    u = User(
        id=uuid4(),
        external_id=f"ext-{uuid4()}",
        email=f"{uuid4()}@e.com",
        display_name="U",
        timezone="UTC",
        is_active=True,
        onboarding_completed=True,
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


@pytest.mark.asyncio
async def test_log_wear_records_wearer_and_increments_once(db_session):
    owner = await _user(db_session)
    wearer = await _user(db_session)
    item = ClothingItem(
        id=uuid4(),
        user_id=owner.id,
        image_path="x.jpg",
        type="jacket",
        status=ItemStatus.ready,
        wear_count=0,
    )
    db_session.add(item)
    await db_session.commit()
    await db_session.refresh(item)

    svc = ItemService(db_session)
    hist = await svc.log_wear(item, worn_at=date(2026, 7, 4), worn_by_user_id=wearer.id)
    await db_session.refresh(item)

    assert hist.worn_by_user_id == wearer.id
    assert item.wear_count == 1
    count = (
        await db_session.execute(
            select(func.count()).select_from(ItemHistory).where(ItemHistory.item_id == item.id)
        )
    ).scalar()
    assert count == 1


@pytest.mark.asyncio
async def test_feedback_worn_path_writes_history_and_does_not_double_count(
    client: AsyncClient, test_user: User, auth_headers: dict[str, str], db_session: AsyncSession
):
    item1 = ClothingItem(
        user_id=test_user.id, image_path="a.jpg", type="shirt", status=ItemStatus.ready
    )
    item2 = ClothingItem(
        user_id=test_user.id, image_path="b.jpg", type="pants", status=ItemStatus.ready
    )
    db_session.add_all([item1, item2])
    await db_session.flush()

    outfit = Outfit(
        user_id=test_user.id,
        occasion="casual",
        scheduled_for=date.today(),
        status=OutfitStatus.pending,
        source=OutfitSource.manual,
    )
    outfit.items.append(OutfitItem(item_id=item1.id, position=0))
    outfit.items.append(OutfitItem(item_id=item2.id, position=1))
    db_session.add(outfit)
    await db_session.commit()
    await db_session.refresh(outfit)

    response = await client.post(
        f"/api/v1/outfits/{outfit.id}/feedback", json={"worn": True}, headers=auth_headers
    )
    assert response.status_code == 200

    # Second submission (e.g. client retry / double-click) must not double-count.
    response2 = await client.post(
        f"/api/v1/outfits/{outfit.id}/feedback", json={"worn": True}, headers=auth_headers
    )
    assert response2.status_code == 200

    for item_id in (item1.id, item2.id):
        count = (
            await db_session.execute(
                select(func.count())
                .select_from(ItemHistory)
                .where(ItemHistory.item_id == item_id, ItemHistory.outfit_id == outfit.id)
            )
        ).scalar()
        assert count == 1

        hist = (
            await db_session.execute(
                select(ItemHistory).where(
                    ItemHistory.item_id == item_id, ItemHistory.outfit_id == outfit.id
                )
            )
        ).scalar_one()
        assert hist.worn_by_user_id == test_user.id

        refreshed_item = await db_session.get(ClothingItem, item_id)
        await db_session.refresh(refreshed_item)
        assert refreshed_item.wear_count == 1
