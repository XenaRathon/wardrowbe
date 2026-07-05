# B1 Calendar + Sharing — Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the frontend for B1 — a two-way outfit calendar (week grid + day detail with plan/confirm/log), household item ownership (owner selector + private toggle), a Mine/Partner/Everyone closet filter, and the nudge deep-link — matching the app's existing conventions.

**Architecture:** New `app/dashboard/calendar/` page + `use-calendar.ts` React Query hook over the existing `/api/v1/calendar` endpoints; a day-detail dialog (shadcn Dialog). Owner selector + `is_private` switch added to the existing add-item and item-detail dialogs. A closet owner filter on the wardrobe page, backed by a small additive backend change (`owner_scope` on `GET /items` using the existing `usable_items_filter`).

**Tech Stack:** Next.js 14 App Router, TypeScript, Tailwind + shadcn/ui (Radix), TanStack React Query v5, `lib/api.ts` client, NextAuth token via `setAccessToken`, `sonner` toasts, `lucide-react` icons. Backend: FastAPI/SQLAlchemy (Task 1 only).

**Branch:** `feat/outfit-calendar-sharing` (has the B1 backend).

## Global Constraints

- Match EXISTING patterns exactly (do not introduce a new design system): shadcn `components/ui/*` primitives, `cn()` from `lib/utils`, `lucide-react` icons, `sonner` `toast`, React Query `lib/hooks/use-*.ts` conventions (see `use-items.ts`/`use-outfits.ts` for the token-attach + invalidate pattern), pages under `app/dashboard/<name>/page.tsx` (`'use client'`), nav entries in `components/sidebar.tsx` + `components/mobile-nav.tsx`.
- API calls go through `lib/api.ts` (`api.get/post/patch/delete` at paths under `/api/v1`, base path prepended by the client). Attach the token via the existing `useSession()` + `setAccessToken(session.accessToken)` pattern (see any `use-*` hook).
- Dates: the calendar works in the user's local dates; format `YYYY-MM-DD` for the API (which is timezone-aware server-side). Use the same date utilities the app already uses if present.
- Frontend gate (run from `frontend/`): `npm run build` MUST pass (Next build = typecheck) AND `npm run test` (vitest) MUST pass with no regressions. Add a focused vitest test for any new PURE logic (date-range math, owner-filter param); JSX-heavy components are verified by the build/typecheck (visual QA happens post-deploy).
- Backend Task 1 only: run `bash /home/xenarathon/claude/wardrowbe/backend/run-tests.sh <args>` for backend tests. Never `python -m pytest` directly.
- Commit after each task.

---

## File Structure

- `backend/app/api/items.py` + `backend/app/services/item_service.py` + `backend/app/schemas/item.py` — `owner_scope` on the list route (Task 1).
- `frontend/lib/hooks/use-calendar.ts` (new) — calendar query + plan/confirm/wear/remove mutations.
- `frontend/lib/types.ts` — add calendar types + `owner_user_id`/`is_private` on `Item`; `owner_scope` on item filters.
- `frontend/app/dashboard/calendar/page.tsx` (new) — week/month grid.
- `frontend/components/calendar/day-cell.tsx`, `day-detail-dialog.tsx` (new).
- `frontend/components/sidebar.tsx` + `components/mobile-nav.tsx` — nav entry.
- `frontend/components/add-item-dialog.tsx` + `components/item-detail-dialog.tsx` — owner selector + private switch.
- `frontend/app/dashboard/wardrobe/page.tsx` — owner filter control.
- `frontend/lib/hooks/use-items.ts` — thread `owner_scope`.
- Tests: `frontend/tests/calendar.test.ts` (new), extend existing where pure logic added.

---

## Task 1 (backend): `owner_scope` on `GET /items`

**Files:**
- Modify: `backend/app/schemas/item.py` (`ItemFilter` add `owner_scope`)
- Modify: `backend/app/services/item_service.py` (`get_list` honors it)
- Modify: `backend/app/api/items.py` (`list_items` accepts + passes it)
- Test: `backend/tests/test_item_owner_sharing.py` (extend)

**Interfaces:**
- Consumes: `FamilyService.get_member_ids`, `usable_items_filter` (both exist from the B1 backend).
- Produces: `GET /api/v1/items?owner_scope=mine|family|all` — `mine` (default) = current behaviour (`user_id == current_user.id`); `family`/`all` = the shared household pool via `usable_items_filter(user, member_ids)` (respects `is_private`).

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_item_owner_sharing.py`:
```python
@pytest.mark.asyncio
async def test_list_items_owner_scope_family_includes_partner_shared(db_session, client):
    from app.api.auth import create_access_token
    from app.models.family import Family
    from app.models.item import ClothingItem, ItemStatus
    from uuid import uuid4
    fam = Family(id=uuid4(), name="F", created_by=uuid4(), invite_code=str(uuid4())[:8])
    db_session.add(fam); await db_session.commit()
    me = await _user(db_session, fam.id)      # helper already in this file
    her = await _user(db_session, fam.id)
    shared = ClothingItem(id=uuid4(), user_id=her.id, image_path="x.jpg", type="jacket",
                          status=ItemStatus.ready, is_private=False)
    db_session.add(shared); await db_session.commit()
    headers = {"Authorization": f"Bearer {create_access_token(me.external_id)}"}
    mine = await client.get("/api/v1/items?owner_scope=mine", headers=headers)
    fam_r = await client.get("/api/v1/items?owner_scope=family", headers=headers)
    mine_ids = [i["id"] for i in mine.json()["items"]]
    fam_ids = [i["id"] for i in fam_r.json()["items"]]
    assert str(shared.id) not in mine_ids
    assert str(shared.id) in fam_ids
```
*(Confirm the list-response shape `{"items":[...]}` and the `_user` helper by reading the file; adjust if the response key differs.)*

- [ ] **Step 2: Run to verify it fails**

Run: `bash backend/run-tests.sh tests/test_item_owner_sharing.py -v`
Expected: FAIL (owner_scope ignored — partner item absent from family scope).

- [ ] **Step 3: Implement**

- `ItemFilter` (schemas/item.py): add `owner_scope: str = "mine"`.
- `get_list(user_id, filters, ...)` → change signature to `get_list(user, filters, ...)` (pass the User, not just id) OR add a `member_ids`/`scope` param. Simplest: accept `owner_scope` + `member_ids` and swap the base `where`:
  ```python
  if filters.owner_scope in ("family", "all"):
      base = usable_items_filter(user, member_ids)   # member_ids from FamilyService
  else:
      base = ClothingItem.user_id == user.id
  query = select(ClothingItem).where(base).options(...)
  ```
  Keep all other filters unchanged.
- `list_items` (api/items.py): read `owner_scope` from the query (add a `Query` param), compute `member_ids = await FamilyService(db).get_member_ids(current_user)` when scope != mine, and call the service accordingly. Match how the route currently calls `get_list`.

- [ ] **Step 4: Run to verify it passes**

Run: `bash backend/run-tests.sh tests/test_item_owner_sharing.py tests/test_items.py -q`
Expected: PASS (new test + existing item tests green).

- [ ] **Step 5: Commit**
```bash
git add backend/app/schemas/item.py backend/app/services/item_service.py backend/app/api/items.py backend/tests/test_item_owner_sharing.py
git commit -m "feat(sharing): owner_scope (mine|family|all) on GET /items via usable_items_filter"
```

---

## Task 2: Calendar hook + week/month page + nav

**Files:**
- Create: `frontend/lib/hooks/use-calendar.ts`
- Modify: `frontend/lib/types.ts` (calendar types)
- Create: `frontend/app/dashboard/calendar/page.tsx`, `frontend/components/calendar/day-cell.tsx`
- Modify: `frontend/components/sidebar.tsx`, `frontend/components/mobile-nav.tsx`
- Test: `frontend/tests/calendar.test.ts`

**Interfaces:**
- Produces:
  - Types: `DayRecord { date: string; primary: OutfitBrief | null; extras: OutfitBrief[]; repeat_warnings?: string[] }`, `OutfitBrief { id: string; occasion: string; scheduled_for: string | null; worn_at: string | null; name: string | null; item_ids: string[] }`.
  - `useCalendar(start: string, end: string)` → React Query over `api.get<DayRecord[]>('/calendar', { params: { start, end } })`.
  - Pure helper `weekRange(anchor: Date): { start: string; end: string; days: string[] }` and `monthRange(anchor: Date)` (exported for tests).

- [ ] **Step 1: Write the failing test**

Create `frontend/tests/calendar.test.ts`:
```ts
import { describe, it, expect } from 'vitest';
import { weekRange, monthRange } from '@/lib/hooks/use-calendar';

describe('calendar ranges', () => {
  it('weekRange returns 7 consecutive days covering the anchor', () => {
    const { start, end, days } = weekRange(new Date('2026-07-08T12:00:00'));
    expect(days).toHaveLength(7);
    expect(days[0]).toBe(start);
    expect(days[6]).toBe(end);
    expect(days).toContain('2026-07-08');
  });
  it('monthRange spans the whole month', () => {
    const { start, end } = monthRange(new Date('2026-07-15T12:00:00'));
    expect(start).toBe('2026-07-01');
    expect(end).toBe('2026-07-31');
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run (from `frontend/`): `npm run test -- calendar`
Expected: FAIL (module/exports missing).

- [ ] **Step 3: Implement the hook + helpers**

Create `frontend/lib/hooks/use-calendar.ts`. Implement `weekRange`/`monthRange` as pure date helpers (format `YYYY-MM-DD` in LOCAL time — write a small `fmt(d: Date)` that pads month/day, do NOT use `toISOString()` which is UTC and can shift the day). `useCalendar` follows the exact `use-items.ts` pattern (`useSession` + `setAccessToken` + `useQuery`, `queryKey: ['calendar', start, end]`, `enabled` when a token exists). Add the calendar types to `lib/types.ts`.

- [ ] **Step 4: Build the page + day cell**

Create `frontend/app/dashboard/calendar/page.tsx` (`'use client'`): a header with week/month toggle + prev/next/today nav (`useState` anchor date), a responsive grid of `DayCell`s for the range from `useCalendar`. `DayCell` (`components/calendar/day-cell.tsx`) shows the date, the primary look's first item thumbnail (reuse `OutfitCard`/item image pattern — read `components/outfits/*` or `OutfitCalendar` for the thumbnail approach), an "extras" count badge, and an amber dot when `repeat_warnings?.length`. Clicking a cell opens the day-detail dialog (Task 3 — for now wire an `onSelect(date)` prop, dialog added next task). Match the app's card/spacing conventions. Add a `Calendar` (lucide `CalendarDays`) nav entry to `components/sidebar.tsx`'s `navigation` array and mirror in `components/mobile-nav.tsx`.

- [ ] **Step 5: Verify**

Run (from `frontend/`): `npm run test -- calendar` (PASS) then `npm run build` (PASS — typecheck + build clean).

- [ ] **Step 6: Commit**
```bash
git add frontend/lib/hooks/use-calendar.ts frontend/lib/types.ts frontend/app/dashboard/calendar frontend/components/calendar/day-cell.tsx frontend/components/sidebar.tsx frontend/components/mobile-nav.tsx frontend/tests/calendar.test.ts
git commit -m "feat(calendar): week/month calendar page + use-calendar hook + nav"
```

---

## Task 3: Day-detail dialog (plan / confirm / log / remove)

**Files:**
- Create: `frontend/components/calendar/day-detail-dialog.tsx`
- Modify: `frontend/lib/hooks/use-calendar.ts` (mutations)
- Modify: `frontend/app/dashboard/calendar/page.tsx` (wire the dialog)
- Test: extend `frontend/tests/calendar.test.ts` if any pure logic added

**Interfaces:**
- Consumes: `useCalendar`, the outfits list (`use-outfits.ts` — to pick an outfit to plan/log), `use-family` (for the wearer selector).
- Produces mutations in `use-calendar.ts`: `usePlanDay()` → `POST /calendar/{date}/plan {outfit_id}`; `useConfirmDay()` → `POST /calendar/{date}/confirm`; `useLogWear()` → `POST /calendar/{date}/wear {outfit_id, worn_by_user_id?, occasion?}`; `useRemoveWear()` → `DELETE /calendar/{date}/wear/{outfit_id}`. Each `invalidateQueries(['calendar'])` (and `['items']`/`['analytics']` since wear changes stats) on success + `toast`.

- [ ] **Step 1: Implement the mutations**

Add the four mutations to `use-calendar.ts` mirroring `use-items.ts` mutation style (token attach, `mutationFn` calling `api.post/delete`, `onSuccess` invalidations + `toast.success`, error handled by the global MutationCache).

- [ ] **Step 2: Build the dialog**

Create `day-detail-dialog.tsx` (shadcn `Dialog`): props `{ date: string | null; open; onOpenChange }`. Shows the day's primary + extras (from a `useCalendar` single-day query or passed-in `DayRecord`). Controls: **Plan** (an outfit picker — reuse an existing outfit-select/`ItemPicker` pattern from `components/shared/*` or a simple `Select` over `useOutfits`), **Confirm worn** (calls `useConfirmDay`; shown when a plan exists and isn't worn), **Log what I actually wore** (outfit picker + optional wearer `Select` from `use-family` → `useLogWear`), and per-extra **Remove** (`useRemoveWear`). Show `repeat_warnings` as amber `Badge`s. Match the app's dialog layout/spacing.

- [ ] **Step 3: Wire into the page**

In `calendar/page.tsx`, hold `selectedDate` state; `DayCell onSelect` sets it + opens the dialog.

- [ ] **Step 4: Verify**

Run (from `frontend/`): `npm run test` (PASS) then `npm run build` (PASS).

- [ ] **Step 5: Commit**
```bash
git add frontend/components/calendar/day-detail-dialog.tsx frontend/lib/hooks/use-calendar.ts frontend/app/dashboard/calendar/page.tsx
git commit -m "feat(calendar): day-detail dialog with plan/confirm/log/remove"
```

---

## Task 4: Owner selector + private toggle on item dialogs

**Files:**
- Modify: `frontend/lib/types.ts` (`Item.owner_user_id`, `Item.is_private`; create/update payload types)
- Modify: `frontend/components/add-item-dialog.tsx`, `frontend/components/item-detail-dialog.tsx`
- Modify: `frontend/lib/hooks/use-items.ts` (send `owner_user_id`/`is_private`)

**Interfaces:**
- Consumes: `use-family` (family members for the Select). Backend already accepts `owner_user_id` on create + `user_id`/`is_private` on update (B1 backend).
- Produces: add-item posts `owner_user_id`; item-detail patches `user_id` (owner reassignment) + `is_private`.

- [ ] **Step 1: Implement**

Add `owner_user_id?: string` and `is_private?: boolean` to the `Item` type + create/update payloads in `lib/types.ts`. In `add-item-dialog.tsx`, add an **Owner** `Select` (family members from `use-family`; default the current user; only shown when the user has a family with >1 member) and an **is_private** `Switch`; include `owner_user_id`/`is_private` in the FormData/create payload (read how the dialog builds the payload). In `item-detail-dialog.tsx`, add the same Owner `Select` (as `user_id` on the PATCH) + `is_private` `Switch`, threaded through the existing edit state + PATCH payload (the dialog already round-trips `subtype`; follow that). Ensure `use-items.ts` `useCreateItem`/`useUpdateItem` forward the new fields.

- [ ] **Step 2: Verify**

Run (from `frontend/`): `npm run test` (PASS) then `npm run build` (PASS — the new fields typecheck through the payloads).

- [ ] **Step 3: Commit**
```bash
git add frontend/lib/types.ts frontend/components/add-item-dialog.tsx frontend/components/item-detail-dialog.tsx frontend/lib/hooks/use-items.ts
git commit -m "feat(sharing): item owner selector + private toggle on add/edit dialogs"
```

---

## Task 5: Closet owner filter on the wardrobe page

**Files:**
- Modify: `frontend/lib/hooks/use-items.ts` (thread `owner_scope`)
- Modify: `frontend/lib/types.ts` (`ItemFilters.owner_scope`)
- Modify: `frontend/app/dashboard/wardrobe/page.tsx` (segmented control)

**Interfaces:**
- Consumes: Task 1's `GET /items?owner_scope=`.
- Produces: a **Mine / Partner / Everyone** control on the wardrobe toolbar that sets `owner_scope` (`mine`/`family` — "Partner" maps to `family` with a client-side owner filter, or `all`; keep it simple: Mine=`mine`, Everyone=`family`). Passed into `useItems`.

- [ ] **Step 1: Implement**

Add `owner_scope?: 'mine' | 'family'` to the items filter type + include it in `useItems`' query params + `queryKey` (so it refetches on change). In `wardrobe/page.tsx`, add a small segmented control (shadcn `Tabs` or a Button group) next to the existing filter toolbar bound to a `useState` that feeds `useItems`. Only show it when the user has a family (from `use-family`). Default `mine`.

- [ ] **Step 2: Verify**

Run (from `frontend/`): `npm run test` (PASS) then `npm run build` (PASS).

- [ ] **Step 3: Commit**
```bash
git add frontend/lib/hooks/use-items.ts frontend/lib/types.ts frontend/app/dashboard/wardrobe/page.tsx
git commit -m "feat(sharing): Mine/Everyone closet owner filter on wardrobe"
```

---

## Task 6: Nudge deep-link to today's day-detail

**Files:**
- Modify: `frontend/app/dashboard/calendar/page.tsx` (open today's dialog from a query param)
- (Reference) the backend nudge notification's deep-link URL (set in the wear-nudge worker).

**Interfaces:**
- Produces: visiting `/dashboard/calendar?day=today` (or `?day=YYYY-MM-DD`) auto-opens that day's detail dialog.

- [ ] **Step 1: Implement**

In `calendar/page.tsx`, read the `day` search param (`useSearchParams`); if present, set the anchor to that date's week and open the day-detail dialog for it on mount. `today` resolves to the local today. This makes the evening nudge notification (which links users to log what they wore) land directly on the log screen.

- [ ] **Step 2: Verify**

Run (from `frontend/`): `npm run build` (PASS). (No new pure logic to unit-test; the param handling is verified by build + manual QA post-deploy.)

- [ ] **Step 3: Commit**
```bash
git add frontend/app/dashboard/calendar/page.tsx
git commit -m "feat(calendar): nudge deep-link opens today's day-detail"
```

---

## Final
- [ ] From `frontend/`: `npm run test` + `npm run build` both green. From repo root, backend: `bash backend/run-tests.sh -q` (Task 1 didn't regress; note the 1 pre-existing OIDC test failure exists on this branch until it merges with main's OIDC fix).
- [ ] Do NOT push/deploy — merges with the Styler frontend then a single combined deploy.

## Self-Review (author checklist — completed)
- **Spec coverage:** week/month calendar → Task 2; day detail plan/confirm/log/remove + repeat warnings → Task 3; owner selector + private → Task 4; Mine/Everyone closet filter (+ backend gap-closer) → Tasks 1+5; nudge deep-link → Task 6.
- **Placeholders:** none for logic (hook/date math/backend shown as code); JSX-heavy components reference the exact existing components to match (`use-items.ts`, `OutfitCalendar`, add-item-dialog) rather than inlining full JSX — appropriate fidelity for frontend, with the build/typecheck gate catching integration errors.
- **Type consistency:** `useCalendar`/`weekRange`/`monthRange`, `DayRecord`/`OutfitBrief`, the four calendar mutations, `owner_scope`, `owner_user_id`/`is_private` used consistently across tasks.

## Out of scope
Styler frontend (separate plan); the wear-analytics dashboard already exists and consumes the now-accurate data; visual/pixel QA (post-deploy).
