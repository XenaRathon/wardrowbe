# Body-Type Styler + Buy-Advisor — Design Spec (Spec 2a + 2b)

**Feature ID:** 2a (Style Profile + deep integration + guidance) + 2b (Buy-Advisor)
**Date:** 2026-07-04
**Status:** Approved design, pending implementation plan
**Fork:** xenarathon/wardrowbe (F.A.S.C.)
**Depends on:** B1 (calendar/sharing) merged first is preferable but not required — this spec is independent of B1's schema.

## Overview

Give each user a **style profile** — body shape, vertical line, frame, colour-season, and a Kibbe-lean — derived from measurements + a few guided hints + an optional photo (AI proposes a draft, the user confirms). The profile then (1) **deeply integrates** into the existing outfit recommendation/pairing engine so daily suggestions are scored for what flatters the user, (2) powers a **standalone styling guide**, and (3) drives a **Buy-Advisor** that gap-analyses the closet and recommends what to buy — in flattering cuts/colours, with retailer search links and per-product size recommendations (including bra/intimate sizing). To score "flattering" well, the AI tagging is enriched with cut attributes and richer subtypes, backfilled by a nightly re-tag.

### Goals
- A per-user style profile: shape · vertical · frame (deterministic from measurements) + colour-season · Kibbe-lean (AI-drafted, user-confirmed).
- **Tagging enrichment** so flatter-scoring is meaningful: a category→type→subtype taxonomy, expanded base-category subtypes, and new cut attributes (neckline, rise, silhouette, sleeve length), with a nightly full re-tag.
- **Deep integration**: profile-aware scoring in `item_scorer` + profile context in the recommendation prompt (down-rank unflattering, never exclude).
- **Styling guidance**: LLM-generated from a curated flattering-rule base (consistent with the scorer).
- **Buy-Advisor**: gap analysis → generic recs + retailer search links + paste-a-URL size recommendation (incl. bra/intimate baseline sizing).
- All AI local (Ollama `qwen3.5:4b`); body photos processed locally (privacy). Photo-derived labels are always advisory + user-confirmed.

### Non-goals (roadmap — see §11)
- **2c**: shareable/giftable wishlist (self-hosted public link **+** Throne links).
- **Auto-suggest products** (active product search/scrape with pre-computed sizes).
- Authoritative auto-classification from photos (Kibbe/season are never trusted without user confirmation).

## Current state (verified — reuse these)
- `User.body_measurements` (JSONB) already exists → raw measurements.
- `UserPreference.style_profile` (JSONB), `color_favorites`, `color_avoid` already exist → computed profile + palette.
- `VALID_TYPES` already covers base + intimates + activewear + sleep + accessories (no type-enum expansion needed).
- `ClothingItem` has `type`, `subtype` (free-text `String(50)`), `colors`, `pattern`, `material`, `formality`, `style`, `season`, `fit` — but **no neckline/rise/silhouette/sleeve** attributes, and thin base-category subtype guidance in `clothing_analysis.txt`.
- `item_scorer.py` (`score_items`) + `recommendation_service.py` already score/rank candidates and build the LLM prompt → the integration points.
- Cron worker infra (`app/workers/`) exists (used by nudge/auto-confirm) → the nightly re-tag job.

## Component 0 — Taxonomy + tagging enrichment (foundation)

### Category taxonomy (new backend module `app/taxonomy.py` 💡)
Canonical **category → types** map (single source of truth), e.g.:
`Tops` (t-shirt, top, shirt, blouse, polo, tank-top, sweater, hoodie, cardigan) · `Bottoms` (pants, jeans, shorts, skirt, leggings, joggers) · `Dresses & One-pieces` (dress, jumpsuit, tracksuit) · `Outerwear` (jacket, coat, blazer, vest) · `Footwear` (shoes, sneakers, boots, sandals) · `Intimates` (bra, sports-bra, underwear, briefs, boxers, lingerie, shapewear, tights) · `Activewear` (gym-top, base-layer) · `Sleep & Lounge` (pajamas, robe) · `Swimwear` (swimwear) · `Accessories` (hat, scarf, belt, bag, tie, jewelry, watch, sunglasses, gloves, socks).
- **`category` is derived from `type`** (reverse lookup) — no new stored column; `type` stays canonical, existing items slot in automatically.
- Exposed via `GET /api/v1/taxonomy` for the frontend cascading selector (category → type → subtype).
- Used to validate AI `type` and to scope subtype suggestions.

### Subtype vocabulary expansion (`clothing_analysis.txt`, no migration — subtype is free-text)
Add rich subtype guidance for the under-served base categories, e.g. `top/t-shirt` → crop, tube/bandeau, halter, camisole, peplum, wrap, henley, muscle, boxy; `shirt/blouse` → button-down, oxford, flannel, camp-collar, tie-front, tunic; `dress` → (existing) + bodycon, shirt-dress, tea, slip; `skirt` → (existing) + circle, godet. Keep an authoritative subtype list per type in `taxonomy.py`.

### New cut attributes (small additive migration + prompt)
Add optional `ClothingItem` columns (all nullable): `neckline`, `rise`, `silhouette`, `sleeve_length` (`String(30)` each). Add them to `clothing_analysis.txt` output with controlled vocabularies:
- `neckline`: crew, v-neck, scoop, boat, halter, off-shoulder, turtleneck, cowl, square, sweetheart, collared, strapless, null.
- `rise`: high, mid, low, null (bottoms only).
- `silhouette`: a-line, bodycon, straight, wrap, fit-and-flare, shift, pencil, pleated, oversized, tailored, skinny, bootcut, wide-leg, null.
- `sleeve_length`: sleeveless, short, three-quarter, long, null.
Lazy population: new uploads get them; the scorer uses them when present and falls back to `type`+`subtype`+`fit` when absent.

### Nightly full re-tag worker
A cron job (mirror the auto-confirm/nudge worker pattern) that re-runs AI tagging over items missing the new attributes (or all items, batched, throttled for the single-GPU Ollama — respects `max_jobs=1`), backfilling attributes + richer subtypes overnight. Idempotent; resumable; logs progress.

## Component 1 — Style profile pipeline (2a)

### Inputs
- **Measurements** (`User.body_measurements` JSONB, cm/in toggle 💡): height, shoulders, bust, **underbust** (for bra sizing), waist, hips, wrist (frame), inseam or torso length (vertical). Weight optional.
- **Guided hints** (steer the VLM, kept short): undertone (vein colour / gold-vs-silver), contrast level, 2–3 Kibbe self-perceptions.
- **Photo** (optional, local-only): feeds the VLM draft only.

### Determination
- **Deterministic (measurements):**
  - **Shape** from ratios: hourglass (bust≈hips, waist/hip < ~0.75, shoulder≈hip) · pear/triangle (hips > shoulders+bust) · inverted-triangle (shoulders/bust > hips) · rectangle (bust≈waist≈hips, low waist definition) · apple (waist ≥ bust/hips).
  - **Vertical line** from height + torso:leg → petite / balanced / tall (+ short/long torso).
  - **Frame** from wrist:height → small / medium / large.
- **AI-drafted (hints + photo → `qwen3.5:4b`):** colour-season (spring/summer/autumn/winter + depth/clarity) + Kibbe-lean (dramatic/natural/romantic/classic/gamine tilt). Returned as a **draft**.
- **User confirm/edit:** a review screen shows the deterministic results (locked, editable) + the AI draft (clearly labelled "AI suggestion — please confirm"); the user adjusts and saves. Saved profile → `UserPreference.style_profile`.

### Flattering-rule base (the shared brain — `app/style_rules.py` 💡)
Curated, editable mapping used by BOTH the scorer and the guidance generator:
- **shape → recommended** {silhouette, neckline, rise, waist-emphasis, fabric-weight, proportions} + **avoid**.
- **season → palette** (harmonising colour set) + contrast guidance.
- **frame/vertical → scale** guidance (print size, structure, hem points).
Encodes well-documented style knowledge; versioned in the repo so it can be tuned without code changes to the engine.

## Component 2 — Deep outfit-engine integration (2a)
- **`item_scorer.py` gains a `style_fit` component** per item given the profile:
  - **colour-season match**: item `colors`/`primary_color` vs the season palette → boost/penalty.
  - **shape-flatter**: item `type`/`silhouette`/`neckline`/`rise`/`sleeve_length`/`fit` vs the shape's recommended/avoid sets → boost/penalty (graceful when attributes absent).
  - Combined into the existing score. 💡 **Down-rank, never hard-exclude** — the user owns the item.
- **Recommendation prompt** gets concise profile context ("soft-autumn pear, balanced vertical, medium frame — favour defined waists, V/scoop necks, structured shoulders; ease off volume at the hip").
- Scoring is behind the profile: users without a profile get today's behaviour unchanged.

## Component 3 — Standalone styling guidance (2a)
- A profile page renders an LLM-generated guide grounded in `style_rules.py` + the user's profile: flattering cuts, necklines, rises, silhouettes, fabrics, colour palette, and proportions to emphasise/avoid. Deterministic rule text + LLM phrasing (so it's consistent with the scorer, not free-floating).

## Component 4 — Buy-Advisor (2b)
- **Gap analysis** over the user's OWN ready closet: identify missing core pieces/categories that (a) would complete the most new outfits (reuse outfit-completeness logic) AND (b) suit the profile's shape + season. Output ranked buy-recs: `{category, type, recommended silhouette/neckline/rise, colour (from palette), rationale}` (LLM writes the rationale from the rule base).
- **Retailer search links**: each rec ships prefilled search-URL deep-links (marketplace/retailer search for the described item) — no scraping, always works.
- **Paste-to-size**: the user pastes a real product URL → backend fetches the page → `qwen3.5:4b` parses the size chart → maps the user's measurements → **size recommendation + confidence**. Best-effort: on unreadable/blocked pages, fall back to generic S/M/L from measurements, with a visible caveat.
- **Bra/intimate sizing**: compute a **baseline** band (from underbust) + cup (bust − underbust) in a chosen system (💡 US default, US/UK/EU toggle); refine per-product from the manufacturer chart on paste. UI states clearly that brand variance makes this a starting point.
- 💡 Buy-recs computed **on-demand** (no persistence yet — the wishlist model arrives with 2c).

## Data model summary
| Store | Content | New? |
|-------|---------|------|
| `User.body_measurements` (JSONB) | raw measurements incl. underbust | reuse |
| `UserPreference.style_profile` (JSONB) | shape, vertical, frame, season, kibbe_lean, palette, confirmed flags, size-system | reuse |
| `ClothingItem.neckline/rise/silhouette/sleeve_length` | cut attributes | **new (additive, nullable)** |
| `app/taxonomy.py`, `app/style_rules.py` | category→type→subtype map; flattering rules | new config modules |

## API surface (new, `/api/v1`)
- `GET /taxonomy` — category → type → subtype (for the cascading selector + validation).
- `GET/PUT /style-profile` — read/update the user's measurements + confirmed profile.
- `POST /style-profile/draft` — measurements + hints + (optional) photo → AI draft (unsaved) for the confirm screen.
- `GET /style-profile/guidance` — the styling guide text.
- `GET /buy-advisor` — ranked buy-recs + search links.
- `POST /buy-advisor/size` — `{product_url}` → parsed-chart size recommendation + confidence (falls back to measurement-based).
- Reuse existing item create/update to accept the new attributes.

## Delivery
Backend-first (a testable API, like B1), then a **frontend plan** (Plan 2): the cascading category/type/subtype selector, the Style-Profile onboarding wizard (measurements → hints → photo → confirm draft → save), the Guidance view, and the Buy-Advisor view (recs + search links + paste-to-size).

## Testing notes
- Deterministic shape/frame/vertical: unit tests over ratio boundaries.
- Bra baseline: unit tests over underbust/bust → band/cup in each system.
- `style_fit` scoring: profile + item attribute matrices (incl. missing-attribute fallback).
- Buy-Advisor gap analysis: closet fixtures → expected missing pieces.
- Size-chart parse: fixture HTML charts → parsed sizes; unreadable → graceful fallback.
- Taxonomy: every `type` maps to exactly one category; subtype lists valid.

## Roadmap (explicitly out of this spec)
- **2c — shareable/giftable wishlist**: self-hosted public read-only wishlist link (uses the existing tunnel + auth) **and** per-item Throne links for anonymous gifting. Needs a persistent wishlist/`StyleRecommendation` model.
- **Auto-suggest products**: active product search/scrape with pre-computed sizes (needs a shopping-search source; flakier, less private).
- Optional type additions if desired later: `bodysuit`, `romper/playsuit`, `two-piece/set`.

---
*Designed with help of Claude (Anthropic, Opus 4.8).*
