"""Tests for the nightly re-tag backfill worker (check_retag_backfill)."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.item import ClothingItem, ItemStatus
from app.models.user import User
from app.services.ai_service import AIService, ClothingTags
from app.workers.retag import check_retag_backfill


@pytest_asyncio.fixture(autouse=True)
async def clean_items(db_session: AsyncSession):
    await db_session.execute(delete(ClothingItem))
    await db_session.commit()


@pytest_asyncio.fixture
async def retag_user(db_session: AsyncSession) -> User:
    unique_id = uuid.uuid4()
    user = User(
        id=unique_id,
        external_id=f"retag-user-{unique_id}",
        email=f"retag-{unique_id}@example.com",
        display_name="Retag User",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


def _make_item(user: User, *, neckline: str | None = None, image_path: str = "items/foo.jpg"):
    return ClothingItem(
        id=uuid.uuid4(),
        user_id=user.id,
        image_path=image_path,
        type="shirt",
        subtype=None,
        status=ItemStatus.ready,
        ai_processed=True,
        neckline=neckline,
        rise=None,
        silhouette=None,
        sleeve_length=None,
    )


def _fake_tags(**overrides) -> ClothingTags:
    defaults = dict(
        type="shirt",
        subtype="button-down",
        primary_color="blue",
        neckline="v-neck",
        rise=None,
        silhouette="slim",
        sleeve_length="long",
        confidence=0.9,
    )
    defaults.update(overrides)
    return ClothingTags(**defaults)


class TestCheckRetagBackfill:
    @pytest.mark.asyncio
    async def test_item_with_null_cut_attrs_is_backfilled(
        self, db_session: AsyncSession, retag_user: User
    ):
        item = _make_item(retag_user)
        db_session.add(item)
        await db_session.commit()

        analyze_mock = AsyncMock(return_value=_fake_tags())
        ctx: dict = {}

        with (
            patch("app.workers.retag.get_db_session", return_value=db_session),
            patch.object(db_session, "close", new_callable=AsyncMock),
            patch.object(AIService, "analyze_image", analyze_mock),
        ):
            result = await check_retag_backfill(ctx)

        await db_session.refresh(item)
        assert item.neckline == "v-neck"
        assert item.silhouette == "slim"
        assert item.sleeve_length == "long"
        analyze_mock.assert_called_once()
        assert result["retagged"] == 1

    @pytest.mark.asyncio
    async def test_item_with_existing_cut_attr_is_not_retagged(
        self, db_session: AsyncSession, retag_user: User
    ):
        item = _make_item(retag_user, neckline="crew")
        db_session.add(item)
        await db_session.commit()

        analyze_mock = AsyncMock(return_value=_fake_tags())
        ctx: dict = {}

        with (
            patch("app.workers.retag.get_db_session", return_value=db_session),
            patch.object(db_session, "close", new_callable=AsyncMock),
            patch.object(AIService, "analyze_image", analyze_mock),
        ):
            result = await check_retag_backfill(ctx)

        await db_session.refresh(item)
        assert item.neckline == "crew"
        analyze_mock.assert_not_called()
        assert result["retagged"] == 0
