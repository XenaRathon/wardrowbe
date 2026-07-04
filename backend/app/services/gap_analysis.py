from app.utils.clothing import ITEM_ROLE

_TOP_ROLES = {"base_top", "mid_layer", "outer_layer"}


def _counts(item_types: list[str]) -> dict[str, int]:
    c = {"top": 0, "bottom": 0, "full_body": 0, "footwear": 0, "outer_layer": 0}
    for t in item_types:
        role = ITEM_ROLE.get((t or "").lower())
        if role in _TOP_ROLES:
            c["top"] += 1
        if role == "bottom":
            c["bottom"] += 1
        if role == "full_body":
            c["full_body"] += 1
        if role == "footwear":
            c["footwear"] += 1
        if role == "outer_layer":
            c["outer_layer"] += 1
    return c


def analyze_gaps(item_types: list[str]) -> list[dict]:
    c = _counts(item_types)
    shoes = max(1, c["footwear"])
    # marginal new complete outfits from adding ONE item of each role
    marginal = {
        "bottom": c["top"] * shoes,
        "base_top": c["bottom"] * shoes,
        "footwear": (c["top"] * c["bottom"] + c["full_body"]),
        "outer_layer": (c["top"] * c["bottom"] + c["full_body"]),  # layering versatility
    }
    # footwear only matters when you actually lack shoes
    if c["footwear"] >= 2:
        marginal["footwear"] = max(0, marginal["footwear"] // 4)
    reasons = {
        "bottom": f"You have {c['top']} tops but {c['bottom']} bottoms — a new bottom pairs with all of them.",
        "base_top": f"You have {c['bottom']} bottoms but {c['top']} tops — a new top adds fresh looks.",
        "footwear": f"With {c['footwear']} pairs of shoes, another pair multiplies your outfits.",
        "outer_layer": "A structured layer (blazer/jacket) adds versatility across your looks.",
    }
    ranked = sorted(marginal.items(), key=lambda kv: kv[1], reverse=True)
    return [{"role": r, "marginal_outfits": m, "reason": reasons[r]} for r, m in ranked]
