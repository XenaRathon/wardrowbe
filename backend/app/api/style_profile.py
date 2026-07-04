from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.database import get_db
from app.models.user import User
from app.schemas.preference import StyleProfile
from app.services.ai_service import AIDisabledError
from app.services.style_service import StyleService
from app.utils.auth import get_current_user

router = APIRouter(prefix="/style-profile", tags=["Style Profile"])


class StyleProfileUpdate(BaseModel):
    color_season: str | None = None
    kibbe_lean: str | None = None
    palette: list[str] | None = None
    season_confirmed: bool | None = None
    kibbe_confirmed: bool | None = None


class StyleDraftRequest(BaseModel):
    hints: dict = Field(default_factory=dict)
    image_b64: str | None = None


@router.get("", response_model=dict)
async def get_style_profile(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    service = StyleService(db)
    return await service.get_profile(current_user)


@router.put("", response_model=dict)
async def update_style_profile(
    data: StyleProfileUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    service = StyleService(db)
    preferences = await service.preference_service.get_or_create_preferences(current_user.id)

    profile = StyleProfile(**(preferences.style_profile or {}))
    update_data = data.model_dump(exclude_unset=True)
    for field in ("color_season", "kibbe_lean", "palette", "season_confirmed", "kibbe_confirmed"):
        if field in update_data:
            setattr(profile, field, update_data[field])

    preferences.style_profile = profile.model_dump()
    flag_modified(preferences, "style_profile")
    await db.commit()

    return await service.get_profile(current_user)


@router.post("/draft", response_model=dict)
async def draft_style_profile(
    data: StyleDraftRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    service = StyleService(db)
    try:
        return await service.draft(current_user, hints=data.hints, image_b64=data.image_b64)
    except AIDisabledError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Internal AI is disabled; style drafting is deferred to an external agent.",
        ) from None
