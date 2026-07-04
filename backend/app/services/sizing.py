"""Pure sizing helpers for the Styler Buy-Advisor.

Bra sizing follows the /r/ABraThatFits (ABTF) methodology
(https://www.abrathatfits.org/calculator):

- Band = the SNUG underbust measurement, rounded to the nearest even inch.
  This is deliberately NOT the legacy "underbust + 4 inches" method.
- Cup = (loose standing bust - snug underbust), in inches, mapped onto the
  US cup sequence below (each inch of difference is one cup up).

UK bands share the US inch-based rounding convention; EU bands are
cm-based (65/70/75, ...), which is why US/UK and EU band numbers diverge
for the same underbust measurement.
"""

CM_PER_INCH = 2.54

_CUP_LETTERS = ["AA", "A", "B", "C", "D", "DD", "DDD", "G", "H", "I", "J"]

_VALID_SYSTEMS = {"US", "UK", "EU"}


def bra_size(underbust_cm, bust_cm, system: str = "US") -> dict | None:
    """Compute an ABTF-style bra band/cup from underbust + bust measurements (cm).

    Returns None if either measurement is missing or non-positive.
    """
    if underbust_cm is None or bust_cm is None:
        return None
    if underbust_cm <= 0 or bust_cm <= 0:
        return None

    system = (system or "US").upper()
    if system not in _VALID_SYSTEMS:
        system = "US"

    diff_cm = max(0.0, bust_cm - underbust_cm)
    cup_idx = min(len(_CUP_LETTERS) - 1, round(diff_cm / CM_PER_INCH))
    cup = _CUP_LETTERS[cup_idx]

    if system == "EU":
        # EU bands are cm-based: 65, 70, 75, ... (nearest multiple of 5)
        band = int(round(underbust_cm / 5.0) * 5)
    else:
        # US/UK bands are inch-based: nearest even inch, ABTF-style
        # (band = snug underbust itself, NOT underbust + 4).
        ub_in = underbust_cm / CM_PER_INCH
        band = int(round(ub_in / 2.0) * 2)
        if system == "US" and band < 28:
            band = 28

    return {
        "band": band,
        "cup": cup,
        "label": f"{band}{cup}",
        "system": system,
        "method": "ABTF",
    }


def generic_size(measurements: dict, garment_role: str | None = None) -> str:
    """Best-effort S/M/L(/XS/XL) from bust/chest (+ waist context), in cm.

    Falls back to "M" when nothing usable is present.
    """

    def _f(key):
        value = (measurements or {}).get(key)
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    chest = _f("bust")
    if chest is None:
        chest = _f("chest")
    if chest is None:
        return "M"

    # Rough unisex upper-body banding in cm.
    if chest < 82:
        return "XS"
    if chest < 90:
        return "S"
    if chest < 100:
        return "M"
    if chest < 110:
        return "L"
    return "XL"
