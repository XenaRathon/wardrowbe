from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.outfit import Outfit
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
