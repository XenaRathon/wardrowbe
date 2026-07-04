from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.item import ClothingItem, ItemHistory
from app.models.outfit import Outfit, OutfitItem
from app.models.preference import UserPreference
from app.models.user import User
from app.schemas.item import DEFAULT_WASH_INTERVALS
from app.services.family_service import FamilyService
from app.services.item_service import ItemService


def _brief(o: Outfit) -> dict:
    return {"id": o.id, "occasion": o.occasion, "scheduled_for": o.scheduled_for,
            "worn_at": o.worn_at, "name": o.name,
            "item_ids": [oi.item_id for oi in o.items]}


class CalendarService:
    _REPEAT_EXCLUDE = {"shoes", "sneakers", "boots", "sandals", "jewelry", "watch",
                       "belt", "bag", "sunglasses", "hat", "scarf", "tie", "gloves"}

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
            repeat_warnings = (
                await self.recently_worn(user, [oi.item_id for oi in primary.items], d)
                if primary else []
            )
            records.append({
                "date": d,
                "primary": _brief(primary) if primary else None,
                "extras": [_brief(o) for o in extras],
                "repeat_warnings": repeat_warnings,
            })
        return records

    async def recently_worn(self, user: User, item_ids: list[UUID], on_date: date) -> list[UUID]:
        if not item_ids:
            return []
        pref = (await self.db.execute(
            select(UserPreference).where(UserPreference.user_id == user.id)
        )).scalar_one_or_none()
        window = pref.avoid_repeat_days if pref else 7
        since = on_date - timedelta(days=window)
        rows = (await self.db.execute(
            select(ItemHistory.item_id, ClothingItem.type)
            .join(ClothingItem, ClothingItem.id == ItemHistory.item_id)
            .where(
                ItemHistory.item_id.in_(item_ids),
                ItemHistory.worn_at >= since,
                ItemHistory.worn_at < on_date,
            )
        )).all()
        return [iid for iid, itype in rows if (itype or "").lower() not in self._REPEAT_EXCLUDE]

    async def get_day(self, user: User, d: date) -> dict:
        """Like get_range for a single date, but always returns a record even
        when the day has no outfits (e.g. after remove_wear clears the last one)."""
        records = await self.get_range(user, d, d)
        return records[0] if records else {"date": d, "primary": None, "extras": [], "repeat_warnings": []}

    async def set_plan(self, user: User, d: date, outfit_id: UUID) -> Outfit:
        outfit = await self._owned_outfit(user, outfit_id)
        # Clear any other plan for the day so only one outfit is scheduled per date.
        for o in await self._day_outfits(user, d):
            if o.id != outfit.id and o.scheduled_for == d:
                o.scheduled_for = None
        outfit.scheduled_for = d
        await self.db.flush()
        return outfit

    async def confirm(self, user: User, d: date) -> dict:
        planned = next((o for o in await self._day_outfits(user, d) if o.scheduled_for == d), None)
        if planned is None:
            raise ValueError("No planned outfit for this date")
        await self._log_outfit(user, planned, d, worn_by_user_id=user.id)
        return await self.get_day(user, d)

    async def log_wear_outfit(
        self,
        user: User,
        d: date,
        outfit_id: UUID,
        worn_by_user_id: UUID,
        occasion: str | None = None,
    ) -> Outfit:
        await self._validate_wearer(user, worn_by_user_id)
        outfit = await self._owned_outfit(user, outfit_id)
        await self._log_outfit(user, outfit, d, worn_by_user_id=worn_by_user_id, occasion=occasion)
        return outfit

    async def _validate_wearer(self, user: User, worn_by_user_id: UUID) -> None:
        member_ids = await FamilyService(self.db).get_member_ids(user)
        if worn_by_user_id not in member_ids:
            raise ValueError("worn_by_user_id must be a family member")

    async def remove_wear(self, user: User, d: date, outfit_id: UUID) -> None:
        outfit = await self._owned_outfit(user, outfit_id)
        hist = (await self.db.execute(
            select(ItemHistory)
            .where(ItemHistory.outfit_id == outfit.id, ItemHistory.worn_at == d)
            .options(selectinload(ItemHistory.item))
        )).scalars().all()
        items = {h.item_id: h.item for h in hist if h.item is not None}
        for h in hist:
            await self.db.delete(h)
        await self.db.flush()

        for item in items.values():
            if item.wear_count > 0:
                item.wear_count -= 1
            if item.wears_since_wash > 0:
                item.wears_since_wash -= 1
            effective_interval = (
                item.wash_interval
                if item.wash_interval is not None
                else DEFAULT_WASH_INTERVALS.get(item.type, 3)
            )
            item.needs_wash = item.wears_since_wash >= effective_interval
            item.last_worn_at = (await self.db.execute(
                select(func.max(ItemHistory.worn_at)).where(ItemHistory.item_id == item.id)
            )).scalar()

        outfit.worn_at = None
        await self.db.flush()

    async def _log_outfit(
        self,
        user: User,
        outfit: Outfit,
        d: date,
        *,
        worn_by_user_id: UUID,
        occasion: str | None = None,
    ) -> None:
        existing = (await self.db.execute(
            select(ItemHistory.item_id)
            .where(ItemHistory.outfit_id == outfit.id, ItemHistory.worn_at == d)
        )).scalars().all()
        already = set(existing)
        svc = ItemService(self.db)
        for oi in outfit.items:
            if oi.item_id in already:
                continue
            await svc.log_wear(
                oi.item,
                worn_at=d,
                outfit_id=outfit.id,
                worn_by_user_id=worn_by_user_id,
                occasion=occasion or outfit.occasion,
            )
        outfit.worn_at = d
        await self.db.flush()

    async def _owned_outfit(self, user: User, outfit_id: UUID) -> Outfit:
        o = (await self.db.execute(
            select(Outfit)
            .where(Outfit.id == outfit_id, Outfit.user_id == user.id)
            .options(selectinload(Outfit.items).selectinload(OutfitItem.item))
        )).scalar_one_or_none()
        if o is None:
            raise ValueError("Outfit not found")
        return o

    async def _day_outfits(self, user: User, d: date) -> list[Outfit]:
        return list((await self.db.execute(
            select(Outfit)
            .where(Outfit.user_id == user.id, or_(Outfit.scheduled_for == d, Outfit.worn_at == d))
            .options(selectinload(Outfit.items).selectinload(OutfitItem.item))
        )).scalars().all())
