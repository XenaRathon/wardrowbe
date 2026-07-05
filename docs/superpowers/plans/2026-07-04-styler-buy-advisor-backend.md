# Styler Buy-Advisor — Backend Implementation Plan (Plan 3 of 3 for the Styler)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Buy-Advisor: gap analysis over the user's closet → ranked buy recommendations (in flattering cuts/colours) with retailer search links, plus a paste-a-URL size recommendation (with bra/intimate baseline sizing).

**Architecture:** A pure gap-analysis engine buckets owned items by `ITEM_ROLE` (from `app.utils.clothing`), scores the marginal complete-outfits each missing slot would unlock, and maps the top gaps to concrete garment types annotated with `style_rules` recommendations (shape silhouette/neckline/rise + season palette colour). A pure `sizing.py` computes bra band/cup + generic S/M/L from measurements. Paste-to-size fetches a product page, LLM-parses its size chart, matches the user's measurements, and falls back to the pure sizing when the page can't be read.

**Tech Stack:** Python 3.11, FastAPI (`/api/v1`), SQLAlchemy 2 async, Pydantic v2, httpx, pytest (real Postgres `wardrobe_test`), local Ollama (`qwen3.5:4b`).

**Branch:** continues on `feat/styler-tagging` (uses Plan 1 cut attributes + taxonomy + Plan 2 profile/style_rules).

## Global Constraints

- Python 3.11; SQLAlchemy 2 async; endpoints under `/api/v1` with `current_user: Annotated[User, Depends(get_current_user)]` + `Annotated[AsyncSession, Depends(get_db)]`.
- Gap analysis runs over the user's OWN `ready`, non-archived items (per-user, not the shared household pool — you buy for your own wardrobe). Exclude `INTIMATE_TYPES` from the outfit-completeness gap logic (bras aren't outfit pieces), but intimates ARE valid buy/sizing targets.
- Buy recommendations pull recommended silhouette/neckline/rise from `style_rules.flattering_attrs(body_shape)` and colour from `style_rules.palette_for(color_season)` — degrade gracefully (no shape/season → generic rec without those annotations). NEVER hard-require a profile.
- Size recommendation is BEST-EFFORT: on fetch/parse failure, fall back to generic S/M/L from measurements (or the bra baseline for bra products), with a visible `confidence` + `source` field. Bra sizing UI copy states brand variance makes it a starting point.
- All AI local via `AIService`; wrap AI-endpoint failure so endpoints return a controlled error, never an unhandled 500 (mirror Plan 2's `StyleDraftError`→503 pattern). Guard AI calls with `require_internal_ai("text")`.
- Buy-recs are computed ON-DEMAND (no persistence — the wishlist model is roadmap 2c).
- Run tests ONLY via `bash /home/xenarathon/claude/wardrowbe/backend/run-tests.sh <pytest args>`. Never `python -m pytest` directly.
- Commit after each task.

---

## File Structure

- `backend/app/services/gap_analysis.py` (new) — pure closet-gap scoring → ranked missing roles.
- `backend/app/services/sizing.py` (new) — pure bra band/cup + generic size from measurements.
- `backend/app/services/buy_advisor_service.py` (new) — assembles buy-recs (gap + style_rules + search links); paste-to-size (fetch + LLM parse + match + fallback).
- `backend/app/api/buy_advisor.py` (new) — `GET /buy-advisor`, `POST /buy-advisor/size`.
- `backend/app/api/router.py` — register the router.
- Tests: `backend/tests/test_gap_analysis.py`, `test_sizing.py`, `test_buy_advisor_service.py`, `test_buy_advisor_api.py` (new).

---

## Task 1: Gap-analysis engine

**Files:**
- Create: `backend/app/services/gap_analysis.py`
- Test: `backend/tests/test_gap_analysis.py`

**Interfaces:**
- Consumes: `app.utils.clothing.ITEM_ROLE`.
- Produces: `analyze_gaps(item_types: list[str]) -> list[dict]` — ranked list of `{"role": str, "marginal_outfits": int, "reason": str}` for the core buildable roles (`base_top`→"top", `bottom`, `footwear`, `outer_layer`), highest marginal first. Pure (takes a list of type strings, no DB).

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_gap_analysis.py`:
```python
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `bash backend/run-tests.sh tests/test_gap_analysis.py -v`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement**

Create `backend/app/services/gap_analysis.py`:
```python
from app.utils.clothing import ITEM_ROLE

_TOP_ROLES = {"base_top", "mid_layer", "outer_layer"}


def _counts(item_types: list[str]) -> dict[str, int]:
    c = {"top": 0, "bottom": 0, "full_body": 0, "footwear": 0, "outer_layer": 0}
    for t in item_types:
        role = ITEM_ROLE.get((t or "").lower())
        if role in _TOP_ROLES:
            c["top"] += 1
        if role == "bottom":
            c["bottom"] += 1
        if role == "full_body":
            c["full_body"] += 1
        if role == "footwear":
            c["footwear"] += 1
        if role == "outer_layer":
            c["outer_layer"] += 1
    return c


def analyze_gaps(item_types: list[str]) -> list[dict]:
    c = _counts(item_types)
    shoes = max(1, c["footwear"])
    # marginal new complete outfits from adding ONE item of each role
    marginal = {
        "bottom": c["top"] * shoes,
        "base_top": c["bottom"] * shoes,
        "footwear": (c["top"] * c["bottom"] + c["full_body"]),
        "outer_layer": (c["top"] * c["bottom"] + c["full_body"]),  # layering versatility
    }
    # footwear only matters when you actually lack shoes
    if c["footwear"] >= 2:
        marginal["footwear"] = max(0, marginal["footwear"] // 4)
    reasons = {
        "bottom": f"You have {c['top']} tops but {c['bottom']} bottoms — a new bottom pairs with all of them.",
        "base_top": f"You have {c['bottom']} bottoms but {c['top']} tops — a new top adds fresh looks.",
        "footwear": f"With {c['footwear']} pairs of shoes, another pair multiplies your outfits.",
        "outer_layer": "A structured layer (blazer/jacket) adds versatility across your looks.",
    }
    ranked = sorted(marginal.items(), key=lambda kv: kv[1], reverse=True)
    return [{"role": r, "marginal_outfits": m, "reason": reasons[r]} for r, m in ranked]
```
If `test_no_shoes_recommends_footwear` doesn't rank footwear first (e.g. because top×bottom is small), that's acceptable only if footwear still appears; adjust the `>= 2` gate / formula so the NAMED test cases pass (they encode intended behaviour).

- [ ] **Step 4: Run to verify it passes**

Run: `bash backend/run-tests.sh tests/test_gap_analysis.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add backend/app/services/gap_analysis.py backend/tests/test_gap_analysis.py
git commit -m "feat(buy-advisor): closet gap-analysis engine (marginal-outfits scoring)"
```

---

## Task 2: Bra/intimate + generic sizing (pure)

**Files:**
- Create: `backend/app/services/sizing.py`
- Test: `backend/tests/test_sizing.py`

**Methodology — follow /r/ABraThatFits (reference: https://www.abrathatfits.org/calculator):**
- **Band** = the SNUG underbust measurement, rounded to the nearest even inch. Do NOT use the legacy "add 4 inches" method — ABTF bands are the underbust itself.
- **Cup** = (loose standing **bust** − snug **underbust**), in INCHES, mapped to the **US cup sequence**: 0″=AA, 1″=A, 2″=B, 3″=C, 4″=D, 5″=DD, 6″=DDD, 7″=G, 8″=H, 9″=I, 10″=J (each inch of difference = one cup up). `label = f"{band}{cup}"`.
- Return `"method": "ABTF"` in the dict; UI copy (frontend) will note brand variance makes it a starting point.
- UK/EU differ from US by band-unit convention (EU bands are cm-based: 65/70/75…); keep US as the primary and provide UK/EU band conversion.

**Interfaces:**
- Produces:
  - `bra_size(underbust_cm: float, bust_cm: float, system: str = "US") -> dict | None` — `{"band": int, "cup": str, "label": str, "system": str, "method": "ABTF"}` or `None` if inputs missing. `system` in `{"US","UK","EU"}`.
  - `generic_size(measurements: dict, garment_role: str | None = None) -> str` — an S/M/L(/XS/XL) from bust/chest+waist (best-effort; returns "M" when nothing usable).

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_sizing.py`:
```python
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `bash backend/run-tests.sh tests/test_sizing.py -v`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement**

Create `backend/app/services/sizing.py`:
```python
_CUP_LETTERS = ["AA", "A", "B", "C", "D", "DD", "DDD", "G", "H", "I", "J"]


def bra_size(underbust_cm, bust_cm, system: str = "US") -> dict | None:
    if underbust_cm is None or bust_cm is None or underbust_cm <= 0 or bust_cm <= 0:
        return None
    system = system.upper()
    diff_cm = max(0.0, bust_cm - underbust_cm)
    cup_idx = min(len(_CUP_LETTERS) - 1, round(diff_cm / 2.54))  # ~1 inch per cup
    cup = _CUP_LETTERS[cup_idx]
    if system == "EU":
        band = int(round(underbust_cm / 5.0) * 5)          # EU bands: 65,70,75,... (cm-based)
    elif system == "UK":
        ub_in = underbust_cm / 2.54
        band = int(round(ub_in / 2.0) * 2)                 # nearest even inch band
    else:  # US
        ub_in = underbust_cm / 2.54
        band = int(round(ub_in / 2.0) * 2)
        if band < 28:
            band = 28
    return {"band": band, "cup": cup, "label": f"{band}{cup}", "system": system, "method": "ABTF"}


def generic_size(measurements: dict, garment_role: str | None = None) -> str:
    def _f(k):
        v = measurements.get(k)
        try:
            return float(v) if v is not None else None
        except (TypeError, ValueError):
            return None
    chest = _f("bust") or _f("chest")
    if chest is None:
        return "M"
    # rough unisex upper-body banding in cm
    if chest < 82:
        return "XS"
    if chest < 90:
        return "S"
    if chest < 100:
        return "M"
    if chest < 110:
        return "L"
    return "XL"
```
Tune the cup/band thresholds only if a NAMED test case disagrees (the tests encode intended output). Note EU vs US band differ by construction (cm-rounded vs inch-rounded), satisfying `test_bra_size_systems_differ`.

- [ ] **Step 4: Run to verify it passes**

Run: `bash backend/run-tests.sh tests/test_sizing.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add backend/app/services/sizing.py backend/tests/test_sizing.py
git commit -m "feat(buy-advisor): bra band/cup + generic sizing from measurements"
```

---

## Task 3: Buy-Advisor service (recs + search links + paste-to-size)

**Files:**
- Create: `backend/app/services/buy_advisor_service.py`
- Test: `backend/tests/test_buy_advisor_service.py`

**Interfaces:**
- Consumes: `analyze_gaps` (Task 1), `sizing.bra_size`/`generic_size` (Task 2), `style_rules.flattering_attrs`/`palette_for`, `StyleService.get_profile` (Plan 2), `AIService.generate_text`, `ITEM_ROLE`.
- Produces:
  - `BuyAdvisorService(db).recommendations(user) -> list[dict]` — per top gap: `{"role", "type", "silhouette", "color", "rationale", "search_links": [{"retailer","url"}]}` (silhouette/color from style_rules when a profile exists; None otherwise).
  - `BuyAdvisorService(db).size_for_url(user, product_url, product_type=None) -> dict` — `{"size", "confidence", "source"}` where `source` in `{"chart","measurement","bra-baseline"}`. Fetch page → `_parse_chart` (LLM) → match; on any failure fall back to sizing.
  - `_search_links(query: str) -> list[dict]`, `_fetch_page(url) -> str | None`, `_parse_chart(page_text) -> dict | None` (isolated for tests).

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_buy_advisor_service.py`:
```python
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_recommendations_returns_search_links(db_session, test_user):
    from app.services.buy_advisor_service import BuyAdvisorService
    # give the user a lopsided closet via the service's item query — or patch analyze_gaps
    with patch("app.services.buy_advisor_service.BuyAdvisorService._owned_types",
               new=AsyncMock(return_value=["t-shirt"] * 6 + ["sneakers", "sneakers"])):
        recs = await BuyAdvisorService(db_session).recommendations(test_user)
    assert recs and recs[0]["search_links"]
    assert recs[0]["search_links"][0]["url"].startswith("http")


@pytest.mark.asyncio
async def test_size_for_url_falls_back_on_fetch_failure(db_session, test_user):
    from app.services.buy_advisor_service import BuyAdvisorService
    test_user.body_measurements = {"chest": 96, "waist": 84}
    svc = BuyAdvisorService(db_session)
    with patch.object(svc, "_fetch_page", new=AsyncMock(return_value=None)):
        out = await svc.size_for_url(test_user, "http://x/product")
    assert out["source"] == "measurement"
    assert out["size"] in {"XS", "S", "M", "L", "XL"}


@pytest.mark.asyncio
async def test_size_for_url_uses_chart_when_parsed(db_session, test_user):
    from app.services.buy_advisor_service import BuyAdvisorService
    test_user.body_measurements = {"chest": 96, "waist": 84}
    svc = BuyAdvisorService(db_session)
    chart = {"S": {"chest": 88}, "M": {"chest": 96}, "L": {"chest": 104}}
    with patch.object(svc, "_fetch_page", new=AsyncMock(return_value="<html>chart</html>")), \
         patch.object(svc, "_parse_chart", new=AsyncMock(return_value=chart)):
        out = await svc.size_for_url(test_user, "http://x/product")
    assert out["source"] == "chart"
    assert out["size"] == "M"        # 96 matches M exactly
```

- [ ] **Step 2: Run to verify it fails**

Run: `bash backend/run-tests.sh tests/test_buy_advisor_service.py -v`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement**

Create `backend/app/services/buy_advisor_service.py` with `BuyAdvisorService(db)`:
- `_owned_types(user)`: query the user's own `ready`, non-archived `ClothingItem.type` list (per-user; read how `pairing_service`/`item_service` query items and mirror it, but scope to `user.id` only — NOT the shared pool).
- `recommendations(user)`: `types = await self._owned_types(user)`; `gaps = analyze_gaps(types)`; get profile via `StyleService(self.db).get_profile(user)`; for the top 3 gaps, map role→a representative `type` (e.g. bottom→"jeans", base_top→"top", footwear→"sneakers", outer_layer→"blazer"), pull `flattering_attrs(profile["body_shape"]).get("recommended")` for a silhouette + a palette colour from `palette_for(profile["color_season"])`; build a `query` string + `_search_links(query)`; assemble the rec dict with a rationale (gap reason + shape/colour note when present).
- `_search_links(query)`: return 1-2 prefilled search URLs, e.g. `{"retailer":"Google Shopping","url":"https://www.google.com/search?tbm=shop&q="+urllib.parse.quote(query)}`. No scraping.
- `size_for_url(user, product_url, product_type)`: if `product_type` is a bra/intimate type AND measurements have underbust+bust → return `bra_size(...)` with `source="bra-baseline"`. Else: `page = await self._fetch_page(url)`; if page: `chart = await self._parse_chart(page)`; if chart: pick the size whose chart chest/bust is the smallest value >= the user's chest (else nearest) → `source="chart"`, confidence "high"/"medium". On ANY failure (no page/no chart/exception): `generic_size(measurements)` with `source="measurement"`, low confidence.
- `_fetch_page(url)`: `httpx.AsyncClient(timeout=10, follow_redirects=True, headers={"User-Agent": "..."})`; return text or None on `httpx.HTTPError`.
- `_parse_chart(page_text)`: `AIService(...).generate_text(prompt, system_prompt="Extract the size chart as JSON {size:{chest,waist,hips}} from this page text. OUTPUT ONLY JSON.")` (guard with `require_internal_ai("text")`; wrap failures → return None). Truncate page_text to a sane length before sending.

- [ ] **Step 4: Run to verify it passes**

Run: `bash backend/run-tests.sh tests/test_buy_advisor_service.py -v`
Expected: PASS. Then full suite `bash backend/run-tests.sh -q`.

- [ ] **Step 5: Commit**
```bash
git add backend/app/services/buy_advisor_service.py backend/tests/test_buy_advisor_service.py
git commit -m "feat(buy-advisor): recommendations + search links + paste-to-size (chart parse + fallback)"
```

---

## Task 4: Buy-Advisor endpoints

**Files:**
- Create: `backend/app/api/buy_advisor.py`
- Modify: `backend/app/api/router.py`
- Test: `backend/tests/test_buy_advisor_api.py`

**Interfaces:**
- Consumes: `BuyAdvisorService`.
- Produces: `GET /api/v1/buy-advisor` → `{"recommendations": [...]}`; `POST /api/v1/buy-advisor/size` (`{product_url, product_type?}`) → `{size, confidence, source}`. Auth-gated. AI failure inside → controlled error (503), never unhandled 500.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_buy_advisor_api.py`:
```python
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_get_buy_advisor(client, auth_headers, test_user):
    with patch("app.services.buy_advisor_service.BuyAdvisorService._owned_types",
               new=AsyncMock(return_value=["t-shirt"] * 5 + ["sneakers"])):
        r = await client.get("/api/v1/buy-advisor", headers=auth_headers)
    assert r.status_code == 200
    assert "recommendations" in r.json()


@pytest.mark.asyncio
async def test_post_size_measurement_fallback(client, auth_headers, test_user, db_session):
    test_user.body_measurements = {"chest": 96}
    await db_session.commit()
    with patch("app.services.buy_advisor_service.BuyAdvisorService._fetch_page",
               new=AsyncMock(return_value=None)):
        r = await client.post("/api/v1/buy-advisor/size", headers=auth_headers,
                             json={"product_url": "http://x/p"})
    assert r.status_code == 200
    assert r.json()["source"] == "measurement"
```

- [ ] **Step 2: Run to verify it fails**

Run: `bash backend/run-tests.sh tests/test_buy_advisor_api.py -v`
Expected: FAIL (routes missing).

- [ ] **Step 3: Implement**

Create `backend/app/api/buy_advisor.py` with `router = APIRouter(prefix="/buy-advisor", tags=["Buy Advisor"])`, the two routes using the standard `Annotated` deps, request model `SizeRequest(product_url: str, product_type: str | None = None)`. Catch the service's AI-failure error (reuse Plan 2's `StyleDraftError` pattern or a local `BuyAdvisorError`) → `HTTPException(503)`. Register in `backend/app/api/router.py` per the existing include pattern.

- [ ] **Step 4: Run to verify it passes**

Run: `bash backend/run-tests.sh tests/test_buy_advisor_api.py -q`
Expected: PASS. Then full suite `bash backend/run-tests.sh -q`.

- [ ] **Step 5: Commit**
```bash
git add backend/app/api/buy_advisor.py backend/app/api/router.py backend/tests/test_buy_advisor_api.py
git commit -m "feat(buy-advisor): GET /buy-advisor + POST /buy-advisor/size endpoints"
```

---

## Final: full suite
- [ ] `bash backend/run-tests.sh -q` — all green.
- [ ] Do NOT push/deploy — the whole styler backend (Plans 1-3) ships with the frontend.

## Self-Review (author checklist — completed)
- **Spec coverage (Component 4 / 2b):** gap analysis → Task 1; bra/intimate baseline + generic sizing → Task 2; recs + search links + paste-to-size (chart parse + fallback) → Task 3; endpoints → Task 4. Shareable/giftable wishlist (2c) + auto-suggest products = roadmap (not here). Frontend (buy-advisor view, paste box) = frontend plan.
- **Placeholders:** none — gap/sizing math is complete; service/endpoint tasks reference existing patterns (item queries, AIService.generate_text, httpx, StyleService.get_profile, Plan 2's 503 pattern) with concrete integration points.
- **Type consistency:** `analyze_gaps`, `bra_size`/`generic_size`, `BuyAdvisorService.{recommendations,size_for_url,_owned_types,_search_links,_fetch_page,_parse_chart}` used consistently across tasks.

## Out of scope for Plan 3 (→ roadmap + frontend)
Shareable/giftable wishlist (self-hosted link + Throne), auto-suggest products (active search/scrape), persistence of recs/wishlist; the buy-advisor UI + paste-URL box (frontend plan).
