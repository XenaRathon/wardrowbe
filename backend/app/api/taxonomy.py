from typing import Annotated

from fastapi import APIRouter, Depends

from app.models.user import User
from app.taxonomy import CATEGORY_ORDER, CATEGORY_TYPES, SUBTYPES
from app.utils.auth import get_current_user

router = APIRouter(prefix="/taxonomy", tags=["Taxonomy"])


@router.get("")
async def get_taxonomy(current_user: Annotated[User, Depends(get_current_user)]):
    return {
        "categories": [
            {
                "category": cat,
                "types": [
                    {"type": t, "subtypes": SUBTYPES.get(t, [])}
                    for t in CATEGORY_TYPES[cat]
                ],
            }
            for cat in CATEGORY_ORDER
        ]
    }
