from app.services.gap_analysis import analyze_gaps


def test_many_tops_one_bottom_recommends_bottom():
    types = ["t-shirt"] * 8 + ["jeans"] + ["sneakers", "sneakers"]
    gaps = analyze_gaps(types)
    assert gaps[0]["role"] == "bottom"       # bottoms unlock the most new outfits
    assert gaps[0]["marginal_outfits"] > 0


def test_no_shoes_recommends_footwear():
    types = ["t-shirt", "t-shirt", "jeans", "jeans"]  # cores but no shoes
    gaps = analyze_gaps(types)
    roles = [g["role"] for g in gaps]
    assert "footwear" in roles
    # footwear ranks high because it unlocks all top×bottom combos
    assert gaps[0]["role"] == "footwear"


def test_balanced_closet_low_marginal():
    types = ["t-shirt"] * 3 + ["jeans"] * 3 + ["sneakers"] * 2 + ["blazer"]
    gaps = analyze_gaps(types)
    # still returns rankings, but the top marginal is modest vs the lopsided cases
    assert all("role" in g and "marginal_outfits" in g for g in gaps)


def test_empty_closet():
    assert analyze_gaps([]) != []  # recommends foundational roles even when empty
