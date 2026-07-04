from uuid import uuid4

import pytest

from app.api.auth import create_access_token
from app.models.family import Family
from app.models.user import User
from app.schemas.item import ItemCreate
from app.services.item_service import ItemService


async def _user(db, fam=None) -> User:
    u = User(
        id=uuid4(),
        external_id=f"ext-{uuid4()}",
        email=f"{uuid4()}@e.com",
        display_name="U",
        timezone="UTC",
        is_active=True,
        onboarding_completed=True,
        family_id=fam,
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


async def _family(db, owner: User) -> Family:
    # created_by has a real FK to users.id, so the owning user must exist first.
    fam = Family(id=uuid4(), name="F", created_by=owner.id, invite_code=str(uuid4())[:8])
    db.add(fam)
    await db.commit()
    owner.family_id = fam.id
    await db.commit()
    await db.refresh(owner)
    return fam


class TestAssignOwnerOnCreate:
    """Item creation (POST /api/v1/items) is a multipart/Form + required-image route,
    so owner-assignment is exercised at the service layer directly, per the task brief."""

    @pytest.mark.asyncio
    async def test_assign_owner_to_family_member(self, db_session):
        me = await _user(db_session)
        fam = await _family(db_session, me)
        her = await _user(db_session, fam.id)

        item_service = ItemService(db_session)
        item = await item_service.create(
            user_id=me.id,
            item_data=ItemCreate(type="jacket"),
            image_paths={"image_path": f"test/{uuid4()}.jpg"},
            owner_user_id=her.id,
        )

        assert item.user_id == her.id

    @pytest.mark.asyncio
    async def test_assign_owner_outside_family_rejected(self, db_session):
        me = await _user(db_session)  # no family
        stranger = await _user(db_session)  # different, no family

        item_service = ItemService(db_session)

        with pytest.raises(ValueError):
            await item_service.create(
                user_id=me.id,
                item_data=ItemCreate(type="jacket"),
                image_paths={"image_path": f"test/{uuid4()}.jpg"},
                owner_user_id=stranger.id,
            )


class TestAssignOwnerAndPrivacyOnUpdate:
    """PATCH /api/v1/items/{id} takes a plain JSON body (no image), so this is exercised
    through the real HTTP route."""

    @pytest.mark.asyncio
    async def test_reassign_owner_and_set_private_via_update(self, db_session, client):
        me = await _user(db_session)
        fam = await _family(db_session, me)
        her = await _user(db_session, fam.id)

        item_service = ItemService(db_session)
        item = await item_service.create(
            user_id=me.id,
            item_data=ItemCreate(type="jacket"),
            image_paths={"image_path": f"test/{uuid4()}.jpg"},
        )

        headers = {"Authorization": f"Bearer {create_access_token(me.external_id)}"}
        r = await client.patch(
            f"/api/v1/items/{item.id}",
            headers=headers,
            json={"user_id": str(her.id), "is_private": True},
        )

        assert r.status_code == 200, r.text
        body = r.json()
        assert body["user_id"] == str(her.id)
        assert body["is_private"] is True

    @pytest.mark.asyncio
    async def test_reassign_owner_outside_family_rejected_via_update(self, db_session, client):
        me = await _user(db_session)  # no family
        stranger = await _user(db_session)  # different, no family

        item_service = ItemService(db_session)
        item = await item_service.create(
            user_id=me.id,
            item_data=ItemCreate(type="jacket"),
            image_paths={"image_path": f"test/{uuid4()}.jpg"},
        )

        headers = {"Authorization": f"Bearer {create_access_token(me.external_id)}"}
        r = await client.patch(
            f"/api/v1/items/{item.id}",
            headers=headers,
            json={"user_id": str(stranger.id)},
        )

        assert r.status_code == 400
