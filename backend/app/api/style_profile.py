from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.services.ai_service import AIDisabledError
from app.services.style_service import StyleDraftError, StyleService
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
    update_data = data.model_dump(exclude_unset=True)
    await service.update_confirmed(current_user, update_data)

    return await service.get_profile(current_user)


@router.get("/guidance", response_model=dict)
async def get_style_guidance(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    service = StyleService(db)
    return await service.guidance(current_user)


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
    except StyleDraftError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        ) from None
