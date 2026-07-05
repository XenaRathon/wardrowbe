from app.models.item import ClothingItem
from app.models.preference import UserPreference
from app.services.item_scorer import _style_fit_score
from app.services.recommendation_service import RecommendationService


def _item(**kw):
    return ClothingItem(type=kw.get("type", "dress"), silhouette=kw.get("silhouette"),
                        neckline=kw.get("neckline"), rise=kw.get("rise"),
                        primary_color=kw.get("primary_color"), colors=kw.get("colors", []))


def test_neutral_without_profile():
    assert _style_fit_score(_item(silhouette="a-line"), None) == 1.0


def test_neutral_without_cut_attrs():
    profile = {"body_shape": "pear", "palette": ["olive"]}
    assert _style_fit_score(_item(silhouette=None, neckline=None, colors=[]), profile) == 1.0


def test_flattering_boosts():
    profile = {"body_shape": "pear"}
    s = _style_fit_score(_item(silhouette="a-line"), profile)
    assert s > 1.0


def test_unflattering_penalizes_but_not_zero():
    profile = {"body_shape": "pear"}
    s = _style_fit_score(_item(silhouette="skinny"), profile)
    assert 0.7 <= s < 1.0


def test_palette_match_boosts():
    profile = {"body_shape": "pear", "palette": ["olive", "rust"]}
    s = _style_fit_score(_item(silhouette="a-line", primary_color="olive"), profile)
    assert s > 1.0


def test_bounded():
    profile = {"body_shape": "pear", "palette": ["olive"]}
    for it in (_item(silhouette="a-line", neckline="boat", rise="high", primary_color="olive"),
               _item(silhouette="skinny", rise="low", primary_color="orange")):
        assert 0.7 <= _style_fit_score(it, profile) <= 1.2


def test_bool_body_profile_fields_not_treated_as_style_sliders():
    """season_confirmed / kibbe_confirmed are bools (int subclass in Python) and
    body_shape is a string -- none should leak into the numeric slider-derived
    'Preferred styles' / 'Less preferred styles' lines."""
    service = RecommendationService.__new__(RecommendationService)
    preferences = UserPreference(
        style_profile={
            "casual": 20,
            "season_confirmed": True,
            "kibbe_confirmed": True,
            "body_shape": "pear",
        }
    )
    text = service._format_preferences_for_prompt(preferences, None, None, None, occasion="work")
    assert "season_confirmed" not in text
    assert "kibbe_confirmed" not in text
    assert "Less preferred styles: casual" in text
