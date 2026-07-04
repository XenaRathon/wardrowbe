from app.services.body_analysis import analyze_measurements, compute_shape


def test_shape_hourglass():
    # bust≈hips, defined waist
    assert compute_shape(bust=94, waist=68, hips=96, shoulders=94) == "hourglass"


def test_shape_pear():
    assert compute_shape(bust=88, waist=72, hips=104, shoulders=86) == "pear"


def test_shape_inverted_triangle():
    assert compute_shape(bust=100, waist=80, hips=90, shoulders=104) == "inverted-triangle"


def test_shape_rectangle():
    assert compute_shape(bust=90, waist=84, hips=92, shoulders=90) == "rectangle"


def test_shape_apple():
    assert compute_shape(bust=96, waist=100, hips=94, shoulders=94) == "apple"


def test_shape_none_when_missing():
    assert compute_shape(bust=None, waist=68, hips=96, shoulders=None) is None


def test_analyze_returns_all_three_keys():
    out = analyze_measurements({"bust": 94, "waist": 68, "hips": 96, "shoulders": 94,
                                "height": 168, "inseam": 78, "wrist": 15})
    assert set(out) == {"body_shape", "vertical_line", "frame"}
    assert out["body_shape"] == "hourglass"
