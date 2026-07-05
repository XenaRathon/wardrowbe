"""Flattering-rule base: body-shape -> recommended/avoid cut attributes, and
colour-season -> palette. Shared "brain" read by the scorer and the guidance
copy generator. All values are drawn from the VALID_* vocab sets in
app.services.ai_service so tagged item attributes can be matched directly.
"""

FLATTERING: dict[str, dict] = {
    "pear": {
        "recommended": {
            "silhouette": {"a-line", "bootcut", "wide-leg", "fit-and-flare", "straight"},
            "neckline": {"boat", "off-shoulder", "scoop", "square"},
            "rise": {"high", "mid"},
        },
        "avoid": {
            "silhouette": {"skinny", "bodycon"},
            "rise": {"low"},
        },
    },
    "inverted-triangle": {
        "recommended": {
            "silhouette": {"a-line", "fit-and-flare", "wide-leg", "bootcut"},
            "neckline": {"v-neck", "scoop"},
            "rise": {"mid", "low"},
        },
        "avoid": {
            "neckline": {"boat", "halter", "off-shoulder"},
            "silhouette": {"oversized"},
        },
    },
    "hourglass": {
        "recommended": {
            "silhouette": {"bodycon", "wrap", "pencil", "fit-and-flare", "a-line"},
            "neckline": {"v-neck", "sweetheart", "scoop"},
            "rise": {"high", "mid"},
        },
        "avoid": {
            "silhouette": {"oversized", "shift"},
        },
    },
    "rectangle": {
        "recommended": {
            "silhouette": {"fit-and-flare", "wrap", "pleated", "a-line", "bodycon"},
            "neckline": {"sweetheart", "scoop", "cowl"},
            "rise": {"mid"},
        },
        "avoid": {
            "silhouette": {"straight", "shift"},
        },
    },
    "apple": {
        "recommended": {
            "silhouette": {"a-line", "wrap", "shift", "fit-and-flare"},
            "neckline": {"v-neck", "scoop", "cowl"},
            "rise": {"mid", "high"},
        },
        "avoid": {
            "silhouette": {"bodycon", "pencil"},
            "neckline": {"turtleneck", "crew"},
        },
    },
}

SEASON_PALETTE: dict[str, list[str]] = {
    "cool-winter": ["black", "white", "navy", "burgundy", "purple", "blue", "silver", "gray"],
    "warm-winter": ["black", "red", "purple", "navy", "white", "burgundy", "gray", "gold"],
    "warm-spring": ["cream", "tan", "gold", "orange", "yellow", "green", "beige", "light-blue"],
    "cool-spring": ["light-blue", "pink", "cream", "yellow", "green", "tan", "blue", "white"],
    "soft-autumn": ["olive", "brown", "tan", "beige", "cream", "burgundy", "gold", "green"],
    "warm-autumn": ["brown", "olive", "orange", "gold", "tan", "burgundy", "green", "cream"],
    "cool-summer": ["navy", "blue", "light-blue", "gray", "pink", "purple", "white", "silver"],
    "soft-summer": ["gray", "light-blue", "pink", "purple", "navy", "tan", "white", "blue"],
}


def flattering_attrs(body_shape: str | None) -> dict:
    return FLATTERING.get(body_shape or "", {"recommended": {}, "avoid": {}})


def palette_for(color_season: str | None) -> list[str]:
    return SEASON_PALETTE.get(color_season or "", [])
