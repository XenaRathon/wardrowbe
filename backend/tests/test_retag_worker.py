"""Tests for the nightly re-tag backfill worker (check_retag_backfill)."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.item import ClothingItem, ItemStatus
from app.models.user import User
from app.services.ai_service import AIService, ClothingTags
from app.workers.retag import check_retag_backfill

# The four cut attributes the Styler tagging feature introduced; used below to
# build a ClothingTags response for un-enrichable item types (footwear, bags,
# belts, etc.) that legitimately never get any of them.
_ALL_NONE_CUT_ATTRS = {"neckline": None, "rise": None, "silhouette": None, "sleeve_length": None}


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


def _make_item(
    user: User,
    *,
    neckline: str | None = None,
    image_path: str = "items/foo.jpg",
    cut_attrs_checked_at=None,
):
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
        cut_attrs_checked_at=cut_attrs_checked_at,
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
        assert item.cut_attrs_checked_at is not None
        analyze_mock.assert_called_once()
        assert result["retagged"] == 1

    @pytest.mark.asyncio
    async def test_item_already_checked_is_not_retagged(
        self, db_session: AsyncSession, retag_user: User
    ):
        """Once cut_attrs_checked_at is set (whatever the cut attr values),
        the item has left the candidate set for good — the gate is the
        checked marker, not the attribute values themselves.
        """
        item = _make_item(retag_user, neckline="crew", cut_attrs_checked_at=datetime.now(UTC))
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

    @pytest.mark.asyncio
    async def test_analyze_image_is_called_with_resolved_storage_path(
        self, db_session: AsyncSession, retag_user: User
    ):
        """The AI layer must receive a full filesystem path, not the bare
        relative storage key stored on the item — regression test for the
        FileNotFoundError bug where every item silently failed to backfill.
        """
        item = _make_item(retag_user, image_path="items/foo.jpg")
        db_session.add(item)
        await db_session.commit()

        analyze_mock = AsyncMock(return_value=_fake_tags())
        ctx: dict = {}

        with (
            patch("app.workers.retag.get_db_session", return_value=db_session),
            patch.object(db_session, "close", new_callable=AsyncMock),
            patch.object(AIService, "analyze_image", analyze_mock),
        ):
            await check_retag_backfill(ctx)

        analyze_mock.assert_called_once()
        called_path = analyze_mock.call_args.args[0]
        expected_path = f"{get_settings().storage_path}/{item.image_path}"
        assert called_path == expected_path

    @pytest.mark.asyncio
    async def test_user_set_subtype_is_preserved_while_cut_attrs_backfill(
        self, db_session: AsyncSession, retag_user: User
    ):
        """subtype may have been manually corrected by the user; the backfill
        should only fill it in from AI when it's still None, while the four
        NULL cut attributes are always backfilled.
        """
        item = _make_item(retag_user)
        item.subtype = "user-corrected-subtype"
        db_session.add(item)
        await db_session.commit()

        analyze_mock = AsyncMock(return_value=_fake_tags(subtype="ai-guessed-subtype"))
        ctx: dict = {}

        with (
            patch("app.workers.retag.get_db_session", return_value=db_session),
            patch.object(db_session, "close", new_callable=AsyncMock),
            patch.object(AIService, "analyze_image", analyze_mock),
        ):
            result = await check_retag_backfill(ctx)

        await db_session.refresh(item)
        assert item.subtype == "user-corrected-subtype"
        assert item.neckline == "v-neck"
        assert item.silhouette == "slim"
        assert item.sleeve_length == "long"
        assert result["retagged"] == 1

    @pytest.mark.asyncio
    async def test_unenrichable_item_is_checked_once_and_not_retagged_again(
        self, db_session: AsyncSession, retag_user: User
    ):
        """Item types that legitimately never get cut attributes (footwear,
        bags, belts, socks, ties, jewelry, watches, hats, gloves, scarves,
        ...) must still leave the candidate set after one analysis pass.

        Pre-fix, the gate re-selected "all four cut attrs NULL" every run:
        analyze_image legitimately returns all-None cut attrs for these
        types, setattr(item, field, None) is a no-op, updated_at never
        bumps, and the item sorts to the front of every subsequent batch
        forever — a real GPU call each night, and (at BATCH_SIZE-or-more
        such items) permanent starvation of enrichable items. This test
        fails against that code because the second run's analyze_mock would
        be invoked a second time.
        """
        item = _make_item(retag_user, image_path="items/shoe.jpg")
        db_session.add(item)
        await db_session.commit()

        analyze_mock = AsyncMock(return_value=_fake_tags(**_ALL_NONE_CUT_ATTRS))
        ctx: dict = {}

        with (
            patch("app.workers.retag.get_db_session", return_value=db_session),
            patch.object(db_session, "close", new_callable=AsyncMock),
            patch.object(AIService, "analyze_image", analyze_mock),
        ):
            first_result = await check_retag_backfill(ctx)

        await db_session.refresh(item)
        assert item.neckline is None
        assert item.rise is None
        assert item.silhouette is None
        assert item.sleeve_length is None
        assert item.cut_attrs_checked_at is not None
        analyze_mock.assert_called_once()
        assert first_result["retagged"] == 1

        # Second nightly run: the item must not be picked up again.
        with (
            patch("app.workers.retag.get_db_session", return_value=db_session),
            patch.object(db_session, "close", new_callable=AsyncMock),
            patch.object(AIService, "analyze_image", analyze_mock),
        ):
            second_result = await check_retag_backfill(ctx)

        analyze_mock.assert_called_once()  # still just the one call from the first run
        assert second_result["retagged"] == 0
