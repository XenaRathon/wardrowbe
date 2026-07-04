from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.calendar import DayRecordOut, PlanRequest, WearRequest
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


@router.post("/{d}/plan", response_model=DayRecordOut)
async def plan_day(
    d: date,
    body: PlanRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    svc = CalendarService(db)
    try:
        await svc.set_plan(current_user, d, body.outfit_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return await svc.get_day(current_user, d)


@router.post("/{d}/confirm", response_model=DayRecordOut)
async def confirm_day(
    d: date,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    try:
        return await CalendarService(db).confirm(current_user, d)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/{d}/wear", response_model=DayRecordOut)
async def wear_day(
    d: date,
    body: WearRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    svc = CalendarService(db)
    wearer = body.worn_by_user_id or current_user.id
    try:
        await svc.log_wear_outfit(current_user, d, body.outfit_id, wearer, body.occasion)
    except ValueError as e:
        status_code = 400 if "worn_by_user_id" in str(e) else 404
        raise HTTPException(status_code, str(e))
    return await svc.get_day(current_user, d)


@router.delete("/{d}/wear/{outfit_id}", response_model=DayRecordOut)
async def remove_wear(
    d: date,
    outfit_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    svc = CalendarService(db)
    try:
        await svc.remove_wear(current_user, d, outfit_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return await svc.get_day(current_user, d)
