"""Category taxonomy: parent category -> type -> subtype.

`category` is derived from `type` via `category_for_type`; there is no stored
category column. `CATEGORY_TYPES` must always partition `VALID_TYPES`
(`app.services.ai_service.VALID_TYPES`) exactly -- every valid type belongs to
exactly one category. See `test_every_valid_type_has_exactly_one_category`.
"""

CATEGORY_ORDER = [
    "Tops",
    "Bottoms",
    "Dresses & One-pieces",
    "Outerwear",
    "Footwear",
    "Intimates",
    "Activewear",
    "Sleep & Lounge",
    "Swimwear",
    "Accessories",
]

CATEGORY_TYPES: dict[str, list[str]] = {
    "Tops": [
        "t-shirt",
        "top",
        "shirt",
        "blouse",
        "polo",
        "tank-top",
        "sweater",
        "hoodie",
        "cardigan",
    ],
    "Bottoms": ["pants", "jeans", "shorts", "skirt", "leggings", "joggers"],
    "Dresses & One-pieces": ["dress", "jumpsuit", "tracksuit"],
    "Outerwear": ["jacket", "coat", "blazer", "vest"],
    "Footwear": ["shoes", "sneakers", "boots", "sandals"],
    "Intimates": [
        "bra",
        "sports-bra",
        "underwear",
        "briefs",
        "boxers",
        "lingerie",
        "shapewear",
        "tights",
    ],
    "Activewear": ["gym-top", "base-layer"],
    "Sleep & Lounge": ["pajamas", "robe"],
    "Swimwear": ["swimwear"],
    "Accessories": [
        "hat",
        "scarf",
        "belt",
        "bag",
        "tie",
        "jewelry",
        "watch",
        "sunglasses",
        "gloves",
        "socks",
        "accessories",
    ],
}

SUBTYPES: dict[str, list[str]] = {
    "top": ["crop", "tube", "bandeau", "halter", "camisole", "peplum", "wrap", "muscle", "boxy"],
    "t-shirt": ["crop", "boxy", "muscle", "ringer", "pocket", "oversized"],
    "shirt": ["button-down", "oxford", "flannel", "camp-collar", "henley", "tie-front", "tunic"],
    "blouse": ["wrap", "peplum", "tie-neck", "peasant", "shell"],
    "dress": ["sundress", "slip", "maxi", "midi", "wrap", "shirt-dress", "a-line", "bodycon", "tea", "shift"],
    "skirt": ["mini", "midi", "maxi", "pleated", "wrap", "pencil", "circle", "a-line"],
    "pants": ["chinos", "cargo", "trousers", "wide-leg", "straight", "bootcut", "sweatpants"],
    "jeans": ["skinny", "straight", "bootcut", "wide-leg", "mom", "boyfriend", "flare"],
    "bra": ["push-up", "balconette", "bralette", "t-shirt", "plunge", "full-coverage", "wireless"],
    "sports-bra": ["low-impact", "medium-impact", "high-impact", "racerback"],
    "underwear": ["thong", "bikini", "hipster", "boyshort", "high-waist"],
    "sweater": ["pullover", "crewneck", "turtleneck", "v-neck", "cowl"],
    "jacket": ["denim-jacket", "bomber", "parka", "windbreaker", "trucker", "anorak"],
    "shoes": ["loafers", "oxfords", "mules", "flats", "heels", "platforms"],
    "sneakers": ["low-top", "high-top", "chunky", "slip-on"],
    "boots": ["ankle", "chelsea", "combat", "knee-high", "rain"],
    "socks": ["ankle", "crew", "knee-high", "no-show", "dress", "athletic"],
    "tie": ["necktie", "bow-tie", "bolo"],
}

_TYPE_TO_CATEGORY = {t: cat for cat, types in CATEGORY_TYPES.items() for t in types}


def category_for_type(t: str | None) -> str | None:
    """Reverse lookup: type -> parent category. Returns None for unknown/"unknown"."""
    if not t or t == "unknown":
        return None
    return _TYPE_TO_CATEGORY.get(t)
