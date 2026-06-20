import logging
from uuid import UUID

logger = logging.getLogger(__name__)

ITEM_ROLE: dict[str, str] = {
    "shirt": "base_top",
    "t-shirt": "base_top",
    "blouse": "base_top",
    "polo": "base_top",
    "tank-top": "base_top",
    "top": "base_top",
    "sweater": "base_top",
    "pants": "bottom",
    "jeans": "bottom",
    "shorts": "bottom",
    "skirt": "bottom",
    "dress": "full_body",
    "jumpsuit": "full_body",
    "cardigan": "mid_layer",
    "vest": "mid_layer",
    "jacket": "outer_layer",
    "blazer": "outer_layer",
    "coat": "outer_layer",
    "hoodie": "outer_layer",
    "shoes": "footwear",
    "sneakers": "footwear",
    "boots": "footwear",
    "sandals": "footwear",
    "socks": "socks",
    "tie": "neckwear",
    "hat": "accessory",
    "scarf": "accessory",
    "belt": "accessory",
    "bag": "accessory",
    "accessories": "accessory",
    # activewear
    "gym-top": "base_top",
    "leggings": "bottom",
    "joggers": "bottom",
    "tracksuit": "full_body",
    # one-piece / loungewear / swim (a complete look on their own)
    "swimwear": "full_body",
    "pajamas": "full_body",
    "robe": "full_body",
    # base layers / intimates: NOT part of an assembled outfit
    "base-layer": "base_top",  # thermal top, wearable on its own
    "bra": "intimate",
    "sports-bra": "base_top",  # visible athletic top
    "underwear": "intimate",
    "briefs": "intimate",
    "boxers": "intimate",
    "lingerie": "intimate",
    "shapewear": "intimate",
    "tights": "intimate",
}

INTIMATE_TYPES = frozenset(t for t, r in ITEM_ROLE.items() if r == "intimate")
# any of these can serve as the visible "top" of a look
_TOP_ROLES = frozenset({"base_top", "mid_layer", "outer_layer"})
# full-body pieces that read as a complete look without shoes
LOUNGE_NO_SHOES = frozenset({"pajamas", "robe", "swimwear"})


def outfit_is_complete(types) -> bool:
    """A real outfit = (a top + a bottom) OR a one-piece, plus shoes.

    A hoodie/cardigan/jacket can serve as the top. Loungewear/swim one-pieces
    don't need shoes. Accessories, socks, ties, and base layers never make an
    outfit on their own.
    """
    types_l = {(t or "").lower() for t in types if t}
    roles = {ITEM_ROLE.get(t) for t in types_l}
    has_top = bool(roles & _TOP_ROLES)
    has_core = "full_body" in roles or (has_top and "bottom" in roles)
    has_shoes = "footwear" in roles
    is_lounge = bool(types_l & LOUNGE_NO_SHOES)
    return has_core and (has_shoes or is_lounge)


def deduplicate_by_body_slot(item_ids: list[UUID], item_type_map: dict[UUID, str]) -> list[UUID]:
    seen_roles: dict[str, UUID] = {}
    result: list[UUID] = []
    has_full_body = any(
        ITEM_ROLE.get(item_type_map.get(iid, "")) == "full_body" for iid in item_ids
    )
    for iid in item_ids:
        item_type = item_type_map.get(iid, "")
        role = ITEM_ROLE.get(item_type)
        if not role:
            result.append(iid)
            continue
        if role == "accessory":
            result.append(iid)
            continue
        if role == "intimate":
            # base layers / underwear are not part of the assembled outfit
            continue
        if has_full_body and role in ("base_top", "bottom"):
            logger.warning(f"Removing {item_type} item {iid}: full_body item present")
            continue
        if role in seen_roles:
            logger.warning(
                f"Removing duplicate {role} item {iid} ({item_type}): "
                f"role already filled by {seen_roles[role]}"
            )
            continue
        seen_roles[role] = iid
        result.append(iid)
    return result


_CANONICAL_ROLE_ORDER = [
    "full_body",
    "base_top",
    "mid_layer",
    "outer_layer",
    "bottom",
    "footwear",
    "socks",
    "neckwear",
    "accessory",
]

_ROLE_SORT_INDEX: dict[str, int] = {role: idx for idx, role in enumerate(_CANONICAL_ROLE_ORDER)}


def canonical_item_order(item_ids: list[UUID], item_type_map: dict[UUID, str]) -> list[UUID]:
    original_positions = {iid: idx for idx, iid in enumerate(item_ids)}

    def sort_key(item_id: UUID) -> tuple[int, int]:
        item_type = item_type_map.get(item_id, "")
        role = ITEM_ROLE.get(item_type)
        role_idx = (
            _ROLE_SORT_INDEX.get(role, len(_CANONICAL_ROLE_ORDER))
            if role
            else len(_CANONICAL_ROLE_ORDER)
        )
        return (role_idx, original_positions[item_id])

    return sorted(item_ids, key=sort_key)
