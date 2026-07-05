"""Tests for notification worker concurrency fixes."""

import uuid
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.item import ClothingItem
from app.models.notification import Notification, NotificationSettings, NotificationStatus
from app.models.preference import UserPreference
from app.models.schedule import Schedule
from app.models.user import User
from app.workers.notifications import (
    check_auto_confirm,
    check_scheduled_notifications,
    check_wash_reminders,
    check_wear_nudges,
    process_scheduled_notification,
)
from app.workers.worker import WorkerSettings


@pytest_asyncio.fixture(autouse=True)
async def clean_schedules(db_session: AsyncSession):
    await db_session.execute(delete(Schedule))
    await db_session.commit()


@pytest_asyncio.fixture
async def schedule_user(db_session: AsyncSession) -> User:
    unique_id = uuid.uuid4()
    user = User(
        id=unique_id,
        external_id=f"sched-user-{unique_id}",
        email=f"sched-{unique_id}@example.com",
        display_name="Schedule User",
        timezone="UTC",
        is_active=True,
        onboarding_completed=True,
        location_lat=Decimal("40.71427800"),
        location_lon=Decimal("-74.00597200"),
        location_name="New York",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def ntfy_channel(db_session: AsyncSession, schedule_user: User) -> NotificationSettings:
    channel = NotificationSettings(
        user_id=schedule_user.id,
        channel="ntfy",
        enabled=True,
        config={"server": "https://ntfy.sh", "topic": "test-topic"},
    )
    db_session.add(channel)
    await db_session.commit()
    await db_session.refresh(channel)
    return channel


@pytest_asyncio.fixture
async def nudge_user(db_session: AsyncSession) -> User:
    """A user with wear_nudge_enabled and a wear_nudge_time comfortably in the
    past, so `check_wear_nudges` always considers them due regardless of
    wall-clock time when the suite runs."""
    unique_id = uuid.uuid4()
    user = User(
        id=unique_id,
        external_id=f"nudge-user-{unique_id}",
        email=f"nudge-{unique_id}@example.com",
        display_name="Nudge User",
        timezone="UTC",
        is_active=True,
        onboarding_completed=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    pref = UserPreference(
        user_id=user.id,
        wear_nudge_enabled=True,
        wear_nudge_time=_past_time(),
    )
    db_session.add(pref)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def nudge_ntfy_channel(db_session: AsyncSession, nudge_user: User) -> NotificationSettings:
    channel = NotificationSettings(
        user_id=nudge_user.id,
        channel="ntfy",
        enabled=True,
        config={"server": "https://ntfy.sh", "topic": "nudge-topic"},
    )
    db_session.add(channel)
    await db_session.commit()
    await db_session.refresh(channel)
    return channel


@pytest_asyncio.fixture
async def future_nudge_user(db_session: AsyncSession) -> User:
    """A user with wear_nudge_enabled but a wear_nudge_time still ahead of the
    user's current local time today, so `check_wear_nudges` must treat them as
    NOT due yet (mirrors nudge_user, inverted)."""
    unique_id = uuid.uuid4()
    user = User(
        id=unique_id,
        external_id=f"future-nudge-user-{unique_id}",
        email=f"future-nudge-{unique_id}@example.com",
        display_name="Future Nudge User",
        timezone="UTC",
        is_active=True,
        onboarding_completed=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    pref = UserPreference(
        user_id=user.id,
        wear_nudge_enabled=True,
        wear_nudge_time=_future_time(),
    )
    db_session.add(pref)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def future_nudge_ntfy_channel(
    db_session: AsyncSession, future_nudge_user: User
) -> NotificationSettings:
    channel = NotificationSettings(
        user_id=future_nudge_user.id,
        channel="ntfy",
        enabled=True,
        config={"server": "https://ntfy.sh", "topic": "future-nudge-topic"},
    )
    db_session.add(channel)
    await db_session.commit()
    await db_session.refresh(channel)
    return channel


@pytest_asyncio.fixture
async def wash_user(db_session: AsyncSession) -> User:
    """A plain active user used to exercise check_wash_reminders in isolation."""
    unique_id = uuid.uuid4()
    user = User(
        id=unique_id,
        external_id=f"wash-user-{unique_id}",
        email=f"wash-{unique_id}@example.com",
        display_name="Wash User",
        timezone="UTC",
        is_active=True,
        onboarding_completed=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def wash_ntfy_channel(db_session: AsyncSession, wash_user: User) -> NotificationSettings:
    channel = NotificationSettings(
        user_id=wash_user.id,
        channel="ntfy",
        enabled=True,
        config={"server": "https://ntfy.sh", "topic": "wash-topic"},
    )
    db_session.add(channel)
    await db_session.commit()
    await db_session.refresh(channel)
    return channel


@pytest_asyncio.fixture
async def dirty_item(db_session: AsyncSession, wash_user: User) -> ClothingItem:
    """A clothing item that is due for a wash: needs_wash=True and not archived
    is exactly what `check_wash_reminders`'s query selects on."""
    item = ClothingItem(
        id=uuid.uuid4(),
        user_id=wash_user.id,
        image_path="/tmp/wardrobe_test/dirty-shirt.jpg",
        type="shirt",
        name="Blue Shirt",
        needs_wash=True,
        is_archived=False,
    )
    db_session.add(item)
    await db_session.commit()
    await db_session.refresh(item)
    return item


class _FakeRedis:
    """Minimal in-memory stand-in for the arq redis pool's get/set, so the
    dedup-key round trip (check_wear_nudges reads back its own write) can be
    exercised across two real invocations instead of mocking away the logic
    under test."""

    def __init__(self):
        self.store: dict[str, str] = {}

    async def get(self, key: str):
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None):
        self.store[key] = value


def _past_time(hours_ago: int = 1) -> time:
    target = datetime.now(UTC) - timedelta(hours=hours_ago)
    return time(target.hour, target.minute)


def _future_time(hours_ahead: int = 1) -> time:
    target = datetime.now(UTC) + timedelta(hours=hours_ahead)
    return time(target.hour, target.minute)


def _make_due_schedule(
    user: User,
    *,
    offset_minutes: int = 0,
    last_triggered_at: datetime | None = None,
    notify_day_before: bool = False,
) -> Schedule:
    now = datetime.now(UTC)
    target = now + timedelta(minutes=offset_minutes)
    day = now.weekday() if not notify_day_before else (now.weekday() + 1) % 7
    return Schedule(
        id=uuid.uuid4(),
        user_id=user.id,
        day_of_week=day,
        notification_time=time(target.hour, target.minute),
        occasion="casual",
        enabled=True,
        notify_day_before=notify_day_before,
        last_triggered_at=last_triggered_at,
    )


# ── check_scheduled_notifications ──


class TestCheckScheduledNotifications:
    @pytest.mark.asyncio
    async def test_due_schedule_gets_marked_and_enqueued(
        self, db_session: AsyncSession, schedule_user: User
    ):
        schedule = _make_due_schedule(schedule_user)
        db_session.add(schedule)
        await db_session.commit()

        enqueue_mock = AsyncMock()
        ctx = {"redis": MagicMock(enqueue_job=enqueue_mock)}

        with (
            patch("app.workers.notifications.get_db_session", return_value=db_session),
            patch.object(db_session, "close", new_callable=AsyncMock),
        ):
            result = await check_scheduled_notifications(ctx)

        assert result["enqueued"] == 1
        enqueue_mock.assert_called_once()
        call_args = enqueue_mock.call_args
        assert call_args.args == ("process_scheduled_notification", str(schedule.id))
        assert call_args.kwargs["_queue_name"] == "arq:tagging"
        assert call_args.kwargs["_job_id"].startswith(f"sched:{schedule.id}:")
        await db_session.refresh(schedule)
        assert schedule.last_triggered_at is not None

    @pytest.mark.asyncio
    async def test_recently_triggered_schedule_is_skipped(
        self, db_session: AsyncSession, schedule_user: User
    ):
        schedule = _make_due_schedule(
            schedule_user,
            last_triggered_at=datetime.now(UTC) - timedelta(minutes=10),
        )
        db_session.add(schedule)
        await db_session.commit()

        ctx = {"redis": MagicMock(enqueue_job=AsyncMock())}

        with (
            patch("app.workers.notifications.get_db_session", return_value=db_session),
            patch.object(db_session, "close", new_callable=AsyncMock),
        ):
            result = await check_scheduled_notifications(ctx)

        assert result["enqueued"] == 0

    @pytest.mark.asyncio
    async def test_schedule_outside_time_window_is_skipped(
        self, db_session: AsyncSession, schedule_user: User
    ):
        schedule = _make_due_schedule(schedule_user, offset_minutes=30)
        db_session.add(schedule)
        await db_session.commit()

        ctx = {"redis": MagicMock(enqueue_job=AsyncMock())}

        with (
            patch("app.workers.notifications.get_db_session", return_value=db_session),
            patch.object(db_session, "close", new_callable=AsyncMock),
        ):
            result = await check_scheduled_notifications(ctx)

        assert result["enqueued"] == 0

    @pytest.mark.asyncio
    async def test_multiple_due_schedules_all_committed_before_enqueue(
        self, db_session: AsyncSession, schedule_user: User
    ):
        s1 = _make_due_schedule(schedule_user)
        s2 = _make_due_schedule(schedule_user)
        s2.occasion = "work"
        db_session.add_all([s1, s2])
        await db_session.commit()

        call_order: list[str] = []
        original_commit = db_session.commit

        async def tracking_commit():
            call_order.append("commit")
            await original_commit()

        enqueue_mock = AsyncMock(side_effect=lambda *a, **kw: call_order.append("enqueue"))
        ctx = {"redis": MagicMock(enqueue_job=enqueue_mock)}

        with (
            patch("app.workers.notifications.get_db_session", return_value=db_session),
            patch.object(db_session, "close", new_callable=AsyncMock),
            patch.object(db_session, "commit", side_effect=tracking_commit),
        ):
            result = await check_scheduled_notifications(ctx)

        assert result["enqueued"] == 2
        # commit happens before any enqueue
        assert call_order.index("commit") < call_order.index("enqueue")

    @pytest.mark.asyncio
    async def test_enqueue_failure_does_not_rollback_last_triggered_at(
        self, db_session: AsyncSession, schedule_user: User
    ):
        schedule = _make_due_schedule(schedule_user)
        db_session.add(schedule)
        await db_session.commit()

        enqueue_mock = AsyncMock(side_effect=ConnectionError("redis down"))
        ctx = {"redis": MagicMock(enqueue_job=enqueue_mock)}

        with (
            patch("app.workers.notifications.get_db_session", return_value=db_session),
            patch.object(db_session, "close", new_callable=AsyncMock),
        ):
            result = await check_scheduled_notifications(ctx)

        # Schedule was still marked even though enqueue failed
        assert result["enqueued"] == 1
        await db_session.refresh(schedule)
        assert schedule.last_triggered_at is not None


# ── process_scheduled_notification ──


class TestProcessScheduledNotification:
    @pytest.mark.asyncio
    async def test_happy_path_generates_outfit_and_sends(
        self, db_session: AsyncSession, schedule_user: User, ntfy_channel
    ):
        schedule = _make_due_schedule(schedule_user)
        db_session.add(schedule)
        await db_session.commit()

        mock_outfit = MagicMock()
        mock_outfit.id = uuid.uuid4()

        mock_rec_service = MagicMock()
        mock_rec_service.generate_recommendation = AsyncMock(return_value=mock_outfit)

        mock_dispatcher = MagicMock()
        mock_dispatcher.send_outfit_notification = AsyncMock(return_value=[])

        ctx = {"job_try": 1}

        with (
            patch("app.workers.notifications.get_db_session", return_value=db_session),
            patch.object(db_session, "close", new_callable=AsyncMock),
            patch(
                "app.workers.notifications.RecommendationService",
                return_value=mock_rec_service,
            ),
            patch(
                "app.workers.notifications.NotificationDispatcher",
                return_value=mock_dispatcher,
            ),
            patch("app.workers.notifications.WeatherService"),
        ):
            result = await process_scheduled_notification(ctx, str(schedule.id))

        assert result["status"] == "sent"
        assert result["outfit_id"] == str(mock_outfit.id)
        mock_rec_service.generate_recommendation.assert_called_once()
        mock_dispatcher.send_outfit_notification.assert_called_once()

    @pytest.mark.asyncio
    async def test_missing_schedule_returns_skipped(self, db_session: AsyncSession):
        ctx = {"job_try": 1}
        fake_id = str(uuid.uuid4())

        with (
            patch("app.workers.notifications.get_db_session", return_value=db_session),
            patch.object(db_session, "close", new_callable=AsyncMock),
        ):
            result = await process_scheduled_notification(ctx, fake_id)

        assert result == {"status": "skipped", "reason": "not_found"}

    @pytest.mark.asyncio
    async def test_deleted_user_returns_skipped(
        self, db_session: AsyncSession, schedule_user: User
    ):
        schedule_user.is_active = False
        await db_session.commit()

        schedule = _make_due_schedule(schedule_user)
        db_session.add(schedule)
        await db_session.commit()

        ctx = {"job_try": 1}

        with (
            patch("app.workers.notifications.get_db_session", return_value=db_session),
            patch.object(db_session, "close", new_callable=AsyncMock),
        ):
            result = await process_scheduled_notification(ctx, str(schedule.id))

        assert result == {"status": "skipped", "reason": "user_not_found"}

    @pytest.mark.asyncio
    async def test_no_enabled_channels_returns_skipped(
        self, db_session: AsyncSession, schedule_user: User
    ):
        schedule = _make_due_schedule(schedule_user)
        db_session.add(schedule)
        await db_session.commit()

        ctx = {"job_try": 1}

        with (
            patch("app.workers.notifications.get_db_session", return_value=db_session),
            patch.object(db_session, "close", new_callable=AsyncMock),
        ):
            result = await process_scheduled_notification(ctx, str(schedule.id))

        assert result == {"status": "skipped", "reason": "no_channels"}

    @pytest.mark.asyncio
    async def test_value_error_from_ai_returns_skipped(
        self, db_session: AsyncSession, schedule_user: User, ntfy_channel
    ):
        schedule = _make_due_schedule(schedule_user)
        db_session.add(schedule)
        await db_session.commit()

        mock_rec_service = MagicMock()
        mock_rec_service.generate_recommendation = AsyncMock(
            side_effect=ValueError("not enough items")
        )

        ctx = {"job_try": 1}

        with (
            patch("app.workers.notifications.get_db_session", return_value=db_session),
            patch.object(db_session, "close", new_callable=AsyncMock),
            patch(
                "app.workers.notifications.RecommendationService",
                return_value=mock_rec_service,
            ),
            patch("app.workers.notifications.WeatherService"),
        ):
            result = await process_scheduled_notification(ctx, str(schedule.id))

        assert result["status"] == "skipped"
        assert "not enough items" in result["reason"]

    @pytest.mark.asyncio
    async def test_generic_exception_rolls_back_and_reraises(
        self, db_session: AsyncSession, schedule_user: User, ntfy_channel
    ):
        schedule = _make_due_schedule(schedule_user)
        db_session.add(schedule)
        await db_session.commit()

        mock_rec_service = MagicMock()
        mock_rec_service.generate_recommendation = AsyncMock(
            side_effect=RuntimeError("AI service down")
        )

        ctx = {"job_try": 1}

        with pytest.raises(RuntimeError, match="AI service down"):
            with (
                patch("app.workers.notifications.get_db_session", return_value=db_session),
                patch.object(db_session, "close", new_callable=AsyncMock),
                patch(
                    "app.workers.notifications.RecommendationService",
                    return_value=mock_rec_service,
                ),
                patch("app.workers.notifications.WeatherService"),
            ):
                await process_scheduled_notification(ctx, str(schedule.id))


# ── check_wear_nudges ──


class TestCheckWearNudges:
    @pytest.mark.asyncio
    async def test_sends_one_nudge_then_dedupes_on_second_run(
        self, db_session: AsyncSession, nudge_user: User, nudge_ntfy_channel: NotificationSettings
    ):
        fake_redis = _FakeRedis()
        ctx = {"redis": fake_redis}
        mock_send = AsyncMock(return_value={"success": True})

        with (
            patch("app.workers.notifications.get_db_session", return_value=db_session),
            patch.object(db_session, "close", new_callable=AsyncMock),
            patch("app.workers.notifications.NtfyProvider.send", mock_send),
        ):
            await check_wear_nudges(ctx)
            await check_wear_nudges(ctx)

        # The full users table is shared (uncommitted-transaction rollback isn't
        # used in this test DB), so other tests' users may also be scanned and
        # notified. Scope assertions to this test's own user via its Notification
        # rows rather than the aggregate "notified" count.
        notifications = (
            await db_session.execute(
                select(Notification).where(
                    Notification.user_id == nudge_user.id,
                    Notification.payload["type"].astext == "wear_nudge",
                )
            )
        ).scalars().all()

        assert len(notifications) == 1
        assert notifications[0].status == NotificationStatus.sent

    @pytest.mark.asyncio
    async def test_skips_user_with_outfit_already_worn_today(
        self, db_session: AsyncSession, nudge_user: User, nudge_ntfy_channel: NotificationSettings
    ):
        from app.models.outfit import Outfit

        outfit = Outfit(
            id=uuid.uuid4(),
            user_id=nudge_user.id,
            occasion="casual",
            worn_at=datetime.now(UTC).date(),
        )
        db_session.add(outfit)
        await db_session.commit()

        ctx = {"redis": _FakeRedis()}
        mock_send = AsyncMock(return_value={"success": True})

        with (
            patch("app.workers.notifications.get_db_session", return_value=db_session),
            patch.object(db_session, "close", new_callable=AsyncMock),
            patch("app.workers.notifications.NtfyProvider.send", mock_send),
        ):
            await check_wear_nudges(ctx)

        notifications = (
            await db_session.execute(
                select(Notification).where(Notification.user_id == nudge_user.id)
            )
        ).scalars().all()
        assert notifications == []

    @pytest.mark.asyncio
    async def test_skips_user_with_nudges_disabled(
        self, db_session: AsyncSession, nudge_user: User, nudge_ntfy_channel: NotificationSettings
    ):
        await db_session.execute(
            UserPreference.__table__.update()
            .where(UserPreference.user_id == nudge_user.id)
            .values(wear_nudge_enabled=False)
        )
        await db_session.commit()

        ctx = {"redis": _FakeRedis()}
        mock_send = AsyncMock(return_value={"success": True})

        with (
            patch("app.workers.notifications.get_db_session", return_value=db_session),
            patch.object(db_session, "close", new_callable=AsyncMock),
            patch("app.workers.notifications.NtfyProvider.send", mock_send),
        ):
            await check_wear_nudges(ctx)

        notifications = (
            await db_session.execute(
                select(Notification).where(Notification.user_id == nudge_user.id)
            )
        ).scalars().all()
        assert notifications == []

    @pytest.mark.asyncio
    async def test_skips_user_with_planned_outfit_today(
        self, db_session: AsyncSession, nudge_user: User, nudge_ntfy_channel: NotificationSettings
    ):
        """A user with a planned-but-unconfirmed outfit for today is never
        nudged - their day gets silently auto-confirmed by check_auto_confirm
        instead, so the two crons don't race."""
        from app.models.outfit import Outfit

        outfit = Outfit(
            id=uuid.uuid4(),
            user_id=nudge_user.id,
            occasion="casual",
            scheduled_for=datetime.now(UTC).date(),
        )
        db_session.add(outfit)
        await db_session.commit()

        ctx = {"redis": _FakeRedis()}
        mock_send = AsyncMock(return_value={"success": True})

        with (
            patch("app.workers.notifications.get_db_session", return_value=db_session),
            patch.object(db_session, "close", new_callable=AsyncMock),
            patch("app.workers.notifications.NtfyProvider.send", mock_send),
        ):
            await check_wear_nudges(ctx)

        notifications = (
            await db_session.execute(
                select(Notification).where(Notification.user_id == nudge_user.id)
            )
        ).scalars().all()
        assert notifications == []

    @pytest.mark.asyncio
    async def test_skips_user_whose_nudge_time_has_not_passed_yet(
        self,
        db_session: AsyncSession,
        future_nudge_user: User,
        future_nudge_ntfy_channel: NotificationSettings,
    ):
        """future_nudge_user has wear_nudge_enabled and no outfit worn today -
        the only thing keeping them from being nudged is that their
        wear_nudge_time (set an hour ahead of "now") hasn't passed yet in
        their local time. If the `now_local.time() < pref.wear_nudge_time`
        gate in check_wear_nudges were ever inverted, this user would get
        nudged immediately and this assertion would fail."""
        ctx = {"redis": _FakeRedis()}
        mock_send = AsyncMock(return_value={"success": True})

        with (
            patch("app.workers.notifications.get_db_session", return_value=db_session),
            patch.object(db_session, "close", new_callable=AsyncMock),
            patch("app.workers.notifications.NtfyProvider.send", mock_send),
        ):
            await check_wear_nudges(ctx)

        # Shared users table across tests (see comment above) - scope to this
        # test's own user via its Notification rows.
        notifications = (
            await db_session.execute(
                select(Notification).where(
                    Notification.user_id == future_nudge_user.id,
                    Notification.payload["type"].astext == "wear_nudge",
                )
            )
        ).scalars().all()

        assert notifications == []


# ── check_auto_confirm ──


class TestCheckAutoConfirm:
    @pytest.mark.asyncio
    async def test_confirms_planned_outfit_for_today(
        self, db_session: AsyncSession, nudge_user: User
    ):
        """nudge_user's wear_nudge_time is comfortably in the past, so they're
        past their local end-of-day gate; a planned-but-unconfirmed outfit for
        today should get silently confirmed (worn_at set, item wear logged)."""
        from app.models.item import ItemStatus
        from app.models.outfit import Outfit, OutfitItem

        item = ClothingItem(
            id=uuid.uuid4(),
            user_id=nudge_user.id,
            image_path="/tmp/wardrobe_test/auto-confirm-shirt.jpg",
            type="shirt",
            status=ItemStatus.ready,
            wear_count=0,
        )
        outfit = Outfit(
            id=uuid.uuid4(),
            user_id=nudge_user.id,
            occasion="casual",
            scheduled_for=datetime.now(UTC).date(),
        )
        db_session.add_all([item, outfit])
        await db_session.commit()
        db_session.add(OutfitItem(outfit_id=outfit.id, item_id=item.id, position=0))
        await db_session.commit()

        ctx = {}

        with (
            patch("app.workers.notifications.get_db_session", return_value=db_session),
            patch.object(db_session, "close", new_callable=AsyncMock),
        ):
            await check_auto_confirm(ctx)

        await db_session.refresh(outfit)
        await db_session.refresh(item)
        assert outfit.worn_at == datetime.now(UTC).date()
        assert item.wear_count == 1

    @pytest.mark.asyncio
    async def test_skips_user_whose_nudge_time_has_not_passed_yet(
        self,
        db_session: AsyncSession,
        future_nudge_user: User,
    ):
        from app.models.item import ItemStatus
        from app.models.outfit import Outfit, OutfitItem

        item = ClothingItem(
            id=uuid.uuid4(),
            user_id=future_nudge_user.id,
            image_path="/tmp/wardrobe_test/future-auto-confirm-shirt.jpg",
            type="shirt",
            status=ItemStatus.ready,
            wear_count=0,
        )
        outfit = Outfit(
            id=uuid.uuid4(),
            user_id=future_nudge_user.id,
            occasion="casual",
            scheduled_for=datetime.now(UTC).date(),
        )
        db_session.add_all([item, outfit])
        await db_session.commit()
        db_session.add(OutfitItem(outfit_id=outfit.id, item_id=item.id, position=0))
        await db_session.commit()

        ctx = {}

        with (
            patch("app.workers.notifications.get_db_session", return_value=db_session),
            patch.object(db_session, "close", new_callable=AsyncMock),
        ):
            await check_auto_confirm(ctx)

        await db_session.refresh(outfit)
        assert outfit.worn_at is None


# ── check_wash_reminders ──


class TestCheckWashReminders:
    @pytest.mark.asyncio
    async def test_sends_wash_reminder_via_ntfy(
        self,
        db_session: AsyncSession,
        wash_user: User,
        wash_ntfy_channel: NotificationSettings,
        dirty_item: ClothingItem,
    ):
        """dirty_item (needs_wash=True, not archived) plus an enabled ntfy
        channel is exactly what makes wash_user due for a reminder. This
        exercises the NtfyNotification(...) construction in
        _check_wash_reminders_inner - the call previously omitted the
        required `topic` kwarg, which raised inside the per-channel try/except
        and was swallowed, silently downgrading the notification to
        status=failed/channel="unknown" instead of actually sending. Asserting
        status=sent and channel="ntfy" fails if that regresses."""
        mock_send = AsyncMock(return_value={"success": True})

        with (
            patch("app.workers.notifications.get_db_session", return_value=db_session),
            patch.object(db_session, "close", new_callable=AsyncMock),
            patch("app.workers.notifications.NtfyProvider.send", mock_send),
        ):
            await check_wash_reminders({})

        notifications = (
            await db_session.execute(
                select(Notification).where(
                    Notification.user_id == wash_user.id,
                    Notification.payload["type"].astext == "wash_reminder",
                )
            )
        ).scalars().all()

        assert len(notifications) == 1
        notification = notifications[0]
        assert notification.status == NotificationStatus.sent
        assert notification.channel == "ntfy"
        assert dirty_item.name in notification.payload["body"]


# ── Worker registry ──


class TestWorkerFunctionRegistry:
    def test_process_scheduled_notification_is_registered(self):
        func_names = [f.__name__ for f in WorkerSettings.functions]
        assert "process_scheduled_notification" in func_names

    def test_all_enqueued_functions_are_registered(self):
        func_names = {f.__name__ for f in WorkerSettings.functions}
        required = {
            "tag_item_image",
            "send_notification",
            "process_scheduled_notification",
            "retry_failed_notifications",
            "check_scheduled_notifications",
            "check_wash_reminders",
            "check_wear_nudges",
            "check_auto_confirm",
            "update_learning_profiles",
            "check_retag_backfill",
        }
        missing = required - func_names
        assert not missing, f"Functions enqueued but not registered in WorkerSettings: {missing}"
