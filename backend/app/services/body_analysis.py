"""Deterministic body-shape analysis from measurements (all units consistent)."""


def _f(m: dict, k: str):
    v = m.get(k)
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def compute_shape(bust, waist, hips, shoulders) -> str | None:
    if None in (bust, waist, hips) or min(bust, waist, hips) <= 0:
        return None
    waist_defined = waist <= 0.75 * min(bust, hips)
    hips_dominant = hips >= bust * 1.05 and hips >= (shoulders or bust) * 1.05
    shoulders_dominant = (shoulders or bust) >= hips * 1.05 and bust >= hips * 1.02
    if waist >= bust and waist >= hips:
        return "apple"
    if waist_defined and abs(bust - hips) <= 0.05 * max(bust, hips):
        return "hourglass"
    if hips_dominant:
        return "pear"
    if shoulders_dominant:
        return "inverted-triangle"
    return "rectangle"


def compute_vertical(height, inseam) -> str | None:
    if height is None or height <= 0:
        return None
    # short/long legs shift the balance; height sets the base band (cm)
    if height < 160:
        base = "petite"
    elif height > 175:
        base = "tall"
    else:
        base = "balanced"

    if inseam is None or inseam <= 0:
        return base

    leg_ratio = inseam / height
    bands = ["petite", "balanced", "tall"]
    idx = bands.index(base)
    if leg_ratio >= 0.48:
        idx = min(idx + 1, len(bands) - 1)
    elif leg_ratio <= 0.44:
        idx = max(idx - 1, 0)
    return bands[idx]


def compute_frame(wrist, height) -> str | None:
    if wrist is None or height is None or height <= 0:
        return None
    ratio = height / wrist
    if ratio > 11.0:
        return "small"
    if ratio < 10.0:
        return "large"
    return "medium"


def analyze_measurements(m: dict) -> dict:
    bust, waist, hips = _f(m, "bust"), _f(m, "waist"), _f(m, "hips")
    shoulders, height = _f(m, "shoulders"), _f(m, "height")
    inseam, wrist = _f(m, "inseam"), _f(m, "wrist")
    return {
        "body_shape": compute_shape(bust, waist, hips, shoulders),
        "vertical_line": compute_vertical(height, inseam),
        "frame": compute_frame(wrist, height),
    }
