# Styler Profile + Scoring + Guidance — Backend Implementation Plan (Plan 2 of 3 for the Styler)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the style profile (deterministic body shape/vertical/frame from measurements + AI-drafted, user-confirmed colour-season/Kibbe-lean), a curated flattering-rule base, deep `style_fit` scoring in the outfit engine, and standalone styling guidance.

**Architecture:** Extends the EXISTING `StyleProfile` (a JSONB on `UserPreference.style_profile`) with body-profile fields (backward-compatible — the recommendation prompt's numeric filter ignores string fields). A pure `body_analysis.py` computes shape/vertical/frame from `User.body_measurements`; `style_rules.py` holds the shape→attributes + season→palette brain used by BOTH scoring and guidance; a new `_style_fit_score` multiplier folds into the existing multiplicative `score_items`; new endpoints add the AI draft and guidance.

**Tech Stack:** Python 3.11, FastAPI (`/api/v1`), SQLAlchemy 2 async, Pydantic v2, pytest (real Postgres `wardrobe_test`), local Ollama (`qwen3.5:4b`).

**Branch:** continues on `feat/styler-tagging` (needs the cut attributes from Plan 1 for `style_fit`).

## Global Constraints

- Python 3.11; SQLAlchemy 2 async; endpoints under `/api/v1` with `current_user: Annotated[User, Depends(get_current_user)]` + `Annotated[AsyncSession, Depends(get_db)]`.
- Body/colour profile is stored in the EXISTING `UserPreference.style_profile` JSONB by EXTENDING the `StyleProfile` pydantic schema with optional fields — do NOT add a new column; keep the existing 5 style sliders (casual/formal/sporty/minimalist/bold) intact and backward-compatible.
- Raw measurements live in the EXISTING `User.body_measurements` (JSONB); measurements API already exists in `app/api/users.py` (GET/PUT). Do NOT duplicate it.
- `style_fit` scoring DOWN-RANKS unflattering items, never hard-excludes — it is a multiplier bounded to roughly `[0.7, 1.2]` (mirror `_preference_score`'s `max(..., min(...))` clamping), never 0, and it degrades to a neutral `1.0` when the profile or the item's cut attributes are absent.
- All AI is local Ollama via the existing `AIService`; photo-derived draft labels are advisory (the endpoint returns a draft; saving is a separate confirmed write).
- `style_rules.py` is the single source of truth for flattering attributes + palettes — both `_style_fit_score` and the guidance generator read it (DRY).
- Run tests ONLY via `bash /home/xenarathon/claude/wardrowbe/backend/run-tests.sh <pytest args>`. Never call `python -m pytest` directly.
- Commit after each task.

---

## File Structure

- `backend/app/schemas/preference.py` — extend `StyleProfile` with body-profile fields.
- `backend/app/services/body_analysis.py` (new) — deterministic shape/vertical/frame.
- `backend/app/style_rules.py` (new) — `FLATTERING`, `SEASON_PALETTE`, accessors.
- `backend/app/services/item_scorer.py` — `_style_fit_score` + fold into `score_items` + `ScoredItem.style_fit_score`.
- `backend/app/services/recommendation_service.py` — add body-profile lines to `_format_preferences_for_prompt`.
- `backend/app/services/style_service.py` (new) — assemble profile, produce AI draft, produce guidance.
- `backend/app/api/style_profile.py` (new) — `GET /style-profile`, `POST /style-profile/draft`, `GET /style-profile/guidance`.
- `backend/app/api/router.py` — register the router.
- `backend/app/api/users.py` — on measurements save, populate the deterministic profile fields.
- Tests: `backend/tests/test_body_analysis.py`, `test_style_rules.py`, `test_style_fit_scoring.py`, `test_style_profile_api.py` (new).

---

## Task 1: Extend `StyleProfile` with body-profile fields

**Files:**
- Modify: `backend/app/schemas/preference.py` (`StyleProfile`)
- Test: `backend/tests/test_style_rules.py` (a schema round-trip test; the file also serves Task 3)

**Interfaces:**
- Produces: `StyleProfile` gains optional fields: `body_shape: str | None`, `vertical_line: str | None`, `frame: str | None`, `color_season: str | None`, `kibbe_lean: str | None`, `palette: list[str] = []`, `season_confirmed: bool = False`, `kibbe_confirmed: bool = False`. Existing 5 sliders unchanged.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_style_rules.py` (Task 3 adds more here):
```python
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `bash backend/run-tests.sh tests/test_style_rules.py -v`
Expected: FAIL (`body_shape` not a field).

- [ ] **Step 3: Implement**

In `backend/app/schemas/preference.py`, add to `StyleProfile` (after `bold`):
```python
    # Body-type styler profile (optional; coexists with the style sliders above)
    body_shape: str | None = None          # hourglass|pear|inverted-triangle|rectangle|apple
    vertical_line: str | None = None        # petite|balanced|tall
    frame: str | None = None                # small|medium|large
    color_season: str | None = None         # e.g. soft-autumn, cool-winter
    kibbe_lean: str | None = None           # dramatic|natural|romantic|classic|gamine
    palette: list[str] = Field(default_factory=list)
    season_confirmed: bool = False
    kibbe_confirmed: bool = False
```

- [ ] **Step 4: Run to verify it passes**

Run: `bash backend/run-tests.sh tests/test_style_rules.py -v`
Expected: PASS. Then confirm the prompt path is unaffected: `bash backend/run-tests.sh tests/test_recommendation_service.py -q`.

- [ ] **Step 5: Commit**
```bash
git add backend/app/schemas/preference.py backend/tests/test_style_rules.py
git commit -m "feat(styler): extend StyleProfile with body-profile fields (backward-compatible)"
```

---

## Task 2: Deterministic body-analysis engine

**Files:**
- Create: `backend/app/services/body_analysis.py`
- Modify: `backend/app/api/users.py` (populate deterministic fields on measurements save)
- Test: `backend/tests/test_body_analysis.py`

**Interfaces:**
- Produces: `analyze_measurements(m: dict) -> dict` returning `{"body_shape", "vertical_line", "frame"}` (values or `None` when inputs are missing). Helpers `compute_shape(bust, waist, hips, shoulders) -> str | None`, `compute_vertical(height, inseam) -> str | None`, `compute_frame(wrist, height) -> str | None`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_body_analysis.py`:
```python
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `bash backend/run-tests.sh tests/test_body_analysis.py -v`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement**

Create `backend/app/services/body_analysis.py`:
```python
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
    return base


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
```

- [ ] **Step 4: Run to verify it passes**

Run: `bash backend/run-tests.sh tests/test_body_analysis.py -v`
Expected: PASS. If a boundary case disagrees, adjust the thresholds until all named cases pass (they encode the intended classification).

- [ ] **Step 5: Wire into measurements save**

In `backend/app/api/users.py`, where `body_measurements` is updated (around line 59-61), after applying the measurements, compute and store the deterministic fields into the user's `UserPreference.style_profile`: load or create the user's `UserPreference`, parse its `style_profile` into a `StyleProfile`, set `body_shape`/`vertical_line`/`frame` from `analyze_measurements(user.body_measurements)`, and write it back (`preference.style_profile = profile.model_dump()`). Read the surrounding code to match how it accesses the session + user; if `UserPreference` isn't already loaded there, query it by `user_id`. Do NOT overwrite `color_season`/`kibbe_lean`/sliders — only the three deterministic fields.

- [ ] **Step 6: Run to verify it passes**

Run: `bash backend/run-tests.sh tests/test_body_analysis.py tests/test_users.py -q`
Expected: PASS (analysis + existing user tests green).

- [ ] **Step 7: Commit**
```bash
git add backend/app/services/body_analysis.py backend/app/api/users.py backend/tests/test_body_analysis.py
git commit -m "feat(styler): deterministic body-shape analysis + populate on measurements save"
```

---

## Task 3: Flattering-rule base (`style_rules.py`)

**Files:**
- Create: `backend/app/style_rules.py`
- Test: `backend/tests/test_style_rules.py` (extend)

**Interfaces:**
- Produces:
  - `FLATTERING: dict[str, dict]` — `body_shape` → `{"recommended": {...}, "avoid": {...}}` where the inner dicts map attribute names (`silhouette`, `neckline`, `rise`) to sets of values.
  - `SEASON_PALETTE: dict[str, list[str]]` — colour-season → palette colours (from `VALID_COLORS`).
  - `flattering_attrs(body_shape) -> dict` and `palette_for(color_season) -> list[str]` (empty/neutral defaults for unknown keys).

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_style_rules.py`:
```python
from app.style_rules import FLATTERING, SEASON_PALETTE, flattering_attrs, palette_for
from app.services.ai_service import VALID_COLORS, VALID_SILHOUETTE, VALID_NECKLINE, VALID_RISE


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
```

- [ ] **Step 2: Run to verify it fails**

Run: `bash backend/run-tests.sh tests/test_style_rules.py -v`
Expected: FAIL (`app.style_rules` missing).

- [ ] **Step 3: Implement**

Create `backend/app/style_rules.py`. Values MUST come from the `VALID_SILHOUETTE/NECKLINE/RISE`/`VALID_COLORS` sets (Plan 1 / ai_service). Encode well-known guidance, e.g.:
```python
FLATTERING: dict[str, dict] = {
    "pear": {
        "recommended": {"silhouette": {"a-line", "bootcut", "wide-leg", "fit-and-flare", "straight"},
                        "neckline": {"boat", "off-shoulder", "scoop", "square"},
                        "rise": {"high", "mid"}},
        "avoid": {"silhouette": {"skinny", "bodycon"}, "rise": {"low"}},
    },
    "inverted-triangle": {
        "recommended": {"silhouette": {"a-line", "fit-and-flare", "wide-leg", "bootcut"},
                        "neckline": {"v-neck", "scoop"}, "rise": {"mid", "low"}},
        "avoid": {"neckline": {"boat", "halter", "off-shoulder"}, "silhouette": {"oversized"}},
    },
    "hourglass": {
        "recommended": {"silhouette": {"bodycon", "wrap", "pencil", "fit-and-flare", "a-line"},
                        "neckline": {"v-neck", "sweetheart", "scoop"}, "rise": {"high", "mid"}},
        "avoid": {"silhouette": {"oversized", "shift"}},
    },
    "rectangle": {
        "recommended": {"silhouette": {"fit-and-flare", "wrap", "pleated", "a-line", "bodycon"},
                        "neckline": {"sweetheart", "scoop", "cowl"}, "rise": {"mid"}},
        "avoid": {"silhouette": {"straight", "shift"}},
    },
    "apple": {
        "recommended": {"silhouette": {"a-line", "wrap", "shift", "fit-and-flare"},
                        "neckline": {"v-neck", "scoop", "cowl"}, "rise": {"mid", "high"}},
        "avoid": {"silhouette": {"bodycon", "pencil"}, "neckline": {"turtleneck", "crew"}},
    },
}

SEASON_PALETTE: dict[str, list[str]] = {
    "cool-winter": ["black", "white", "navy", "burgundy", "purple", "blue", "silver", "gray"],
    "soft-autumn": ["olive", "brown", "tan", "beige", "cream", "burgundy", "gold", "green"],
    "warm-spring": ["cream", "tan", "gold", "orange", "yellow", "green", "beige", "light-blue"],
    "cool-summer": ["navy", "blue", "light-blue", "gray", "pink", "purple", "white", "silver"],
    # add the remaining common seasons; every color must be in VALID_COLORS
}


def flattering_attrs(body_shape: str | None) -> dict:
    return FLATTERING.get(body_shape or "", {"recommended": {}, "avoid": {}})


def palette_for(color_season: str | None) -> list[str]:
    return SEASON_PALETTE.get(color_season or "", [])
```

- [ ] **Step 4: Run to verify it passes**

Run: `bash backend/run-tests.sh tests/test_style_rules.py -v`
Expected: PASS. Fix any invalid vocab value the test flags.

- [ ] **Step 5: Commit**
```bash
git add backend/app/style_rules.py backend/tests/test_style_rules.py
git commit -m "feat(styler): flattering-rule base (shape attrs + season palettes)"
```

---

## Task 4: `_style_fit_score` in the outfit engine + prompt context

**Files:**
- Modify: `backend/app/services/item_scorer.py` (`_style_fit_score`, `ScoredItem`, `score_items`)
- Modify: `backend/app/services/recommendation_service.py` (`_format_preferences_for_prompt`)
- Test: `backend/tests/test_style_fit_scoring.py`

**Interfaces:**
- Consumes: `flattering_attrs`, `palette_for`, `StyleProfile` (from `preferences.style_profile`).
- Produces: `_style_fit_score(item: ClothingItem, profile: dict | None) -> float` in `[0.7, 1.2]` (1.0 neutral / no profile / no cut attrs); `ScoredItem.style_fit_score: float = 1.0`; `score_items` multiplies it into `total` and populates the field.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_style_fit_scoring.py`:
```python
from app.models.item import ClothingItem
from app.services.item_scorer import _style_fit_score


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
```

- [ ] **Step 2: Run to verify it fails**

Run: `bash backend/run-tests.sh tests/test_style_fit_scoring.py -v`
Expected: FAIL (`_style_fit_score` missing).

- [ ] **Step 3: Implement**

In `backend/app/services/item_scorer.py`, add:
```python
from app.style_rules import flattering_attrs, palette_for

_STYLE_ATTRS = ("silhouette", "neckline", "rise")


def _style_fit_score(item: "ClothingItem", profile: dict | None) -> float:
    if not profile:
        return 1.0
    score = 1.0
    rules = flattering_attrs(profile.get("body_shape"))
    rec, avoid = rules.get("recommended", {}), rules.get("avoid", {})
    for attr in _STYLE_ATTRS:
        val = getattr(item, attr, None)
        if not val:
            continue
        if val in rec.get(attr, set()):
            score += 0.08
        elif val in avoid.get(attr, set()):
            score -= 0.12
    palette = set(profile.get("palette") or [])
    if palette:
        item_colors = set(item.colors or ([item.primary_color] if item.primary_color else []))
        if item_colors:
            if item_colors & palette:
                score += 0.08
            else:
                score -= 0.05
    return max(0.7, min(1.2, score))
```
Add `style_fit_score: float = 1.0` to `ScoredItem`. In `score_items`, inside the per-item loop, compute `profile_dict = preferences.style_profile if preferences else None` (once before the loop), then `sfs = _style_fit_score(item, profile_dict)`, multiply `total *= sfs`, and pass `style_fit_score=sfs` into `ScoredItem(...)`.

In `backend/app/services/recommendation_service.py` `_format_preferences_for_prompt`, after the existing style_profile block, add body-profile context lines when present (read from `preferences.style_profile`): e.g. if `body_shape`, append `f"- Body shape: {body_shape} — favour {…recommended silhouettes/necklines…}, ease off {…avoid…}"` (pull the recommended/avoid from `flattering_attrs`); if `color_season`/`palette`, append `f"- Colour season: {color_season}; palette favours {', '.join(palette)}"`. Keep it concise.

- [ ] **Step 4: Run to verify it passes**

Run: `bash backend/run-tests.sh tests/test_style_fit_scoring.py tests/test_recommendation_service.py tests/test_item_scorer.py -q`
Expected: PASS (new scoring + existing scoring/recommendation tests green).

- [ ] **Step 5: Commit**
```bash
git add backend/app/services/item_scorer.py backend/app/services/recommendation_service.py backend/tests/test_style_fit_scoring.py
git commit -m "feat(styler): style_fit scoring (down-rank not exclude) + profile prompt context"
```

---

## Task 5: AI draft endpoint + style-profile assembler

**Files:**
- Create: `backend/app/services/style_service.py`
- Create: `backend/app/api/style_profile.py`
- Modify: `backend/app/api/router.py`
- Test: `backend/tests/test_style_profile_api.py`

**Interfaces:**
- Produces:
  - `StyleService(db).get_profile(user) -> dict` — assembles `{measurements, body_shape, vertical_line, frame, color_season, kibbe_lean, palette, *_confirmed}` from `user.body_measurements` + `preferences.style_profile`.
  - `StyleService(db).draft(user, hints: dict, image_b64: str | None) -> dict` — calls the local model with a styler prompt → `{"color_season", "kibbe_lean"}` (advisory; unsaved).
  - `GET /api/v1/style-profile`, `PUT /api/v1/style-profile` (save confirmed `color_season`/`kibbe_lean`/`palette` + `*_confirmed`), `POST /api/v1/style-profile/draft`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_style_profile_api.py`:
```python
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_get_style_profile(client, auth_headers, test_user, db_session):
    test_user.body_measurements = {"bust": 94, "waist": 68, "hips": 96, "shoulders": 94, "height": 168}
    await db_session.commit()
    r = await client.get("/api/v1/style-profile", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["body_shape"] == "hourglass"


@pytest.mark.asyncio
async def test_put_style_profile_saves_confirmed(client, auth_headers):
    r = await client.put("/api/v1/style-profile", headers=auth_headers,
                         json={"color_season": "soft-autumn", "palette": ["olive"], "season_confirmed": True})
    assert r.status_code == 200
    g = await client.get("/api/v1/style-profile", headers=auth_headers)
    assert g.json()["color_season"] == "soft-autumn" and g.json()["season_confirmed"] is True


@pytest.mark.asyncio
async def test_draft_returns_advisory_labels(client, auth_headers):
    with patch("app.services.style_service.StyleService._call_model",
               new=AsyncMock(return_value={"color_season": "cool-winter", "kibbe_lean": "dramatic"})):
        r = await client.post("/api/v1/style-profile/draft", headers=auth_headers,
                              json={"hints": {"undertone": "cool", "contrast": "high"}})
    assert r.status_code == 200
    assert r.json()["color_season"] == "cool-winter"
```
*(Adjust fixture usage to conftest — `test_user`/`auth_headers`/`db_session` exist. If `test_user` has no `UserPreference` row, the PUT must create one.)*

- [ ] **Step 2: Run to verify it fails**

Run: `bash backend/run-tests.sh tests/test_style_profile_api.py -v`
Expected: FAIL (endpoints missing).

- [ ] **Step 3: Implement**

Create `backend/app/services/style_service.py` with `StyleService(db)`:
- `get_profile(user)`: run `analyze_measurements(user.body_measurements or {})`, merge with the confirmed fields from the user's `UserPreference.style_profile` (parse via `StyleProfile`), return the assembled dict.
- `draft(user, hints, image_b64)`: build a concise styler prompt (system: "Given measurements-derived shape context + these hints + optional photo, propose the most likely 12-season colour-season and Kibbe lean. OUTPUT ONLY JSON {\"color_season\":..., \"kibbe_lean\":...}"), call `_call_model(...)` (a thin wrapper over the existing `AIService` native `/api/chat` path — reuse the same call mechanics `analyze_image`/`_call_with_fallback` use; if an image is provided include it, else a text-only call). Validate the returned `color_season` against `SEASON_PALETTE` keys and `kibbe_lean` against the known set; drop unknowns to None.
- `_call_model(...)`: isolate the actual AI call here so the test can patch it.

Create `backend/app/api/style_profile.py` with the three routes using the standard `Annotated` deps; PUT loads-or-creates the `UserPreference`, updates only `color_season`/`kibbe_lean`/`palette`/`*_confirmed` on its `StyleProfile`, writes back `model_dump()`. Register the router in `backend/app/api/router.py`.

- [ ] **Step 4: Run to verify it passes**

Run: `bash backend/run-tests.sh tests/test_style_profile_api.py -q`
Expected: PASS. Then full suite: `bash backend/run-tests.sh -q`.

- [ ] **Step 5: Commit**
```bash
git add backend/app/services/style_service.py backend/app/api/style_profile.py backend/app/api/router.py backend/tests/test_style_profile_api.py
git commit -m "feat(styler): style-profile GET/PUT + AI draft endpoint"
```

---

## Task 6: Styling guidance endpoint

**Files:**
- Modify: `backend/app/services/style_service.py` (`guidance`)
- Modify: `backend/app/api/style_profile.py` (`GET /style-profile/guidance`)
- Test: `backend/tests/test_style_profile_api.py` (extend)

**Interfaces:**
- Consumes: `flattering_attrs`, `palette_for`, `get_profile`.
- Produces: `StyleService(db).guidance(user) -> dict` — `{"summary": str, "recommended": {...}, "avoid": {...}, "palette": [...]}` where the structured parts come DIRECTLY from `style_rules` (deterministic) and `summary` is an LLM phrasing grounded in them; `GET /api/v1/style-profile/guidance`.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_style_profile_api.py`:
```python
@pytest.mark.asyncio
async def test_guidance_uses_rules(client, auth_headers, test_user, db_session):
    test_user.body_measurements = {"bust": 88, "waist": 72, "hips": 104, "shoulders": 86}  # pear
    await db_session.commit()
    from unittest.mock import AsyncMock, patch
    with patch("app.services.style_service.StyleService._call_model_text",
               new=AsyncMock(return_value="You're a pear — emphasise the waist and shoulders.")):
        r = await client.get("/api/v1/style-profile/guidance", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    # structured guidance is deterministic from the rule base, not the LLM
    assert "a-line" in body["recommended"].get("silhouette", [])
    assert isinstance(body["summary"], str) and body["summary"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `bash backend/run-tests.sh tests/test_style_profile_api.py::test_guidance_uses_rules -v`
Expected: FAIL (guidance missing).

- [ ] **Step 3: Implement**

Add `guidance(user)` to `StyleService`: get the profile, pull `flattering_attrs(body_shape)` (convert the sets to sorted lists for JSON) + `palette_for(color_season)`, and produce `summary` via `_call_model_text(prompt)` where the prompt feeds the shape + recommended/avoid + palette and asks for 2-3 sentences of encouraging, concrete guidance grounded in exactly those facts. Isolate the text call in `_call_model_text` so it can be patched. Add `GET /style-profile/guidance` to the router.

- [ ] **Step 4: Run to verify it passes**

Run: `bash backend/run-tests.sh tests/test_style_profile_api.py -q`
Expected: PASS. Then full suite `bash backend/run-tests.sh -q`.

- [ ] **Step 5: Commit**
```bash
git add backend/app/services/style_service.py backend/app/api/style_profile.py backend/tests/test_style_profile_api.py
git commit -m "feat(styler): styling guidance endpoint grounded in style_rules"
```

---

## Final: full suite
- [ ] `bash backend/run-tests.sh -q` — all green.
- [ ] Do NOT push/deploy — stacks with Plan 3 (Buy-Advisor) + the frontend before deploy.

## Self-Review (author checklist — completed)
- **Spec coverage (Components 1-3):** measurements→deterministic profile → Task 2; StyleProfile storage → Task 1; flattering-rule base → Task 3; deep style_fit scoring + prompt context → Task 4; AI draft + confirm (GET/PUT/draft) → Task 5; styling guidance → Task 6. Bra/intimate baseline sizing + buy-advisor → Plan 3 (not here). Frontend (wizard, confirm screen) → frontend plan.
- **Placeholders:** none — endpoint tasks reference existing patterns (users.py measurements, preferences.py style_profile, AIService call path) with concrete integration points; all logic steps show code.
- **Type consistency:** `analyze_measurements`, `compute_shape/vertical/frame`, `flattering_attrs`, `palette_for`, `_style_fit_score`, `ScoredItem.style_fit_score`, `StyleService.{get_profile,draft,guidance}` used consistently across tasks.

## Out of scope for Plan 2 (→ Plan 3 + frontend)
Bra/intimate baseline sizing, buy-advisor gap analysis, retailer search links, paste-to-size chart parsing; the profile onboarding wizard + confirm UI + cascading selector (frontend plan).
