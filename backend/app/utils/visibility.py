from uuid import UUID

from sqlalchemy import and_, or_

from app.models.item import ClothingItem
from app.models.user import User


def usable_items_filter(user: User, member_ids: list[UUID]):
    """Boolean clause: items owned by a family member that `user` may use —
    shared items from anyone, plus the user's own private items."""
    return and_(
        ClothingItem.user_id.in_(member_ids),
        or_(ClothingItem.is_private.is_(False), ClothingItem.user_id == user.id),
    )
