from app.services.sizing import bra_size, generic_size


def test_bra_size_us_34b():
    # ABTF: band = snug underbust in inches (86cm ≈ 33.9in → 34 band, NOT underbust+4).
    # cup = bust − underbust in inches (91−86=5cm ≈ 2in → B).
    r = bra_size(underbust_cm=86, bust_cm=91, system="US")
    assert r["band"] == 34
    assert r["cup"] == "B"
    assert r["label"] == "34B"
    assert r["method"] == "ABTF"


def test_bra_size_none_when_missing():
    assert bra_size(underbust_cm=None, bust_cm=86) is None


def test_bra_size_systems_differ():
    us = bra_size(74, 90, "US")
    eu = bra_size(74, 90, "EU")
    assert us["system"] == "US" and eu["system"] == "EU"
    assert us["band"] != eu["band"]        # EU band uses cm (~underbust+... )


def test_generic_size_bands():
    assert generic_size({"chest": 88, "waist": 74}) in {"S", "M"}
    assert generic_size({}) == "M"


def test_bra_size_coerces_numeric_strings():
    # body_measurements is a free-form dict; string values (e.g. "86") must
    # not raise -- they should coerce and match the numeric-input result.
    numeric = bra_size(underbust_cm=86, bust_cm=91, system="US")
    stringy = bra_size(underbust_cm="86", bust_cm="91", system="US")
    assert stringy == numeric
    assert stringy["label"] == "34B"


def test_bra_size_non_numeric_returns_none_not_raise():
    assert bra_size(underbust_cm="abc", bust_cm=91) is None
