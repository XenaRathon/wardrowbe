from app.schemas.preference import StyleProfile
from app.style_rules import FLATTERING, SEASON_PALETTE, flattering_attrs, palette_for
from app.services.ai_service import VALID_COLORS, VALID_SILHOUETTE, VALID_NECKLINE, VALID_RISE


def test_style_profile_keeps_sliders_and_adds_body_fields():
    p = StyleProfile()
    # existing sliders still default 50
    assert p.casual == 50 and p.bold == 50
    # new body fields default empty/None
    assert p.body_shape is None and p.palette == [] and p.season_confirmed is False


def test_style_profile_round_trips_body_fields():
    p = StyleProfile(body_shape="pear", color_season="soft-autumn", palette=["olive", "rust"],
                     season_confirmed=True)
    dumped = p.model_dump()
    assert dumped["body_shape"] == "pear"
    assert dumped["palette"] == ["olive", "rust"]
    # a legacy blob with only sliders still parses
    legacy = StyleProfile(**{"casual": 70, "formal": 20, "sporty": 50, "minimalist": 50, "bold": 50})
    assert legacy.body_shape is None


def test_every_shape_has_recommended_and_avoid():
    shapes = {"hourglass", "pear", "inverted-triangle", "rectangle", "apple"}
    assert shapes.issubset(FLATTERING)
    for s in shapes:
        assert "recommended" in FLATTERING[s] and "avoid" in FLATTERING[s]


def test_rule_values_are_valid_vocab():
    valid = {"silhouette": VALID_SILHOUETTE, "neckline": VALID_NECKLINE, "rise": VALID_RISE}
    for s, rules in FLATTERING.items():
        for bucket in ("recommended", "avoid"):
            for attr, values in rules[bucket].items():
                assert attr in valid, f"{s}/{bucket}: unknown attr {attr}"
                assert set(values).issubset(valid[attr]), f"{s}/{bucket}/{attr} has invalid values"


def test_palette_values_are_valid_colors():
    for season, colors in SEASON_PALETTE.items():
        assert set(colors).issubset(VALID_COLORS), f"{season} has invalid colors"


def test_accessors_default_gracefully():
    assert flattering_attrs("not-a-shape") == {"recommended": {}, "avoid": {}}
    assert palette_for("not-a-season") == []
    assert "neckline" in flattering_attrs("pear")["recommended"]
