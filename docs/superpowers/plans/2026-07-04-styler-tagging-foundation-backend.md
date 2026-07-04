# Styler Tagging Foundation — Backend Implementation Plan (Plan 1 of 3 for the Styler)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the tagging foundation the Body-Type Styler scores against — a category→type→subtype taxonomy (for a cascading selector), richer base-category subtypes, new cut attributes (neckline/rise/silhouette/sleeve), and a nightly re-tag worker to backfill them.

**Architecture:** A canonical `app/taxonomy.py` maps every `type` to one parent category and lists valid subtypes per type; `category` is derived from `type` (no stored column). Four nullable cut-attribute columns are added to `ClothingItem` and flow through the existing AI-tagging parse (`ClothingTags` → `_parse_tags_from_response` → `tags_to_item_fields`). The tagging prompt is enriched. A cron worker re-tags items missing the new attributes.

**Tech Stack:** Python 3.11, FastAPI (`/api/v1`), SQLAlchemy 2 async + asyncpg, Alembic, Pydantic v2, arq worker, pytest (real Postgres `wardrobe_test`), local Ollama tagging (`qwen3.5:4b`).

## Global Constraints

- Python 3.11; SQLAlchemy 2 async (`Mapped[...]`, `mapped_column`).
- Endpoints under `/api/v1` (router registered in `app/api/router.py`); auth `current_user: Annotated[User, Depends(get_current_user)]`; DB `Annotated[AsyncSession, Depends(get_db)]`.
- Migrations additive/forward-only; new columns nullable (no backfill migration). Migration dir is `backend/migrations/versions/` (NOT `alembic/`).
- `category` is DERIVED from `type` — do NOT add a stored `category` column. `type` stays the single source of truth.
- New cut attributes are OPTIONAL/nullable; anything downstream must tolerate their absence.
- AI tagging goes through the existing `AIService._parse_tags_from_response` / `ClothingTags`; validate new attributes against controlled sets exactly like the existing `validate_value(x, VALID_SET)` pattern.
- Run tests ONLY via the wrapper: `bash /home/xenarathon/claude/wardrowbe/backend/run-tests.sh <pytest args>` (venv 3.11 + server test pg/redis + auto-migrates the test DB). Never call `python -m pytest` directly.
- Commit after each task (`feat:`/`test:` message).

---

## File Structure

- `backend/app/taxonomy.py` (new) — `CATEGORY_TYPES`, `category_for_type`, `SUBTYPES`, `CATEGORY_ORDER`.
- `backend/app/api/taxonomy.py` (new) — `GET /taxonomy`.
- `backend/app/api/router.py` — register taxonomy router.
- `backend/app/models/item.py` — add `neckline`, `rise`, `silhouette`, `sleeve_length` to `ClothingItem`.
- `backend/migrations/versions/<rev>_cut_attributes.py` — additive migration.
- `backend/app/services/ai_service.py` — `ClothingTags` fields + `VALID_NECKLINE/RISE/SILHOUETTE/SLEEVE` + parse.
- `backend/app/workers/tagging.py` — `tags_to_item_fields` maps the new attributes.
- `backend/app/schemas/item.py` — expose new attributes on read/update schemas.
- `backend/app/api/items.py` / `app/services/item_service.py` — accept new attributes on update.
- `backend/app/prompts/clothing_analysis.txt` — expanded subtypes + new attributes.
- `backend/app/workers/retag.py` (new) — nightly re-tag worker; registered in `backend/app/workers/worker.py`.
- Tests: `backend/tests/test_taxonomy.py`, `test_cut_attributes.py`, `test_retag_worker.py` (new).

---

## Task 1: Category taxonomy module + `GET /taxonomy`

**Files:**
- Create: `backend/app/taxonomy.py`
- Create: `backend/app/api/taxonomy.py`
- Modify: `backend/app/api/router.py`
- Test: `backend/tests/test_taxonomy.py`

**Interfaces:**
- Produces:
  - `CATEGORY_TYPES: dict[str, list[str]]` — parent category → its `type`s.
  - `CATEGORY_ORDER: list[str]` — display order of categories.
  - `SUBTYPES: dict[str, list[str]]` — `type` → allowed subtypes.
  - `category_for_type(t: str) -> str | None` — reverse lookup (returns `None` for unknown/`"unknown"`).
  - `GET /api/v1/taxonomy` → `{"categories": [{"category": str, "types": [{"type": str, "subtypes": [str]}]}]}`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_taxonomy.py`:
```python
import pytest
from app.services.ai_service import VALID_TYPES
from app.taxonomy import CATEGORY_TYPES, SUBTYPES, category_for_type


def test_every_valid_type_has_exactly_one_category():
    assigned = [t for types in CATEGORY_TYPES.values() for t in types]
    # no type appears in two categories
    assert len(assigned) == len(set(assigned))
    # every VALID_TYPES member is categorized
    missing = VALID_TYPES - set(assigned)
    assert not missing, f"uncategorized types: {sorted(missing)}"


def test_category_for_type_reverse_lookup():
    assert category_for_type("bra") == "Intimates"
    assert category_for_type("jeans") == "Bottoms"
    assert category_for_type("unknown") is None
    assert category_for_type("not-a-type") is None


def test_subtypes_only_reference_known_types():
    assert set(SUBTYPES).issubset(VALID_TYPES)
    assert "push-up" in SUBTYPES["bra"]
    assert "crop" in SUBTYPES["top"]


@pytest.mark.asyncio
async def test_taxonomy_endpoint(client, auth_headers):
    r = await client.get("/api/v1/taxonomy", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    cats = {c["category"] for c in data["categories"]}
    assert "Intimates" in cats and "Tops" in cats
    intimates = next(c for c in data["categories"] if c["category"] == "Intimates")
    bra = next(t for t in intimates["types"] if t["type"] == "bra")
    assert "push-up" in bra["subtypes"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `bash backend/run-tests.sh tests/test_taxonomy.py -v`
Expected: FAIL (`app.taxonomy` missing).

- [ ] **Step 3: Implement the taxonomy module**

Create `backend/app/taxonomy.py`. Populate `CATEGORY_TYPES` so its union equals `VALID_TYPES` exactly (read `VALID_TYPES` in `app/services/ai_service.py` and cover every member). Example structure — extend to cover ALL `VALID_TYPES`:
```python
CATEGORY_ORDER = [
    "Tops", "Bottoms", "Dresses & One-pieces", "Outerwear", "Footwear",
    "Intimates", "Activewear", "Sleep & Lounge", "Swimwear", "Accessories",
]

CATEGORY_TYPES: dict[str, list[str]] = {
    "Tops": ["t-shirt", "top", "shirt", "blouse", "polo", "tank-top", "sweater", "hoodie", "cardigan"],
    "Bottoms": ["pants", "jeans", "shorts", "skirt", "leggings", "joggers"],
    "Dresses & One-pieces": ["dress", "jumpsuit", "tracksuit"],
    "Outerwear": ["jacket", "coat", "blazer", "vest"],
    "Footwear": ["shoes", "sneakers", "boots", "sandals"],
    "Intimates": ["bra", "sports-bra", "underwear", "briefs", "boxers", "lingerie", "shapewear", "tights"],
    "Activewear": ["gym-top", "base-layer"],
    "Sleep & Lounge": ["pajamas", "robe"],
    "Swimwear": ["swimwear"],
    "Accessories": ["hat", "scarf", "belt", "bag", "tie", "jewelry", "watch", "sunglasses", "gloves", "socks"],
}

SUBTYPES: dict[str, list[str]] = {
    "top": ["crop", "tube", "bandeau", "halter", "camisole", "peplum", "wrap", "muscle", "boxy"],
    "t-shirt": ["crop", "boxy", "muscle", "ringer", "pocket", "oversized"],
    "shirt": ["button-down", "oxford", "flannel", "camp-collar", "henley", "tie-front", "tunic"],
    "blouse": ["wrap", "peplum", "tie-neck", "peasant", "shell"],
    "dress": ["sundress", "slip", "maxi", "midi", "wrap", "shirt-dress", "a-line", "bodycon", "tea", "shift"],
    "skirt": ["mini", "midi", "maxi", "pleated", "wrap", "pencil", "circle", "a-line"],
    "pants": ["chinos", "cargo", "trousers", "wide-leg", "straight", "bootcut", "sweatpants"],
    "jeans": ["skinny", "straight", "bootcut", "wide-leg", "mom", "boyfriend", "flare"],
    "bra": ["push-up", "balconette", "bralette", "t-shirt", "plunge", "full-coverage", "wireless"],
    "sports-bra": ["low-impact", "medium-impact", "high-impact", "racerback"],
    "underwear": ["thong", "bikini", "hipster", "boyshort", "high-waist"],
    "sweater": ["pullover", "crewneck", "turtleneck", "v-neck", "cowl"],
    "jacket": ["denim-jacket", "bomber", "parka", "windbreaker", "trucker", "anorak"],
    "shoes": ["loafers", "oxfords", "mules", "flats", "heels", "platforms"],
    "sneakers": ["low-top", "high-top", "chunky", "slip-on"],
    "boots": ["ankle", "chelsea", "combat", "knee-high", "rain"],
    "socks": ["ankle", "crew", "knee-high", "no-show", "dress", "athletic"],
    "tie": ["necktie", "bow-tie", "bolo"],
}

_TYPE_TO_CATEGORY = {t: cat for cat, types in CATEGORY_TYPES.items() for t in types}


def category_for_type(t: str | None) -> str | None:
    if not t or t == "unknown":
        return None
    return _TYPE_TO_CATEGORY.get(t)
```

- [ ] **Step 4: Implement the endpoint + register**

Create `backend/app/api/taxonomy.py`:
```python
from typing import Annotated

from fastapi import APIRouter, Depends
from app.models.user import User
from app.taxonomy import CATEGORY_ORDER, CATEGORY_TYPES, SUBTYPES
from app.utils.auth import get_current_user

router = APIRouter(prefix="/taxonomy", tags=["Taxonomy"])


@router.get("")
async def get_taxonomy(current_user: Annotated[User, Depends(get_current_user)]):
    return {
        "categories": [
            {
                "category": cat,
                "types": [
                    {"type": t, "subtypes": SUBTYPES.get(t, [])}
                    for t in CATEGORY_TYPES[cat]
                ],
            }
            for cat in CATEGORY_ORDER
        ]
    }
```
Register in `backend/app/api/router.py` following the existing include pattern:
```python
from app.api import taxonomy
api_router.include_router(taxonomy.router)
```

- [ ] **Step 5: Run to verify it passes**

Run: `bash backend/run-tests.sh tests/test_taxonomy.py -v`
Expected: PASS (all 4). If `test_every_valid_type_has_exactly_one_category` fails, add the missing types to `CATEGORY_TYPES` until the union equals `VALID_TYPES`.

- [ ] **Step 6: Commit**
```bash
git add backend/app/taxonomy.py backend/app/api/taxonomy.py backend/app/api/router.py backend/tests/test_taxonomy.py
git commit -m "feat(taxonomy): category->type->subtype map + GET /taxonomy for cascading selector"
```

---

## Task 2: Cut attributes end-to-end (schema → parse → item)

**Files:**
- Modify: `backend/app/models/item.py` (ClothingItem)
- Create: `backend/migrations/versions/<rev>_cut_attributes.py`
- Modify: `backend/app/services/ai_service.py` (ClothingTags + VALID sets + parse)
- Modify: `backend/app/workers/tagging.py` (`tags_to_item_fields`)
- Modify: `backend/app/schemas/item.py` (read + update schemas)
- Modify: `backend/app/services/item_service.py` (`update` applies them)
- Test: `backend/tests/test_cut_attributes.py`

**Interfaces:**
- Produces: `ClothingItem.neckline/rise/silhouette/sleeve_length: Mapped[str | None]`; `ClothingTags.neckline/rise/silhouette/sleeve_length: str | None = None`; `VALID_NECKLINE`, `VALID_RISE`, `VALID_SILHOUETTE`, `VALID_SLEEVE` sets; parse populates them via `validate_value`.

- [ ] **Step 1: Add the model columns**

In `backend/app/models/item.py`, in `ClothingItem` (near `fit`/`style`):
```python
    neckline: Mapped[str | None] = mapped_column(String(30))
    rise: Mapped[str | None] = mapped_column(String(30))
    silhouette: Mapped[str | None] = mapped_column(String(30))
    sleeve_length: Mapped[str | None] = mapped_column(String(30))
```

- [ ] **Step 2: Generate the migration**

Run from `backend/`:
```bash
cd /home/xenarathon/claude/wardrowbe/backend
export PATH="$PWD/.venv/bin:$PATH"
export DATABASE_URL="postgresql+asyncpg://wardrobe:wardrobe@192.168.1.209:55432/wardrobe_test"
python -m alembic revision --autogenerate -m "cut_attributes: neckline, rise, silhouette, sleeve_length"
```
Open the file under `backend/migrations/versions/`; keep ONLY the four `add_column`s (delete any unrelated drift, as prior migrations in this repo do). Use `postgresql.UUID(as_uuid=True)` style only if UUIDs appear (they don't here).

- [ ] **Step 3: Write the failing test**

Create `backend/tests/test_cut_attributes.py`:
```python
import pytest
from app.services.ai_service import AIService, VALID_NECKLINE, VALID_RISE


def test_parse_populates_cut_attributes():
    svc = AIService(endpoints=[{"name": "x", "url": "http://x/v1", "vision_model": "m", "text_model": "m"}])
    resp = (
        '{"type":"dress","subtype":"a-line","primary_color":"navy","colors":["navy"],'
        '"pattern":"solid","material":null,"formality":"casual","style":["classic"],'
        '"season":["all-season"],"fit":"regular","neckline":"v-neck","rise":null,'
        '"silhouette":"a-line","sleeve_length":"short"}'
    )
    tags = svc._parse_tags_from_response(resp)
    assert tags.neckline == "v-neck"
    assert tags.silhouette == "a-line"
    assert tags.sleeve_length == "short"
    assert tags.rise is None


def test_parse_rejects_out_of_vocab_attribute():
    svc = AIService(endpoints=[{"name": "x", "url": "http://x/v1", "vision_model": "m", "text_model": "m"}])
    resp = '{"type":"top","neckline":"banana","sleeve_length":"short"}'
    tags = svc._parse_tags_from_response(resp)
    assert tags.neckline is None       # not in VALID_NECKLINE -> dropped
    assert tags.sleeve_length == "short"
```
*(Confirm the `AIService(...)` constructor signature by reading `ai_service.py`; adjust the endpoint arg to match how existing tests in `tests/test_ai_service.py` instantiate it.)*

- [ ] **Step 4: Run to verify it fails**

Run: `bash backend/run-tests.sh tests/test_cut_attributes.py -v`
Expected: FAIL (`VALID_NECKLINE` missing / attributes not parsed).

- [ ] **Step 5: Implement**

In `backend/app/services/ai_service.py`:
Add the controlled vocabularies near the other `VALID_*` sets:
```python
VALID_NECKLINE = {"crew", "v-neck", "scoop", "boat", "halter", "off-shoulder",
                  "turtleneck", "cowl", "square", "sweetheart", "collared", "strapless"}
VALID_RISE = {"high", "mid", "low"}
VALID_SILHOUETTE = {"a-line", "bodycon", "straight", "wrap", "fit-and-flare", "shift",
                    "pencil", "pleated", "oversized", "tailored", "skinny", "bootcut", "wide-leg"}
VALID_SLEEVE = {"sleeveless", "short", "three-quarter", "long"}
```
Add to `ClothingTags` (after `fit`):
```python
    neckline: str | None = None
    rise: str | None = None
    silhouette: str | None = None
    sleeve_length: str | None = None
```
In `_parse_tags_from_response`, after the `tags.fit = ...` line:
```python
        tags.neckline = validate_value(data.get("neckline"), VALID_NECKLINE)
        tags.rise = validate_value(data.get("rise"), VALID_RISE)
        tags.silhouette = validate_value(data.get("silhouette"), VALID_SILHOUETTE)
        tags.sleeve_length = validate_value(data.get("sleeve_length"), VALID_SLEEVE)
```
In `backend/app/workers/tagging.py` `tags_to_item_fields`, add the four fields to the returned dict (mirror how `fit`/`subtype` are mapped):
```python
        "neckline": tags.neckline,
        "rise": tags.rise,
        "silhouette": tags.silhouette,
        "sleeve_length": tags.sleeve_length,
```
In `backend/app/schemas/item.py`: add the four optional fields to the item READ schema and `ItemUpdate` (`str | None = None`). In `backend/app/services/item_service.py` `update`, they flow through the existing `model_dump(exclude_unset=True)` + `setattr` loop (verify that loop applies arbitrary fields; if it whitelists, add the four).

- [ ] **Step 6: Run to verify it passes**

Run: `bash backend/run-tests.sh tests/test_cut_attributes.py -v`
Expected: PASS. Then full suite: `bash backend/run-tests.sh -q`.

- [ ] **Step 7: Commit**
```bash
git add backend/app/models/item.py backend/migrations/versions backend/app/services/ai_service.py backend/app/workers/tagging.py backend/app/schemas/item.py backend/app/services/item_service.py backend/tests/test_cut_attributes.py
git commit -m "feat(tagging): neckline/rise/silhouette/sleeve cut attributes end-to-end"
```

---

## Task 3: Prompt enrichment (subtypes + cut attributes)

**Files:**
- Modify: `backend/app/prompts/clothing_analysis.txt`
- Test: `backend/tests/test_cut_attributes.py` (add a JSON-shape assertion)

**Interfaces:**
- Consumes: `VALID_NECKLINE/RISE/SILHOUETTE/SLEEVE` (Task 2), `SUBTYPES` (Task 1).
- Produces: the tagging prompt now instructs the model to output `neckline`, `rise`, `silhouette`, `sleeve_length` and richer subtypes.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_cut_attributes.py`:
```python
def test_prompt_declares_new_attributes():
    from pathlib import Path
    txt = Path("app/prompts/clothing_analysis.txt").read_text()
    for key in ("neckline", "rise", "silhouette", "sleeve_length"):
        assert key in txt, f"prompt missing {key}"
    # a richer base-category subtype example is present
    assert "crop" in txt and "halter" in txt
```

- [ ] **Step 2: Run to verify it fails**

Run: `bash backend/run-tests.sh tests/test_cut_attributes.py::test_prompt_declares_new_attributes -v`
Expected: FAIL (keys absent from the prompt).

- [ ] **Step 3: Edit the prompt**

In `backend/app/prompts/clothing_analysis.txt`:
- Under SUBTYPE, add examples for the under-served base categories (mirror the existing `- type → a, b, c` bullet style): `top → crop, tube, bandeau, halter, camisole, peplum, wrap`; `t-shirt → crop, boxy, muscle, ringer`; `shirt → button-down, oxford, flannel, henley, camp-collar`; `blouse → wrap, peplum, tie-neck, shell`.
- Add four new attribute blocks with their vocabularies (copy the exact value lists from `VALID_NECKLINE/RISE/SILHOUETTE/SLEEVE`), each marked optional/null:
  `NECKLINE (optional, pick one or null): crew, v-neck, scoop, boat, halter, off-shoulder, turtleneck, cowl, square, sweetheart, collared, strapless`
  `RISE (optional, bottoms only, pick one or null): high, mid, low`
  `SILHOUETTE (optional, pick one or null): a-line, bodycon, straight, wrap, fit-and-flare, shift, pencil, pleated, oversized, tailored, skinny, bootcut, wide-leg`
  `SLEEVE_LENGTH (optional, pick one or null): sleeveless, short, three-quarter, long`
- Extend the final output JSON object to include `"neckline":null,"rise":null,"silhouette":null,"sleeve_length":null`.

- [ ] **Step 4: Run to verify it passes**

Run: `bash backend/run-tests.sh tests/test_cut_attributes.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add backend/app/prompts/clothing_analysis.txt backend/tests/test_cut_attributes.py
git commit -m "feat(tagging): enrich prompt with base-category subtypes + cut attributes"
```

---

## Task 4: Nightly re-tag worker

**Files:**
- Create: `backend/app/workers/retag.py`
- Modify: `backend/app/workers/worker.py` (register cron + function)
- Test: `backend/tests/test_retag_worker.py`

**Interfaces:**
- Consumes: `AIService.analyze_image`, `tags_to_item_fields`, `ItemStatus`.
- Produces: `check_retag_backfill(ctx)` — re-tags a bounded batch of `ready` items whose cut attributes are all NULL (i.e. tagged before this feature), applying the AI result; throttled (respects single-GPU `max_jobs=1`), idempotent, resumable across runs.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_retag_worker.py`. Mirror the fake-ctx/session pattern in `tests/test_notification_workers.py`. The test: insert a `ready` item with `neckline/rise/silhouette/sleeve_length` all NULL and a valid `image_path`; monkeypatch `AIService.analyze_image` to return a `ClothingTags` with `neckline="v-neck"` etc.; invoke `check_retag_backfill(ctx)`; assert the item now has `neckline == "v-neck"`. Add a second assertion that an item which ALREADY has a non-null cut attribute is NOT re-tagged (the monkeypatched analyze_image is not called for it — track calls). Read `test_notification_workers.py` first for the exact ctx/db fakes; if the harness is unclear, report NEEDS_CONTEXT rather than guessing.

- [ ] **Step 2: Run to verify it fails**

Run: `bash backend/run-tests.sh tests/test_retag_worker.py -v`
Expected: FAIL (`check_retag_backfill` missing).

- [ ] **Step 3: Implement the worker**

Create `backend/app/workers/retag.py` with `async def check_retag_backfill(ctx)`:
- Get a db session from `ctx` the same way `check_wear_nudges` does.
- Query a bounded batch (e.g. `limit(20)`) of `ClothingItem` where `status == ItemStatus.ready` AND all four cut attributes `IS NULL` AND `image_path IS NOT NULL`, ordered by `updated_at` (resumable — next run picks up the rest).
- For each: `tags = await AIService(...).analyze_image(item.image_path)`; apply `tags_to_item_fields(tags)` values for the four cut attributes (and refreshed subtype) via `setattr`/`update`; commit per item (so a mid-batch failure keeps progress). Wrap each item in try/except and log — one bad image must not stop the batch.
- Keep the batch small + serial (single-GPU Ollama, `max_jobs=1`).

Register in `backend/app/workers/worker.py`: add `check_retag_backfill` to the `functions` list and a nightly `cron(check_retag_backfill, hour={3})` (mirror how `check_wear_nudges`/`check_auto_confirm` are registered). Add to the registry-completeness test if one exists.

- [ ] **Step 4: Run to verify it passes**

Run: `bash backend/run-tests.sh tests/test_retag_worker.py -v`
Expected: PASS. Then full suite: `bash backend/run-tests.sh -q`.

- [ ] **Step 5: Commit**
```bash
git add backend/app/workers/retag.py backend/app/workers/worker.py backend/tests/test_retag_worker.py
git commit -m "feat(tagging): nightly re-tag worker backfills cut attributes"
```

---

## Final: full suite

- [ ] Run `bash backend/run-tests.sh -q` — all green (1 known-unrelated failure only if the OIDC slash fix is NOT on this branch; if branched from post-`393b316` main, expect zero failures).
- [ ] Do NOT push/deploy — this stacks with the rest of the Styler backend (Plans 2–3) and its frontend before deploy.

## Self-Review (author checklist — completed)

- **Spec coverage (Component 0 only):** taxonomy + derived category + selector API → Task 1; subtype expansion → Tasks 1 (data) + 3 (prompt); cut attributes (schema/parse/item) → Task 2; prompt enrichment → Task 3; nightly re-tag → Task 4. **Components 1–4 (profile, integration, guidance, buy-advisor) are Plans 2–3 — not here.**
- **Placeholders:** none — the only prose-directed steps (Task 4 test harness) defer to the existing `test_notification_workers.py` fakes rather than inventing them; every code step shows code.
- **Type consistency:** `category_for_type`, `CATEGORY_TYPES`, `SUBTYPES`, `VALID_NECKLINE/RISE/SILHOUETTE/SLEEVE`, `ClothingTags.{neckline,rise,silhouette,sleeve_length}`, `check_retag_backfill` used consistently across tasks.

## Out of scope for Plan 1 (→ Plans 2 & 3)
Style-profile measurements/analysis/rules/draft, `style_fit` scoring integration, styling guidance, and the Buy-Advisor (gap analysis + paste-to-size + bra sizing). Frontend (cascading selector UI, profile wizard) is a separate frontend plan.
