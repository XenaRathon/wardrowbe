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
