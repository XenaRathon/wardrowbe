# Outfit Calendar + Wear-Log + Household Closet Sharing — Design Spec

**Feature ID:** B1
**Date:** 2026-07-04
**Status:** Approved design, pending implementation plan
**Fork:** xenarathon/wardrowbe (F.A.S.C.)

## Overview

Add a two-way outfit **calendar** (plan outfits forward + log what was actually
worn), make the wear-log **household-aware** so partners who share clothes can
draw from each other's closets, and let an item's **owner be assigned** to any
family member at scan time. This turns the wear data the app already collects
into an honest, shared record that later features (cost-per-wear, declutter,
trip-packing) build on.

### Goals
- A **week-default** calendar (month toggle) showing one primary look per day.
- Plan outfits for future dates; log/confirm what was actually worn per day.
- One **primary** outfit per day + optional **extra** logged wears (e.g. a gym fit).
- **Household closet sharing**: within a `Family`, all items are usable by every
  member by default; individual items can be marked private.
- **Assignable owner**: when scanning an item, choose whose closet it belongs to.
- Wear attribution: record **who wore** an item, separately from who **owns** it.
- A low-effort daily loop: auto-confirm planned days; evening nudge on unplanned days.
- "Don't repeat within N days" planning warning (falls out of the wear-log).

### Non-goals (deferred — see Out of Scope)
- Full laundry state machine ("in wash → unavailable"). A `needs_wash` flag already
  exists; the full state machine is a separate feature (Bundle A6).
- Cost-per-wear UI and the `price` field (Bundle A2). B1 only makes the wear *data*
  accurate and shared.
- Cross-family / social sharing beyond one household.
- The Body-Type Styler + Buy-Advisor (tracked separately as spec #2).

## Current state (what already exists — reuse, don't rebuild)

- `Outfit.scheduled_for: date | None` — a planned date already exists.
- `Outfit.status` (`OutfitStatus`: pending/sent/viewed/accepted/rejected/skipped/
  expired) — **no `planned`/`worn` value**; we add a `worn_at` date instead of new
  statuses.
- `ItemHistory(item_id, outfit_id, worn_at, occasion, notes)` — the dated wear log.
- `ItemService`'s wear-logging method already creates an `ItemHistory` row and
  increments `wear_count`, sets `last_worn_at`, and updates wash tracking
  (`wears_since_wash`, `needs_wash`, `DEFAULT_WASH_INTERVALS`). **This is the single
  source of truth we extend** (add `worn_by_user_id`).
- A **second, inconsistent** wear path exists in the outfit-feedback endpoint
  (`api/outfits.py`, `request.worn`) that bulk-updates `wear_count` but does **not**
  write `ItemHistory`. B1 unifies on the `ItemService` path (see Cleanup).
- `Family` + `FamilyInvite` models + `User.family_id` — household grouping exists.
  `FamilyOutfitRating` lets members rate each other's outfits.
- `analytics.py` (`GET /api/v1/analytics`) already surfaces never-worn /
  most-/least-worn stats — B1's data flows into it for free.
- Notification worker (`send_notification`, `reset_schedule_trigger`, retry) +
  `Schedule` (per-weekday reminder) — reused for the evening nudge.
- API prefix is `/api/v1`.

## Data model changes (small, additive — no destructive migration)

| Model | Change | Purpose |
|-------|--------|---------|
| `ClothingItem` | `is_private: bool = False` | Hide item from family sharing |
| `ClothingItem` | (existing `user_id` becomes **owner-assignable** — no schema change, just editable) | Scan on behalf of a partner |
| `ItemHistory` | `worn_by_user_id: UUID \| None` (FK users) | Who wore it (vs `item.user_id` = owner) |
| `Outfit` | `worn_at: date \| None` (indexed) | Mark a primary as confirmed-worn on a date |
| indexes | `(user_id, scheduled_for)`, `(user_id, worn_at)`, `ItemHistory(worn_at)` | Calendar range queries |

All columns are nullable/defaulted → additive Alembic migration, no backfill required.

## Calendar model & behavior

### Representing a day
A day's record is derived from `Outfit` rows, not a new heavyweight table:
- **Primary (planned):** the `Outfit` with `scheduled_for = <date>` (at most one per
  user per date — enforced at the service layer).
- **Primary (worn):** confirming the plan sets that outfit's `worn_at = <date>` and
  cascades per-item logging.
- **Actual-differs / extras:** additional `Outfit` rows with `worn_at = <date>` and
  `scheduled_for = NULL`. Multiple extras allowed.
- **Primary selection for the grid** (tie-break, service layer): confirmed-worn plan
  → else the plan → else the earliest logged wear that day.

### Views
- **Week strip (default):** 7 days, one primary look per day, mobile-friendly.
- **Month grid (toggle):** compact thumbnails.
- **Day detail:** primary + extras, each with wearer + occasion; add/confirm/replace.

### Daily logging loop
- **Planned day:** at day's end the planned outfit auto-confirms (`worn_at` set,
  items logged) unless the user changed it. Silent, zero-effort.
- **Unplanned day:** evening **nudge** (default 20:00, user-configurable) via the
  existing notification system — "What did you wear today?" → confirm/pick.
- Auto-confirm runs as a scheduled worker job (reuse the notifications/cron worker),
  operating in each user's timezone (`get_user_today`).

### Wear cascade (single source of truth)
Confirming/logging an outfit for a date calls the existing `ItemService` wear method
for each item, passing `worn_by_user_id = <the wearer>` and `worn_at = <date>`. This
guarantees one `ItemHistory` row per item-wear, correct `wear_count`/`last_worn_at`,
and wash tracking — feeding `analytics.py` automatically.

## Household closet sharing

### Visibility
- Sharing scope = the user's `Family`.
- **All items shared by default**; `is_private = True` hides an item from other members
  (still visible to its owner).
- A reusable **visibility filter** (service/query helper): "items I can use" =
  items where `user_id IN family_member_ids AND (is_private = False OR user_id = me)`.
  Applied consistently in: item listing, outfit recommendation candidate pool,
  manual outfit building, pairing suggestions, and the calendar.
- **Owner filter** in the UI: Mine / Partner / Everyone.

### Assignable owner
- The add-item form has an **owner selector** defaulting to the current user; any
  family member can be chosen. Owner is editable later in item detail.
- Only members of the same `Family` are assignable.
- AI tagging is unchanged (runs regardless of owner); owner only determines which
  closet the item lands in and whose stats it counts toward.

### Wear attribution
- `ItemHistory.worn_by_user_id` records the wearer. Owner = `item.user_id`.
- Item-level `wear_count`/`last_worn_at` still increment on the item regardless of
  who wore it (they describe the garment, not a person).
- Per-person wear stats are derivable from `ItemHistory.worn_by_user_id` when needed.

## AI / recommendation integration
- Outfit recommendation and pairing draw from the **shared pool** (family-visible
  items) by default, honoring the owner filter when set. This reuses the visibility
  helper above; the existing `recommendation_service` / `pairing_service` candidate
  queries are updated to use it.
- No model/prompt change; `qwen3.5:4b` stays the tagging/text model.

## "Don't repeat within N days"
- When planning or confirming, warn (non-blocking) if any item was worn in the last
  **N days** (default 3). Computed from `ItemHistory.worn_at`.
- Excluded types: shoes, and accessory-slot items (jewelry/watch/belt/bag/sunglasses).
- N and the toggle live in user preferences (`UserPreference`).

## API surface (new/changed, all under `/api/v1`)
- `GET /calendar?start=&end=` — day records (primary + extras) for a date range
  (week/month). Household-aware.
- `POST /calendar/{date}/plan` — set/replace the planned primary outfit for a date.
- `POST /calendar/{date}/confirm` — confirm the plan as worn (cascade).
- `POST /calendar/{date}/wear` — log an actual/extra worn outfit for a date
  (`{outfit_id | item_ids, worn_by_user_id, occasion, is_extra}`).
- `DELETE /calendar/{date}/wear/{outfit_id}` — remove a logged wear (reverses cascade).
- `PATCH /items/{id}` — extend to accept `user_id` (owner reassignment) and `is_private`.
- Item create — accept optional `owner_user_id`.
- Reuse existing `GET /analytics` unchanged.

## Notifications
- Add an "evening wear nudge" job to the notification worker, gated per user by a
  preference (enabled + time). Sends via each user's configured channel(s)
  (ntfy/email/etc.), deep-linking to today's day-detail.

## Cleanup (bundled, keeps the fork honest)
- Unify the two wear-logging paths: make the outfit-feedback `worn` path call the
  same `ItemService` wear method so every confirmed wear produces an `ItemHistory`
  row (today it silently doesn't). Guard against double-logging when a feedback-worn
  outfit is also calendar-confirmed (idempotency by `(item_id, outfit_id, worn_at)`).

## Migration
- One additive Alembic revision: `is_private`, `worn_by_user_id`, `Outfit.worn_at`,
  new indexes. No data backfill. Safe forward-only.

## Testing
- Unit: visibility helper (private/own/partner matrix); primary-selection tie-break;
  wear cascade writes exactly one `ItemHistory` w/ correct `worn_by`; don't-repeat
  window incl. exclusions; owner reassignment restricted to same family.
- Integration: plan→confirm→analytics reflects the wear; log unplanned extra;
  partner wears owner's item → item stats + attribution correct; private item hidden
  from partner's candidate pool + recommendations.
- Idempotency: auto-confirm + manual confirm don't double-count.
- Regression: existing outfit-feedback `worn` still increments once after unification.

## Out of scope (explicit)
- Laundry availability state machine (Bundle A6) — only the existing `needs_wash`
  flag is surfaced, not enforced in suggestions.
- `price` / cost-per-wear UI (Bundle A2).
- Social/cross-household sharing; resale; care reminders.

## Follow-on
- Spec #2 — **Body-Type Styler + Buy-Advisor** (measurements→shape, style guidance,
  gap-analysis buy recommendations, local-Ollama). Independent; brainstorm next.

---
*Designed with help of Claude (Anthropic, Opus 4.8).*
