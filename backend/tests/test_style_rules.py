from app.schemas.preference import StyleProfile


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
