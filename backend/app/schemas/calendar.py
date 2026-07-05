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
    repeat_warnings: list[UUID] = []


class PlanRequest(BaseModel):
    outfit_id: UUID


class WearRequest(BaseModel):
    outfit_id: UUID
    worn_by_user_id: UUID | None = None
    occasion: str | None = None
