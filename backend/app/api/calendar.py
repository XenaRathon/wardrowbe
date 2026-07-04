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
