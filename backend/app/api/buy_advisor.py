from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.services.ai_service import AIDisabledError
from app.services.buy_advisor_service import BuyAdvisorService
from app.utils.auth import get_current_user

router = APIRouter(prefix="/buy-advisor", tags=["Buy Advisor"])


class SizeRequest(BaseModel):
    product_url: str
    product_type: str | None = None


@router.get("", response_model=dict)
async def get_buy_advisor(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    service = BuyAdvisorService(db)
    try:
        recommendations = await service.recommendations(current_user)
    except AIDisabledError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Internal AI is disabled; buy-advisor recommendations are unavailable.",
        ) from None
    return {"recommendations": recommendations}


@router.post("/size", response_model=dict)
async def post_buy_advisor_size(
    data: SizeRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    service = BuyAdvisorService(db)
    try:
        return await service.size_for_url(
            current_user, data.product_url, product_type=data.product_type
        )
    except AIDisabledError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Internal AI is disabled; size lookup is unavailable.",
        ) from None
