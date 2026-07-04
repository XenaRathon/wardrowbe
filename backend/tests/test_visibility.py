from uuid import uuid4

import pytest
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
    # NOTE: created_by has a real FK to users.id (see app/models/family.py),
    # unlike the task brief's snippet which used a random uuid4(). Create the
    # owning user first, per the pattern in tests/test_pairings.py.
    a = await _mk_user(db_session)
    fam = Family(id=uuid4(), name="F", created_by=a.id, invite_code=str(uuid4())[:8])
    db_session.add(fam); await db_session.commit()
    a.family_id = fam.id
    await db_session.commit(); await db_session.refresh(a)
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
