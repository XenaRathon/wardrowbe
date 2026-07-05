# Outfit Calendar + Closet Sharing — Backend Implementation Plan (Plan 1 of 2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the backend API for a household-aware, two-way outfit calendar (plan forward + log actual wear) with shared closets and assignable item ownership, reusing Wardrowbe's existing wear-logging and analytics.

**Architecture:** Additive schema only (`ClothingItem.is_private`, `ItemHistory.worn_by_user_id`, `Outfit.worn_at`). A day's record is derived from `Outfit` rows (`scheduled_for` = planned, `worn_at` = confirmed) plus `ItemHistory` extras. All item access flows through one family-visibility helper. Confirming/logging a wear funnels through the existing `ItemService.log_wear` so `wear_count`, `last_worn_at`, wash tracking, and `/analytics` update for free.

**Tech Stack:** Python 3.11, FastAPI (`/api/v1`), SQLAlchemy 2 async + asyncpg, Alembic, Pydantic v2, pytest + pytest-asyncio (real Postgres `wardrobe_test`).

## Global Constraints

- Python target 3.11; SQLAlchemy 2 async style (`Mapped[...]`, `mapped_column`).
- Every endpoint is under `/api/v1` (router included in `app/api/router.py`).
- Auth: `current_user: Annotated[User, Depends(get_current_user)]` (from `app.utils.auth`); DB: `Annotated[AsyncSession, Depends(get_db)]` (from `app.database`).
- Dates use the user's timezone via `get_user_today(user)` from `app.utils.timezone`.
- Wear logging MUST go through `ItemService.log_wear(...)` — the single source of truth that writes exactly one `ItemHistory` row and updates item + wash stats. Never bulk-update `wear_count` directly.
- Migrations are additive/forward-only; all new columns nullable or defaulted (no backfill).
- Tests use existing conftest fixtures: `db_session`, `client`, `test_user`, `auth_headers`, `sample_item_data`, `sample_tags`. Create additional users inline like `test_user` (via `User(external_id=..., email=..., ...)`).
- Reuse `UserPreference.avoid_repeat_days` (existing, default 7) for "don't-repeat" — do NOT add a new field.
- Commit after every task with a `feat:`/`test:`/`refactor:` message.
- Run backend tests from `backend/`: `python -m pytest <path> -v`.

---

## File Structure

- `backend/app/models/item.py` — add `is_private` (ClothingItem) + `worn_by_user_id` (ItemHistory).
- `backend/app/models/outfit.py` — add `worn_at`.
- `backend/app/models/preference.py` — add `wear_nudge_enabled`, `wear_nudge_time`.
- `backend/alembic/versions/<rev>_calendar_sharing.py` — one additive migration.
- `backend/app/services/family_service.py` — add `get_member_ids`.
- `backend/app/utils/visibility.py` (new) — `usable_items_filter(...)` shared query helper.
- `backend/app/services/item_service.py` — `log_wear` gains `worn_by_user_id`; `create`/`update` honor owner + `is_private`.
- `backend/app/schemas/item.py` — `owner_user_id`, `is_private` on create/update schemas.
- `backend/app/api/items.py` — pass owner/is_private through.
- `backend/app/api/outfits.py` — unify the feedback `worn` path onto `log_wear`.
- `backend/app/services/recommendation_service.py` + `pairing_service.py` — candidate pools use `usable_items_filter`.
- `backend/app/services/calendar_service.py` (new) — day-record assembly + plan/confirm/log/don't-repeat.
- `backend/app/schemas/calendar.py` (new) — calendar request/response models.
- `backend/app/api/calendar.py` (new) — calendar endpoints.
- `backend/app/api/router.py` — register calendar router.
- `backend/app/workers/notifications.py` — evening wear-nudge job.
- `backend/tests/test_visibility.py`, `test_calendar.py`, `test_item_owner_sharing.py`, `test_log_wear_attribution.py` (new).

---

## Task 1: Additive schema + migration

**Files:**
- Modify: `backend/app/models/item.py` (ClothingItem + ItemHistory)
- Modify: `backend/app/models/outfit.py` (Outfit)
- Modify: `backend/app/models/preference.py` (UserPreference)
- Create: `backend/alembic/versions/<rev>_calendar_sharing.py`
- Test: `backend/tests/test_calendar_migration.py`

**Interfaces:**
- Produces: `ClothingItem.is_private: bool`, `ItemHistory.worn_by_user_id: UUID | None`, `Outfit.worn_at: date | None`, `UserPreference.wear_nudge_enabled: bool`, `UserPreference.wear_nudge_time: time`.

- [ ] **Step 1: Add model columns**

In `backend/app/models/item.py`, in `ClothingItem` (near `status`/`ai_processed`):
```python
    is_private: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
```
In `ItemHistory` (after `outfit_id`):
```python
    worn_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
```
In `backend/app/models/outfit.py`, in `Outfit` (after `scheduled_for`):
```python
    worn_at: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
```
In `backend/app/models/preference.py`, in `UserPreference` (after `avoid_repeat_days`):
```python
    wear_nudge_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    wear_nudge_time: Mapped[time] = mapped_column(Time, default=time(20, 0), server_default="20:00", nullable=False)
```
Add imports where missing: `from datetime import date, time` and `from sqlalchemy import Boolean, Date, ForeignKey, Time` (merge into existing import lines).

- [ ] **Step 2: Generate the migration**

Run from `backend/`:
```bash
python -m alembic revision --autogenerate -m "calendar_sharing: is_private, worn_by_user_id, outfit.worn_at, wear_nudge"
```
Open the generated file and verify it contains `add_column` for each of the five columns plus the `worn_at` index, and no unrelated drops. If autogenerate misses `server_default`, the columns are still safe (nullable/defaulted).

- [ ] **Step 3: Write the failing test**

Create `backend/tests/test_calendar_migration.py`:
```python
import pytest
from sqlalchemy import inspect, text


@pytest.mark.asyncio
async def test_new_columns_exist(db_session):
    rows = (await db_session.execute(text(
        "SELECT table_name, column_name FROM information_schema.columns "
        "WHERE (table_name='clothing_items' AND column_name='is_private') "
        "OR (table_name='item_history' AND column_name='worn_by_user_id') "
        "OR (table_name='outfits' AND column_name='worn_at') "
        "OR (table_name='user_preferences' AND column_name IN ('wear_nudge_enabled','wear_nudge_time'))"
    ))).all()
    found = {(t, c) for t, c in rows}
    assert ("clothing_items", "is_private") in found
    assert ("item_history", "worn_by_user_id") in found
    assert ("outfits", "worn_at") in found
    assert ("user_preferences", "wear_nudge_enabled") in found
    assert ("user_preferences", "wear_nudge_time") in found
```

- [ ] **Step 4: Run — expect FAIL then apply migration**

Run: `python -m pytest tests/test_calendar_migration.py -v`
Expected: FAIL (columns missing) if the test DB predates the migration. The conftest runs `alembic upgrade head` when creating `wardrobe_test`; if the DB already exists, drop it once: `psql "$TEST_DATABASE_URL" -c 'DROP DATABASE wardrobe_test'` is not possible while connected — instead run `python -m alembic upgrade head` against the test DB, or let a fresh CI DB apply it. Re-run.

- [ ] **Step 5: Run — expect PASS**

Run: `python -m pytest tests/test_calendar_migration.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**
```bash
git add backend/app/models backend/alembic/versions backend/tests/test_calendar_migration.py
git commit -m "feat(model): add is_private, worn_by_user_id, outfit.worn_at, wear-nudge prefs + migration"
```

---

## Task 2: Family visibility helper

**Files:**
- Modify: `backend/app/services/family_service.py` (add `get_member_ids`)
- Create: `backend/app/utils/visibility.py`
- Test: `backend/tests/test_visibility.py`

**Interfaces:**
- Consumes: `FamilyService(db)`, `User.family_id`.
- Produces:
  - `FamilyService.get_member_ids(self, user: User) -> list[UUID]` — returns `[user.id]` if no family, else all user ids sharing `user.family_id` (including the user).
  - `usable_items_filter(user: User, member_ids: list[UUID])` in `app/utils/visibility.py` — returns a SQLAlchemy boolean clause for `ClothingItem`: owned by a member AND (not private OR owned by `user`).

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_visibility.py`:
```python
import pytest
from uuid import uuid4
from sqlalchemy import select

from app.models.family import Family
from app.models.item import ClothingItem, ItemStatus
from app.models.user import User
from app.services.family_service import FamilyService
from app.utils.visibility import usable_items_filter


async def _mk_user(db, family_id=None):
    u = User(id=uuid4(), external_id=f"ext-{uuid4()}", email=f"{uuid4()}@e.com",
             display_name="U", timezone="UTC", is_active=True, onboarding_completed=True,
             family_id=family_id)
    db.add(u); await db.commit(); await db.refresh(u); return u


async def _mk_item(db, owner, is_private=False):
    it = ClothingItem(id=uuid4(), user_id=owner.id, image_path="x.jpg", type="shirt",
                      status=ItemStatus.ready, is_private=is_private)
    db.add(it); await db.commit(); await db.refresh(it); return it


@pytest.mark.asyncio
async def test_member_ids_no_family_returns_self(db_session):
    u = await _mk_user(db_session)
    ids = await FamilyService(db_session).get_member_ids(u)
    assert ids == [u.id]


@pytest.mark.asyncio
async def test_visibility_shares_family_hides_private(db_session):
    fam = Family(id=uuid4(), name="F", created_by=uuid4(), invite_code=str(uuid4())[:8])
    db_session.add(fam); await db_session.commit()
    a = await _mk_user(db_session, fam.id)
    b = await _mk_user(db_session, fam.id)
    shared = await _mk_item(db_session, b, is_private=False)
    hidden = await _mk_item(db_session, b, is_private=True)
    fs = FamilyService(db_session)
    ids = await fs.get_member_ids(a)
    assert set(ids) == {a.id, b.id}
    visible = (await db_session.execute(
        select(ClothingItem.id).where(usable_items_filter(a, ids))
    )).scalars().all()
    assert shared.id in visible
    assert hidden.id not in visible  # b's private item hidden from a
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_visibility.py -v`
Expected: FAIL (`ImportError: usable_items_filter` / `get_member_ids` missing).

- [ ] **Step 3: Implement**

Add to `backend/app/services/family_service.py` (inside `FamilyService`):
```python
    async def get_member_ids(self, user: User) -> list[UUID]:
        if user.family_id is None:
            return [user.id]
        result = await self.db.execute(
            select(User.id).where(User.family_id == user.family_id)
        )
        ids = list(result.scalars().all())
        return ids if user.id in ids else [*ids, user.id]
```
Ensure `from uuid import UUID` and `from sqlalchemy import select` and `from app.models.user import User` are imported.

Create `backend/app/utils/visibility.py`:
```python
from uuid import UUID

from sqlalchemy import and_, or_

from app.models.item import ClothingItem
from app.models.user import User


def usable_items_filter(user: User, member_ids: list[UUID]):
    """Boolean clause: items owned by a family member that `user` may use —
    shared items from anyone, plus the user's own private items."""
    return and_(
        ClothingItem.user_id.in_(member_ids),
        or_(ClothingItem.is_private.is_(False), ClothingItem.user_id == user.id),
    )
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_visibility.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add backend/app/services/family_service.py backend/app/utils/visibility.py backend/tests/test_visibility.py
git commit -m "feat(sharing): family member-ids + usable_items visibility filter"
```

---

## Task 3: Assignable owner + is_private on item create/update

**Files:**
- Modify: `backend/app/schemas/item.py` (create + update schemas)
- Modify: `backend/app/services/item_service.py` (`create`, `update`)
- Modify: `backend/app/api/items.py` (pass owner through; validate family)
- Test: `backend/tests/test_item_owner_sharing.py`

**Interfaces:**
- Consumes: `FamilyService.get_member_ids`, `ItemUpdate` schema.
- Produces: item create accepts optional `owner_user_id: UUID`; `ItemUpdate` accepts `user_id: UUID | None` and `is_private: bool | None`. Owner must be in `get_member_ids(current_user)` or a 400 is raised.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_item_owner_sharing.py`:
```python
import pytest
from uuid import uuid4
from app.models.family import Family
from app.models.user import User


async def _user(db, fam=None):
    u = User(id=uuid4(), external_id=f"ext-{uuid4()}", email=f"{uuid4()}@e.com",
             display_name="U", timezone="UTC", is_active=True, onboarding_completed=True,
             family_id=fam)
    db.add(u); await db.commit(); await db.refresh(u); return u


@pytest.mark.asyncio
async def test_assign_owner_to_family_member(db_session, client):
    from app.api.auth import create_access_token
    fam = Family(id=uuid4(), name="F", created_by=uuid4(), invite_code=str(uuid4())[:8])
    db_session.add(fam); await db_session.commit()
    me = await _user(db_session, fam.id)
    her = await _user(db_session, fam.id)
    headers = {"Authorization": f"Bearer {create_access_token(me.external_id)}"}
    # create item on her behalf
    r = await client.post("/api/v1/items", headers=headers,
                          json={"type": "jacket", "owner_user_id": str(her.id)})
    assert r.status_code in (200, 201), r.text
    assert r.json()["user_id"] == str(her.id)


@pytest.mark.asyncio
async def test_assign_owner_outside_family_rejected(db_session, client):
    from app.api.auth import create_access_token
    me = await _user(db_session)          # no family
    stranger = await _user(db_session)    # different, no family
    headers = {"Authorization": f"Bearer {create_access_token(me.external_id)}"}
    r = await client.post("/api/v1/items", headers=headers,
                          json={"type": "jacket", "owner_user_id": str(stranger.id)})
    assert r.status_code == 400
```
*(Note: adapt the create route/path and required fields to match `app/api/items.py`; if item creation requires an image upload, use the service-layer `ItemService.create` directly in the test instead of the HTTP route, asserting `item.user_id == her.id` and that a non-family owner raises `ValueError`/`HTTPException`.)*

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_item_owner_sharing.py -v`
Expected: FAIL (owner not honored / not validated).

- [ ] **Step 3: Implement**

In `backend/app/schemas/item.py`: add to the item-create schema `owner_user_id: UUID | None = None`; add to `ItemUpdate` `user_id: UUID | None = None` and `is_private: bool | None = None`.

In `backend/app/services/item_service.py` `create(...)`: accept `owner_user_id: UUID | None = None`; set the new item's `user_id = owner_user_id or creator.id`. In the calling code (`app/api/items.py`), before create/update, validate:
```python
from app.services.family_service import FamilyService

if owner_user_id is not None:
    member_ids = await FamilyService(db).get_member_ids(current_user)
    if owner_user_id not in member_ids:
        raise HTTPException(status_code=400, detail="Owner must be a family member")
```
In `ItemService.update(...)`: if `item_data.user_id` is set, apply the same family validation and reassign `item.user_id`; if `item_data.is_private` is set, apply it.

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_item_owner_sharing.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add backend/app/schemas/item.py backend/app/services/item_service.py backend/app/api/items.py backend/tests/test_item_owner_sharing.py
git commit -m "feat(sharing): assignable item owner + is_private, family-validated"
```

---

## Task 4: `log_wear` gains `worn_by_user_id` + unify the feedback wear path

**Files:**
- Modify: `backend/app/services/item_service.py` (`log_wear` signature)
- Modify: `backend/app/api/outfits.py` (feedback `worn` path → `log_wear`)
- Test: `backend/tests/test_log_wear_attribution.py`

**Interfaces:**
- Consumes: existing `ItemService.log_wear`.
- Produces: `ItemService.log_wear(self, item, worn_at, occasion=None, notes=None, outfit_id=None, worn_by_user_id: UUID | None = None) -> ItemHistory` — writes `ItemHistory.worn_by_user_id`. The outfit-feedback `worn=True` path calls `log_wear` once per item (idempotent per `(item_id, outfit_id, worn_at)`).

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_log_wear_attribution.py`:
```python
import pytest
from datetime import date
from uuid import uuid4
from sqlalchemy import select, func

from app.models.item import ClothingItem, ItemHistory, ItemStatus
from app.models.user import User
from app.services.item_service import ItemService


async def _user(db):
    u = User(id=uuid4(), external_id=f"ext-{uuid4()}", email=f"{uuid4()}@e.com",
             display_name="U", timezone="UTC", is_active=True, onboarding_completed=True)
    db.add(u); await db.commit(); await db.refresh(u); return u


@pytest.mark.asyncio
async def test_log_wear_records_wearer_and_increments_once(db_session):
    owner = await _user(db_session)
    wearer = await _user(db_session)
    item = ClothingItem(id=uuid4(), user_id=owner.id, image_path="x.jpg", type="jacket",
                        status=ItemStatus.ready, wear_count=0)
    db_session.add(item); await db_session.commit(); await db_session.refresh(item)

    svc = ItemService(db_session)
    hist = await svc.log_wear(item, worn_at=date(2026, 7, 4), worn_by_user_id=wearer.id)
    await db_session.refresh(item)

    assert hist.worn_by_user_id == wearer.id
    assert item.wear_count == 1
    count = (await db_session.execute(
        select(func.count()).select_from(ItemHistory).where(ItemHistory.item_id == item.id)
    )).scalar()
    assert count == 1
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_log_wear_attribution.py -v`
Expected: FAIL (`log_wear() got unexpected keyword 'worn_by_user_id'`).

- [ ] **Step 3: Implement**

In `ItemService.log_wear`, add the param and set it on the history row:
```python
    async def log_wear(
        self,
        item: ClothingItem,
        worn_at: date,
        occasion: str | None = None,
        notes: str | None = None,
        outfit_id: UUID | None = None,
        worn_by_user_id: UUID | None = None,
    ) -> ItemHistory:
        history = ItemHistory(
            item_id=item.id,
            outfit_id=outfit_id,
            worn_at=worn_at,
            occasion=occasion,
            notes=notes,
            worn_by_user_id=worn_by_user_id,
        )
        self.db.add(history)
        item.wear_count += 1
        item.last_worn_at = worn_at
        # ... keep existing wash-tracking block unchanged ...
```
In `backend/app/api/outfits.py`, replace the inline bulk `update(ClothingItem)...wear_count+1` block in the feedback `worn` path with, for each `outfit_item`:
```python
    already = await db.execute(
        select(ItemHistory.id).where(
            ItemHistory.item_id == outfit_item.item_id,
            ItemHistory.outfit_id == outfit.id,
            ItemHistory.worn_at == user_today,
        )
    )
    if already.scalar_one_or_none() is None:
        await ItemService(db).log_wear(
            outfit_item.item, worn_at=user_today, outfit_id=outfit.id,
            worn_by_user_id=current_user.id, occasion=outfit.occasion,
        )
```
Import `ItemHistory` and `ItemService` in `outfits.py` if not present.

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_log_wear_attribution.py tests/test_pairings.py tests/test_studio_service.py -v`
Expected: PASS (attribution test passes; existing outfit tests still green).

- [ ] **Step 5: Commit**
```bash
git add backend/app/services/item_service.py backend/app/api/outfits.py backend/tests/test_log_wear_attribution.py
git commit -m "feat(wear): record worn_by + unify outfit-feedback onto log_wear (idempotent)"
```

---

## Task 5: Shared candidate pool in recommendation & pairing

**Files:**
- Modify: `backend/app/services/recommendation_service.py` (candidate query)
- Modify: `backend/app/services/pairing_service.py` (`get_available_items`)
- Test: extend `backend/tests/test_recommendation_service.py`

**Interfaces:**
- Consumes: `usable_items_filter`, `FamilyService.get_member_ids`.
- Produces: outfit recommendation + pairing candidate pools include family-shared items (respecting `is_private`), replacing any `ClothingItem.user_id == user.id`-only filter.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_recommendation_service.py`:
```python
@pytest.mark.asyncio
async def test_candidate_pool_includes_shared_family_items(db_session):
    from uuid import uuid4
    from app.models.family import Family
    from app.models.item import ClothingItem, ItemStatus
    from app.models.user import User
    from app.services.pairing_service import PairingService

    fam = Family(id=uuid4(), name="F", created_by=uuid4(), invite_code=str(uuid4())[:8])
    db_session.add(fam); await db_session.commit()
    me = User(id=uuid4(), external_id=f"e{uuid4()}", email=f"{uuid4()}@e.com", display_name="M",
              timezone="UTC", is_active=True, onboarding_completed=True, family_id=fam.id)
    her = User(id=uuid4(), external_id=f"e{uuid4()}", email=f"{uuid4()}@e.com", display_name="H",
               timezone="UTC", is_active=True, onboarding_completed=True, family_id=fam.id)
    db_session.add_all([me, her]); await db_session.commit()
    hers = ClothingItem(id=uuid4(), user_id=her.id, image_path="x.jpg", type="jacket",
                        status=ItemStatus.ready, is_private=False)
    db_session.add(hers); await db_session.commit()

    items = await PairingService(db_session).get_available_items(me, exclude_item_id=uuid4())
    assert any(i.id == hers.id for i in items)
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_recommendation_service.py::test_candidate_pool_includes_shared_family_items -v`
Expected: FAIL (her item not in `me`'s pool).

- [ ] **Step 3: Implement**

In `pairing_service.get_available_items` and the equivalent candidate query in `recommendation_service`, replace `ClothingItem.user_id == user.id` with the visibility filter:
```python
from app.services.family_service import FamilyService
from app.utils.visibility import usable_items_filter

member_ids = await FamilyService(self.db).get_member_ids(user)
# ... in the select().where(...):
#   was: ClothingItem.user_id == user.id
#   now: usable_items_filter(user, member_ids)
```
Keep the existing `status == ready`, `is_archived == False`, and INTIMATE_TYPES exclusions.

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_recommendation_service.py tests/test_pairings.py -v`
Expected: PASS (shared item present; existing tests green).

- [ ] **Step 5: Commit**
```bash
git add backend/app/services/recommendation_service.py backend/app/services/pairing_service.py backend/tests/test_recommendation_service.py
git commit -m "feat(sharing): recommendation + pairing draw from shared family pool"
```

---

## Task 6: CalendarService + `GET /calendar` day records

**Files:**
- Create: `backend/app/services/calendar_service.py`
- Create: `backend/app/schemas/calendar.py`
- Create: `backend/app/api/calendar.py`
- Modify: `backend/app/api/router.py` (register router)
- Test: `backend/tests/test_calendar.py`

**Interfaces:**
- Consumes: `Outfit` (`scheduled_for`, `worn_at`, `items`), `get_user_today`.
- Produces:
  - `CalendarService(db).get_range(user, start: date, end: date) -> list[DayRecord]` where `DayRecord = {date, primary: OutfitBrief | None, extras: list[OutfitBrief]}`.
  - `GET /api/v1/calendar?start=YYYY-MM-DD&end=YYYY-MM-DD` → `list[DayRecordOut]`.
- Primary-selection rule: for a date, primary = the outfit with `worn_at == date` and `scheduled_for == date` (confirmed plan) → else `scheduled_for == date` (plan) → else earliest `worn_at == date`. Remaining `worn_at == date` outfits are `extras`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_calendar.py`:
```python
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_calendar.py -v`
Expected: FAIL (`calendar_service` missing).

- [ ] **Step 3: Implement**

Create `backend/app/services/calendar_service.py`:
```python
from datetime import date
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.outfit import Outfit, OutfitItem
from app.models.user import User


def _brief(o: Outfit) -> dict:
    return {"id": o.id, "occasion": o.occasion, "scheduled_for": o.scheduled_for,
            "worn_at": o.worn_at, "name": o.name,
            "item_ids": [oi.item_id for oi in o.items]}


class CalendarService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_range(self, user: User, start: date, end: date) -> list[dict]:
        result = await self.db.execute(
            select(Outfit)
            .where(
                Outfit.user_id == user.id,
                or_(
                    Outfit.scheduled_for.between(start, end),
                    Outfit.worn_at.between(start, end),
                ),
            )
            .options(selectinload(Outfit.items))
            .order_by(Outfit.created_at.asc())
        )
        outfits = list(result.scalars().all())
        by_day: dict[date, list[Outfit]] = {}
        for o in outfits:
            for d in {o.scheduled_for, o.worn_at}:
                if d and start <= d <= end:
                    by_day.setdefault(d, []).append(o)

        records = []
        for d in sorted(by_day):
            todays = by_day[d]
            confirmed = [o for o in todays if o.worn_at == d and o.scheduled_for == d]
            planned = [o for o in todays if o.scheduled_for == d]
            worn = [o for o in todays if o.worn_at == d]
            primary = (confirmed or planned or worn or [None])[0]
            extras = [o for o in worn if primary is None or o.id != primary.id]
            records.append({
                "date": d,
                "primary": _brief(primary) if primary else None,
                "extras": [_brief(o) for o in extras],
            })
        return records
```
Create `backend/app/schemas/calendar.py`:
```python
from datetime import date
from uuid import UUID
from pydantic import BaseModel


class OutfitBrief(BaseModel):
    id: UUID
    occasion: str
    scheduled_for: date | None = None
    worn_at: date | None = None
    name: str | None = None
    item_ids: list[UUID] = []


class DayRecordOut(BaseModel):
    date: date
    primary: OutfitBrief | None = None
    extras: list[OutfitBrief] = []
```
Create `backend/app/api/calendar.py`:
```python
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.calendar import DayRecordOut
from app.services.calendar_service import CalendarService
from app.utils.auth import get_current_user

router = APIRouter(prefix="/calendar", tags=["Calendar"])


@router.get("", response_model=list[DayRecordOut])
async def get_calendar(
    start: Annotated[date, Query()],
    end: Annotated[date, Query()],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await CalendarService(db).get_range(current_user, start, end)
```
Register in `backend/app/api/router.py` following the existing pattern:
```python
from app.api import calendar
api_router.include_router(calendar.router)
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_calendar.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add backend/app/services/calendar_service.py backend/app/schemas/calendar.py backend/app/api/calendar.py backend/app/api/router.py backend/tests/test_calendar.py
git commit -m "feat(calendar): CalendarService + GET /calendar day records"
```

---

## Task 7: Plan / confirm / log / delete endpoints

**Files:**
- Modify: `backend/app/services/calendar_service.py` (mutations)
- Modify: `backend/app/schemas/calendar.py` (request bodies)
- Modify: `backend/app/api/calendar.py` (endpoints)
- Test: extend `backend/tests/test_calendar.py`

**Interfaces:**
- Consumes: `ItemService.log_wear` (with `worn_by_user_id`), `FamilyService.get_member_ids`.
- Produces:
  - `CalendarService.set_plan(user, d, outfit_id) -> Outfit` — sets that outfit's `scheduled_for = d`, clears any other plan for the day.
  - `CalendarService.confirm(user, d) -> DayRecord` — sets planned outfit's `worn_at = d` and calls `log_wear` per item (`worn_by_user_id = user.id`), idempotent.
  - `CalendarService.log_wear_outfit(user, d, outfit_id, worn_by_user_id, occasion) -> Outfit` — sets `worn_at = d` on a (possibly unplanned) outfit and logs items.
  - `CalendarService.remove_wear(user, d, outfit_id)` — clears `worn_at`, deletes that day's `ItemHistory` for the outfit, decrements `wear_count`.
  - Endpoints: `POST /calendar/{d}/plan`, `POST /calendar/{d}/confirm`, `POST /calendar/{d}/wear`, `DELETE /calendar/{d}/wear/{outfit_id}`.

- [ ] **Step 1: Write the failing test**
```python
@pytest.mark.asyncio
async def test_confirm_logs_items(db_session):
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_calendar.py::test_confirm_logs_items -v`
Expected: FAIL (`confirm` missing).

- [ ] **Step 3: Implement**

Add to `CalendarService`:
```python
    from app.models.item import ItemHistory  # top-of-file import
    from app.models.outfit import OutfitItem
    from app.services.item_service import ItemService
    from app.utils.timezone import get_user_today

    async def set_plan(self, user, d, outfit_id):
        outfit = await self._owned_outfit(user, outfit_id)
        # clear other plans for the day
        for o in await self._day_outfits(user, d):
            if o.id != outfit.id and o.scheduled_for == d:
                o.scheduled_for = None
        outfit.scheduled_for = d
        await self.db.flush()
        return outfit

    async def confirm(self, user, d):
        planned = next((o for o in await self._day_outfits(user, d) if o.scheduled_for == d), None)
        if planned is None:
            raise ValueError("No planned outfit for this date")
        await self._log_outfit(user, planned, d, worn_by_user_id=user.id)
        return (await self.get_range(user, d, d))[0]

    async def log_wear_outfit(self, user, d, outfit_id, worn_by_user_id, occasion=None):
        outfit = await self._owned_outfit(user, outfit_id)
        await self._log_outfit(user, outfit, d, worn_by_user_id=worn_by_user_id, occasion=occasion)
        return outfit

    async def remove_wear(self, user, d, outfit_id):
        from sqlalchemy import delete, select
        outfit = await self._owned_outfit(user, outfit_id)
        hist = (await self.db.execute(
            select(ItemHistory).where(ItemHistory.outfit_id == outfit.id, ItemHistory.worn_at == d)
        )).scalars().all()
        for h in hist:
            item = await ItemService(self.db).get_by_id(h.item_id, h.item.user_id if h.item else outfit.user_id)
            if item and item.wear_count > 0:
                item.wear_count -= 1
            await self.db.delete(h)
        outfit.worn_at = None
        await self.db.flush()

    async def _log_outfit(self, user, outfit, d, *, worn_by_user_id, occasion=None):
        from sqlalchemy import select
        existing = (await self.db.execute(
            select(ItemHistory.item_id).where(ItemHistory.outfit_id == outfit.id, ItemHistory.worn_at == d)
        )).scalars().all()
        already = set(existing)
        svc = ItemService(self.db)
        for oi in outfit.items:
            if oi.item_id in already:
                continue
            await svc.log_wear(oi.item, worn_at=d, outfit_id=outfit.id,
                               worn_by_user_id=worn_by_user_id, occasion=occasion or outfit.occasion)
        outfit.worn_at = d
        await self.db.flush()

    async def _owned_outfit(self, user, outfit_id):
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        o = (await self.db.execute(
            select(Outfit).where(Outfit.id == outfit_id, Outfit.user_id == user.id)
            .options(selectinload(Outfit.items).selectinload(OutfitItem.item))
        )).scalar_one_or_none()
        if o is None:
            raise ValueError("Outfit not found")
        return o

    async def _day_outfits(self, user, d):
        from sqlalchemy import or_, select
        from sqlalchemy.orm import selectinload
        return list((await self.db.execute(
            select(Outfit).where(Outfit.user_id == user.id,
                                 or_(Outfit.scheduled_for == d, Outfit.worn_at == d))
            .options(selectinload(Outfit.items).selectinload(OutfitItem.item))
        )).scalars().all())
```
Add request schemas to `schemas/calendar.py`:
```python
class PlanRequest(BaseModel):
    outfit_id: UUID

class WearRequest(BaseModel):
    outfit_id: UUID
    worn_by_user_id: UUID | None = None
    occasion: str | None = None
```
Add endpoints to `api/calendar.py` (map `ValueError` → 404/400):
```python
@router.post("/{d}/plan", response_model=DayRecordOut)
async def plan_day(d: date, body: PlanRequest, current_user=..., db=...):
    svc = CalendarService(db)
    try:
        await svc.set_plan(current_user, d, body.outfit_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return (await svc.get_range(current_user, d, d))[0]

@router.post("/{d}/confirm", response_model=DayRecordOut)
async def confirm_day(d: date, current_user=..., db=...):
    try:
        return await CalendarService(db).confirm(current_user, d)
    except ValueError as e:
        raise HTTPException(400, str(e))

@router.post("/{d}/wear", response_model=DayRecordOut)
async def wear_day(d: date, body: WearRequest, current_user=..., db=...):
    svc = CalendarService(db)
    wearer = body.worn_by_user_id or current_user.id
    try:
        await svc.log_wear_outfit(current_user, d, body.outfit_id, wearer, body.occasion)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return (await svc.get_range(current_user, d, d))[0]

@router.delete("/{d}/wear/{outfit_id}", response_model=DayRecordOut)
async def remove_wear(d: date, outfit_id: UUID, current_user=..., db=...):
    svc = CalendarService(db)
    try:
        await svc.remove_wear(current_user, d, outfit_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return (await svc.get_range(current_user, d, d))[0]
```
Fill the `current_user=...`, `db=...` params with the same `Annotated[...]` dependency form as `get_calendar`. Import `HTTPException`, `UUID`, `PlanRequest`, `WearRequest`.

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_calendar.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add backend/app/services/calendar_service.py backend/app/schemas/calendar.py backend/app/api/calendar.py backend/tests/test_calendar.py
git commit -m "feat(calendar): plan/confirm/wear/remove endpoints with idempotent cascade"
```

---

## Task 8: "Don't repeat within N days" warnings

**Files:**
- Modify: `backend/app/services/calendar_service.py` (`recently_worn`)
- Modify: `backend/app/schemas/calendar.py` (`DayRecordOut.repeat_warnings`)
- Test: extend `backend/tests/test_calendar.py`

**Interfaces:**
- Consumes: `UserPreference.avoid_repeat_days` (existing, default 7), `ItemHistory.worn_at`.
- Produces: `CalendarService.recently_worn(user, item_ids, on_date) -> list[UUID]` — item ids worn within `avoid_repeat_days` before `on_date`, excluding `shoes` + accessory-slot types (`jewelry, watch, belt, bag, sunglasses, hat, scarf, tie, gloves`). Surfaced as `DayRecordOut.repeat_warnings: list[UUID]` on the plan's primary.

- [ ] **Step 1: Write the failing test**
```python
@pytest.mark.asyncio
async def test_recently_worn_flags_within_window(db_session):
    from datetime import date, timedelta
    from uuid import uuid4
    from app.models.item import ClothingItem, ItemStatus, ItemHistory
    from app.models.preference import UserPreference
    from app.services.calendar_service import CalendarService

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
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_calendar.py::test_recently_worn_flags_within_window -v`
Expected: FAIL (`recently_worn` missing).

- [ ] **Step 3: Implement**

Add to `CalendarService`:
```python
    _REPEAT_EXCLUDE = {"shoes", "sneakers", "boots", "sandals", "jewelry", "watch",
                       "belt", "bag", "sunglasses", "hat", "scarf", "tie", "gloves"}

    async def recently_worn(self, user, item_ids, on_date):
        from datetime import timedelta
        from sqlalchemy import select
        from app.models.item import ClothingItem, ItemHistory
        from app.models.preference import UserPreference

        pref = (await self.db.execute(
            select(UserPreference).where(UserPreference.user_id == user.id)
        )).scalar_one_or_none()
        window = (pref.avoid_repeat_days if pref else 7)
        since = on_date - timedelta(days=window)
        rows = (await self.db.execute(
            select(ItemHistory.item_id, ClothingItem.type)
            .join(ClothingItem, ClothingItem.id == ItemHistory.item_id)
            .where(ItemHistory.item_id.in_(item_ids),
                   ItemHistory.worn_at >= since, ItemHistory.worn_at < on_date)
        )).all()
        return [iid for iid, itype in rows if (itype or "").lower() not in self._REPEAT_EXCLUDE]
```
In `get_range`, for each record with a `primary`, add `record["repeat_warnings"] = await self.recently_worn(user, primary_item_ids, d)`. Add `repeat_warnings: list[UUID] = []` to `DayRecordOut`.

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_calendar.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add backend/app/services/calendar_service.py backend/app/schemas/calendar.py backend/tests/test_calendar.py
git commit -m "feat(calendar): don't-repeat-within-N-days warnings (reuses avoid_repeat_days)"
```

---

## Task 9: Evening wear-nudge worker job

**Files:**
- Modify: `backend/app/workers/notifications.py` (nudge job)
- Test: `backend/tests/test_notification_workers.py` (extend)

**Interfaces:**
- Consumes: `UserPreference.wear_nudge_enabled`, `wear_nudge_time`, existing `NotificationDispatcher`, `get_user_today`.
- Produces: `check_wear_nudges(ctx)` worker — for each user with `wear_nudge_enabled` whose local time has passed `wear_nudge_time` today and who has **no** outfit with `worn_at == today`, send one "What did you wear today?" notification (dedup so it fires at most once per user per day).

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_notification_workers.py` a test that: creates a user with `wear_nudge_enabled=True`, no `worn_at==today` outfit, invokes `check_wear_nudges(ctx)` with a stubbed dispatcher, and asserts the dispatcher was asked to send exactly one nudge; then a second invocation same day sends zero (dedup). Follow the existing stubbing pattern already used in `test_notification_workers.py` (inspect it for how `ctx`, redis, and the dispatcher are faked).

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_notification_workers.py -k wear_nudge -v`
Expected: FAIL (`check_wear_nudges` missing).

- [ ] **Step 3: Implement**

Add `check_wear_nudges(ctx)` to `backend/app/workers/notifications.py`, mirroring the existing `check_scheduled_notifications` structure: query users with `wear_nudge_enabled`, compute each user's local `now`/`today` via their timezone, skip if before `wear_nudge_time` or if a `worn_at == today` outfit exists or if a per-day redis dedup key `wear_nudge:{user_id}:{today}` is set; otherwise send via `NotificationDispatcher` and set the dedup key with a 24h TTL. Register it on the worker's cron list next to the other `cron:check_*` functions.

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_notification_workers.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add backend/app/workers/notifications.py backend/tests/test_notification_workers.py
git commit -m "feat(calendar): evening wear-nudge worker on unlogged days (deduped)"
```

---

## Task 10: Silent end-of-day auto-confirm of planned outfits

**Files:**
- Modify: `backend/app/services/calendar_service.py` (`auto_confirm_due`)
- Modify: `backend/app/workers/notifications.py` (`check_auto_confirm` job + nudge skip-if-planned)
- Modify: `backend/app/workers/worker.py` (register cron)
- Test: `backend/tests/test_calendar.py` + `backend/tests/test_notification_workers.py`

**Interfaces:**
- Consumes: `CalendarService._log_outfit` / `_day_outfits` (Task 7), `UserPreference.wear_nudge_time`, `get_user_now`/`get_user_today`.
- Produces:
  - `CalendarService.auto_confirm_due(user, on_date) -> int` — confirms every outfit with `scheduled_for == on_date` AND `worn_at IS NULL` for `user` (sets `worn_at`, cascades `log_wear` with `worn_by_user_id = user.id`), idempotent; returns the count confirmed.
  - Worker `check_auto_confirm(ctx)` — for each user past their local `wear_nudge_time` today, calls `auto_confirm_due(user, local_today)`.
  - `check_wear_nudges` gains a skip: users who have a `scheduled_for == today` outfit are NOT nudged (planned days are auto-confirmed, never nudged), so ordering between the two cron jobs doesn't matter.

**Rationale:** The spec's daily loop = planned days auto-confirm silently; only unplanned days get the nudge. Task 9 built the nudge + manual confirm; this task adds the silent auto-confirm and makes the nudge planned-day-aware.

- [ ] **Step 1: Write the failing test (service)**

Add to `backend/tests/test_calendar.py` (reuse the file's `_user`/`_outfit`/`OutfitItem` helpers):
```python
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `bash backend/run-tests.sh tests/test_calendar.py::test_auto_confirm_due_confirms_planned -v`
Expected: FAIL (`auto_confirm_due` missing).

- [ ] **Step 3: Implement the service method**

Add to `CalendarService`:
```python
    async def auto_confirm_due(self, user, on_date) -> int:
        count = 0
        for o in await self._day_outfits(user, on_date):
            if o.scheduled_for == on_date and o.worn_at is None:
                await self._log_outfit(user, o, on_date, worn_by_user_id=user.id)
                count += 1
        return count
```

- [ ] **Step 4: Run to verify it passes**

Run: `bash backend/run-tests.sh tests/test_calendar.py::test_auto_confirm_due_confirms_planned -v`
Expected: PASS.

- [ ] **Step 5: Worker job + nudge skip-if-planned (TDD)**

Add to `backend/tests/test_notification_workers.py` (mirror the existing harness): a test that `check_auto_confirm(ctx)` confirms a user's planned-but-unconfirmed outfit for today (its `worn_at` becomes today, item wear logged); and a test that `check_wear_nudges` does NOT nudge a user who has a `scheduled_for == today` outfit. Run to confirm RED.

Then in `backend/app/workers/notifications.py`: add `check_auto_confirm(ctx)` mirroring `check_wear_nudges`'s per-user local-time gate (reuse `get_user_now`/`wear_nudge_time`), calling `CalendarService(db).auto_confirm_due(user, local_today)` per eligible user; and add to `check_wear_nudges` an early `continue` when the user has any `Outfit` with `scheduled_for == today` (query mirrors the existing `worn_at == today` check). Register `check_auto_confirm` on the cron list in `backend/app/workers/worker.py` next to `check_wear_nudges`.

- [ ] **Step 6: Run to verify it passes**

Run: `bash backend/run-tests.sh tests/test_calendar.py tests/test_notification_workers.py -v`
Expected: PASS. Then full suite: `bash backend/run-tests.sh -q`.

- [ ] **Step 7: Commit**
```bash
git add backend/app/services/calendar_service.py backend/app/workers/notifications.py backend/app/workers/worker.py backend/tests/test_calendar.py backend/tests/test_notification_workers.py
git commit -m "feat(calendar): silent end-of-day auto-confirm of planned outfits + nudge skips planned days"
```

---

## Final: full suite + push

- [ ] **Run the whole backend suite**

Run from `backend/`: `python -m pytest -q`
Expected: all green (new + existing).

- [ ] **Push (triggers CI image rebuild + then redeploy per project workflow)**
```bash
git push forgejo main
```
Then follow the project's deploy step (pull + recreate `wardrobe-backend`/`-worker`).

---

## Self-Review (author checklist — completed)

- **Spec coverage:** week/two-way calendar → Tasks 6–7; primary+extras → Task 6; auto-confirm → Task 7 (`confirm`) + Task 9 (nudge for unplanned); sharing all-by-default + is_private → Tasks 1–3, 5; assignable owner → Task 3; worn_by attribution → Task 4; shared AI pool → Task 5; don't-repeat → Task 8; unify wear paths → Task 4; migration → Task 1; analytics reuse → free via Task 4. **Frontend (week grid, day detail, owner selector, sharing filter, nudge deep-link) is Plan 2 of 2 — not in this plan.**
- **Placeholders:** none — the only prose-only step is Task 9 Step 1/3 (deliberately deferring to the existing `test_notification_workers.py` stub pattern rather than guessing the fake harness); every code step shows code.
- **Type consistency:** `log_wear(..., worn_by_user_id)`, `usable_items_filter(user, member_ids)`, `get_member_ids(user)`, `CalendarService.get_range/set_plan/confirm/log_wear_outfit/remove_wear/recently_worn`, `DayRecordOut{date, primary, extras, repeat_warnings}` used consistently across tasks.

## Out of scope for Plan 1
Laundry availability state machine; `price`/cost-per-wear; frontend (→ Plan 2); Body-Type Styler (→ spec #2).
