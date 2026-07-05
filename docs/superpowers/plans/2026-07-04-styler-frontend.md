# Styler — Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Styler frontend — a cascading category→type→subtype item selector, an extended measurement form, a style-profile page + create/confirm wizard, styling guidance, and a buy-advisor view — matching the app's existing conventions.

**Architecture:** New React Query hooks (`use-taxonomy`, `use-style-profile`, `use-buy-advisor`) over the already-built backend endpoints (`/taxonomy`, `/style-profile[/draft|/guidance]`, `/buy-advisor[/size]`). A reusable cascading `TypeSelector` replaces the flat type `Select` in the item dialogs. New `app/dashboard/style/` and `app/dashboard/buy-advisor/` pages + nav entries. The settings measurement grid gains `bust/underbust/shoulders/wrist`.

**Tech Stack:** Next.js 14 App Router, TypeScript, Tailwind + shadcn/ui (Radix), TanStack React Query v5, `lib/api.ts`, NextAuth token via `setAccessToken`, `sonner` toasts, `lucide-react`.

**Branch:** `feat/styler-tagging` (has the Styler backend).

## Global Constraints

- Match EXISTING patterns (see B1 frontend + `use-items.ts`/`use-user.ts`/`use-preferences.ts`): shadcn `components/ui/*`, `cn()`, lucide icons, `sonner` `toast`, React Query `use-*` hooks with the `useSession()`+`setAccessToken(session.accessToken)` token-attach idiom, pages under `app/dashboard/<name>/page.tsx` (`'use client'`), nav entries in `components/sidebar.tsx` + `components/mobile-nav.tsx`.
- API via `lib/api.ts` (`api.get/post/put/delete` at `/api/v1` paths). Radix `Select` MUST NOT use empty-string values (use a sentinel, as done elsewhere).
- Frontend gate (from `frontend/`): `npx tsc --noEmit` MUST be clean (the REAL typecheck gate — `next build` has `ignoreBuildErrors: true`), `npm run test` (vitest) MUST pass, and `npm run build` should succeed. Add a focused vitest test for any new PURE logic (taxonomy filtering, wizard step gating); JSX is verified by tsc + post-deploy QA.
- Any page using `useSearchParams` must be Suspense-wrapped (Next 14).
- Commit after each task.

---

## File Structure

- `frontend/lib/hooks/use-taxonomy.ts` (new) — `GET /taxonomy`.
- `frontend/components/type-selector.tsx` (new) — cascading category→type→subtype picker.
- `frontend/components/add-item-dialog.tsx` + `components/item-detail-dialog.tsx` — use `TypeSelector`.
- `frontend/app/dashboard/settings/page.tsx` — add measurement fields.
- `frontend/lib/hooks/use-style-profile.ts` (new) — get/put/draft/guidance.
- `frontend/lib/hooks/use-buy-advisor.ts` (new) — recommendations + size.
- `frontend/app/dashboard/style/page.tsx` (new) — profile + guidance; `components/style/profile-wizard.tsx` (new).
- `frontend/app/dashboard/buy-advisor/page.tsx` (new).
- `frontend/components/sidebar.tsx` + `components/mobile-nav.tsx` — nav entries.
- `frontend/lib/types.ts` — taxonomy/profile/buy-advisor types.
- Tests: `frontend/tests/taxonomy.test.ts`, `frontend/tests/style-profile.test.ts` (new).

---

## Task 1: Taxonomy hook + cascading TypeSelector

**Files:**
- Create: `frontend/lib/hooks/use-taxonomy.ts`, `frontend/components/type-selector.tsx`
- Modify: `frontend/lib/types.ts` (taxonomy types)
- Test: `frontend/tests/taxonomy.test.ts`

**Interfaces:**
- Produces:
  - Types `TaxonomyCategory { category: string; types: { type: string; subtypes: string[] }[] }`, `Taxonomy { categories: TaxonomyCategory[] }`.
  - `useTaxonomy()` → React Query over `api.get<Taxonomy>('/taxonomy')` (long `staleTime` — taxonomy is static).
  - Pure helpers (exported for tests): `categoryOfType(tax, type): string | undefined`, `subtypesOfType(tax, type): string[]`.
  - `<TypeSelector value={{type, subtype}} onChange={(v)=>...} taxonomy={tax} />` — three shadcn `Select`s (Category → Type filtered to category → Subtype filtered to type); picking a category resets type/subtype; type is optional ("AI will detect"); subtype optional.

- [ ] **Step 1: Write the failing test**

Create `frontend/tests/taxonomy.test.ts`:
```ts
import { describe, it, expect } from 'vitest';
import { categoryOfType, subtypesOfType } from '@/lib/hooks/use-taxonomy';

const tax = { categories: [
  { category: 'Intimates', types: [{ type: 'bra', subtypes: ['push-up','balconette'] }] },
  { category: 'Tops', types: [{ type: 't-shirt', subtypes: ['crop'] }, { type: 'top', subtypes: [] }] },
]};

describe('taxonomy helpers', () => {
  it('categoryOfType finds the parent category', () => {
    expect(categoryOfType(tax, 'bra')).toBe('Intimates');
    expect(categoryOfType(tax, 't-shirt')).toBe('Tops');
    expect(categoryOfType(tax, 'nope')).toBeUndefined();
  });
  it('subtypesOfType returns the type\'s subtypes', () => {
    expect(subtypesOfType(tax, 'bra')).toEqual(['push-up','balconette']);
    expect(subtypesOfType(tax, 'top')).toEqual([]);
    expect(subtypesOfType(tax, 'nope')).toEqual([]);
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run (from `frontend/`): `npm run test -- taxonomy`
Expected: FAIL (module/exports missing).

- [ ] **Step 3: Implement the hook + helpers**

Create `use-taxonomy.ts`: `useTaxonomy()` mirrors `use-items.ts` (token attach + `useQuery`, `queryKey: ['taxonomy']`, `staleTime: Infinity`). `categoryOfType`/`subtypesOfType` are pure lookups over the `Taxonomy` shape. Add the types to `lib/types.ts`.

- [ ] **Step 4: Build the TypeSelector**

Create `components/type-selector.tsx`: a client component taking `{ type?: string; subtype?: string; onChange: (v: {type?: string; subtype?: string}) => void }` + `taxonomy` (or call `useTaxonomy()` internally). Renders Category `Select` (derives current category from `categoryOfType`), Type `Select` (options = the category's types; changing category clears type+subtype), Subtype `Select` (options = `subtypesOfType`; hidden/disabled when none). Use a sentinel for "unset". Match the app's Select styling + labels.

- [ ] **Step 5: Verify**

Run (from `frontend/`): `npm run test -- taxonomy` (PASS) then `npx tsc --noEmit` (clean) + `npm run build`.

- [ ] **Step 6: Commit**
```bash
git add frontend/lib/hooks/use-taxonomy.ts frontend/components/type-selector.tsx frontend/lib/types.ts frontend/tests/taxonomy.test.ts
git commit -m "feat(styler): taxonomy hook + cascading category/type/subtype selector"
```

---

## Task 2: Use TypeSelector in the item dialogs

**Files:**
- Modify: `frontend/components/add-item-dialog.tsx`, `frontend/components/item-detail-dialog.tsx`

**Interfaces:**
- Consumes: `TypeSelector`, `useTaxonomy`.
- Produces: both dialogs use `TypeSelector` (type + subtype) in place of the flat `CLOTHING_TYPES` `Select`; `subtype` is now user-settable (add-item sends it in the create FormData; item-detail PATCHes it — it already round-trips `subtype`).

- [ ] **Step 1: Implement**

In `add-item-dialog.tsx`, replace the flat type `Select` with `<TypeSelector value={{type, subtype}} onChange={...}/>` wired to the existing `type` state + a new `subtype` state; append `subtype` to the create `FormData` (backend accepts it). In `item-detail-dialog.tsx`, replace the flat edit `Select` with `TypeSelector` bound to the edit state's `type`/`subtype` (both already in the PATCH payload — the dialog currently sets `subtype` invisibly; now it's user-editable). Keep the "AI will detect if empty" affordance (type optional). Remove now-unused `CLOTHING_TYPES` imports if fully replaced (or leave if still referenced elsewhere — check).

- [ ] **Step 2: Verify**

Run (from `frontend/`): `npm run test` (PASS) then `npx tsc --noEmit` (clean) + `npm run build`.

- [ ] **Step 3: Commit**
```bash
git add frontend/components/add-item-dialog.tsx frontend/components/item-detail-dialog.tsx
git commit -m "feat(styler): cascading type+subtype selector in add/edit item dialogs"
```

---

## Task 3: Extend the measurement form

**Files:**
- Modify: `frontend/app/dashboard/settings/page.tsx`

**Interfaces:**
- Produces: `BODY_MEASUREMENT_FIELDS` gains `bust`, `underbust`, `shoulders`, `wrist` (numeric, cm, with the existing unit toggle) so the backend's deterministic shape/frame/vertical analysis can populate. Existing `chest`/`waist`/`hips`/`inseam`/`height`/`weight` stay.

- [ ] **Step 1: Implement**

In `settings/page.tsx`, add `bust`, `underbust`, `shoulders`, `wrist` to the `BODY_MEASUREMENT_FIELDS` array (match the existing field-descriptor shape: key, label, min/max, unit type). They flow through the existing measurement grid + unit conversion + `useUpdateUserProfile().mutateAsync({ body_measurements })` save with no other change. Add a short helper caption noting these enable the Style Profile analysis (and that `underbust` is for bra sizing). Keep `chest` (the backend aliases `chest`→`bust` when `bust` is absent, so both are fine).

- [ ] **Step 2: Verify**

Run (from `frontend/`): `npm run test` (PASS) then `npx tsc --noEmit` (clean) + `npm run build`.

- [ ] **Step 3: Commit**
```bash
git add frontend/app/dashboard/settings/page.tsx
git commit -m "feat(styler): add bust/underbust/shoulders/wrist to measurement form"
```

---

## Task 4: Style-profile hooks + profile & guidance page

**Files:**
- Create: `frontend/lib/hooks/use-style-profile.ts`, `frontend/app/dashboard/style/page.tsx`
- Modify: `frontend/lib/types.ts` (profile types), `frontend/components/sidebar.tsx`, `frontend/components/mobile-nav.tsx`

**Interfaces:**
- Produces:
  - Types `StyleProfile { body_shape: string|null; vertical_line: string|null; frame: string|null; color_season: string|null; kibbe_lean: string|null; palette: string[]; season_confirmed: boolean; kibbe_confirmed: boolean; measurements?: Record<string,any> }`, `StyleDraft { color_season: string|null; kibbe_lean: string|null }`, `Guidance { summary: string; recommended: Record<string,string[]>; avoid: Record<string,string[]>; palette: string[] }`.
  - `useStyleProfile()` → `GET /style-profile`; `useUpdateStyleProfile()` → `PUT /style-profile`; `useStyleDraft()` → mutation `POST /style-profile/draft {hints, image?}`; `useGuidance()` → `GET /style-profile/guidance`.
  - `app/dashboard/style/page.tsx`: shows the profile (shape/vertical/frame/season/kibbe/palette swatches) + guidance (recommended/avoid/palette + summary), with an "Edit / Set up profile" button that opens the wizard (Task 5). Nav entry "Style Profile" (lucide `Sparkles`).

- [ ] **Step 1: Implement the hooks**

Create `use-style-profile.ts` with the four hooks mirroring `use-preferences.ts`/`use-items.ts` conventions (token attach; queries with `['style-profile']`/`['style-profile','guidance']` keys; mutations invalidate `['style-profile']` + `toast`).

- [ ] **Step 2: Build the page + nav**

`app/dashboard/style/page.tsx` (`'use client'`): render the profile via `useStyleProfile` (Cards for shape/vertical/frame/season/kibbe; palette as colour swatch chips using the colour names) and guidance via `useGuidance` (recommended/avoid as labelled chip lists, palette swatches, the `summary` text). Handle the empty-profile state (prompt to set it up). Add the "Style Profile" nav entry to `sidebar.tsx` + `mobile-nav.tsx`.

- [ ] **Step 3: Verify**

Run (from `frontend/`): `npm run test` (PASS) then `npx tsc --noEmit` (clean) + `npm run build`.

- [ ] **Step 4: Commit**
```bash
git add frontend/lib/hooks/use-style-profile.ts frontend/app/dashboard/style/page.tsx frontend/lib/types.ts frontend/components/sidebar.tsx frontend/components/mobile-nav.tsx
git commit -m "feat(styler): style-profile hooks + profile & guidance page + nav"
```

---

## Task 5: Profile setup wizard

**Files:**
- Create: `frontend/components/style/profile-wizard.tsx`
- Modify: `frontend/app/dashboard/style/page.tsx` (open the wizard)
- Test: `frontend/tests/style-profile.test.ts` (wizard step-gating pure logic, if extracted)

**Interfaces:**
- Consumes: `useStyleDraft`, `useUpdateStyleProfile`, `useUser` (measurements), `useStyleProfile`.
- Produces: `<ProfileWizard open onOpenChange />` — a shadcn `Dialog` multi-step flow: (1) measurements check (link to settings if missing shape-relevant keys), (2) guided hints (undertone select: cool/warm/neutral; contrast: low/medium/high; 2-3 Kibbe self-perception toggles), (3) optional photo upload, (4) "Get AI suggestion" → `useStyleDraft` → shows the deterministic shape/vertical/frame (read-only, from `useStyleProfile` which the backend computes on measurements-save) + the AI-drafted `color_season`/`kibbe_lean` (editable Selects), (5) Save → `useUpdateStyleProfile({color_season, kibbe_lean, palette?, season_confirmed:true, kibbe_confirmed:true})`.

- [ ] **Step 1: Implement**

Create `profile-wizard.tsx` with `useState` step index + a small pure `canAdvance(step, state)` helper (export it if you add a test). Steps as above; the AI-draft step calls `useStyleDraft.mutateAsync({ hints, image })` and pre-fills the editable season/kibbe Selects with the draft (advisory — the user confirms/edits). On save, PUT the confirmed fields. Match the app's dialog/stepper styling (there may be an onboarding wizard to mirror — check `app/onboarding/page.tsx`). Wire the page's "Edit / Set up profile" button to open it.

- [ ] **Step 2: Verify**

Run (from `frontend/`): `npm run test` (PASS — incl. any `canAdvance` test) then `npx tsc --noEmit` (clean) + `npm run build`.

- [ ] **Step 3: Commit**
```bash
git add frontend/components/style/profile-wizard.tsx frontend/app/dashboard/style/page.tsx frontend/tests/style-profile.test.ts
git commit -m "feat(styler): style-profile setup wizard (measurements/hints/photo/draft/confirm)"
```

---

## Task 6: Buy-Advisor page

**Files:**
- Create: `frontend/lib/hooks/use-buy-advisor.ts`, `frontend/app/dashboard/buy-advisor/page.tsx`
- Modify: `frontend/lib/types.ts` (buy-advisor types), `frontend/components/sidebar.tsx`, `frontend/components/mobile-nav.tsx`

**Interfaces:**
- Produces:
  - Types `BuyRec { role: string; type: string; silhouette: string|null; color: string|null; rationale: string; search_links: { retailer: string; url: string }[] }`, `SizeResult { size: string; confidence: string; source: string }`.
  - `useBuyAdvisor()` → `GET /buy-advisor` (returns `{recommendations: BuyRec[]}`); `useSizeForUrl()` → mutation `POST /buy-advisor/size {product_url, product_type?}`.
  - `app/dashboard/buy-advisor/page.tsx`: recommendation Cards (type + recommended silhouette/colour + rationale + retailer search-link buttons) and a "Find my size" panel (paste a product URL + optional type → `useSizeForUrl` → shows size + confidence + source, with a note that it's a starting point). Nav entry "Buy Advisor" (lucide `ShoppingBag`).

- [ ] **Step 1: Implement the hooks**

Create `use-buy-advisor.ts`: `useBuyAdvisor` query (`['buy-advisor']`) + `useSizeForUrl` mutation, both with token attach; mutation surfaces errors via the global handler (503 on AI-down is already handled server-side/globally). Add types to `lib/types.ts`.

- [ ] **Step 2: Build the page + nav**

`app/dashboard/buy-advisor/page.tsx` (`'use client'`): map `recommendations` to Cards (rationale + `search_links` as `Button asChild`+`<a target="_blank" rel="noopener">`); a size panel with an `Input` for the URL, optional type `Select`, a submit button, and a result display (size/confidence/source, styled by confidence). Handle empty/loading. Add the "Buy Advisor" nav entry to `sidebar.tsx` + `mobile-nav.tsx`.

- [ ] **Step 3: Verify**

Run (from `frontend/`): `npm run test` (PASS) then `npx tsc --noEmit` (clean) + `npm run build`.

- [ ] **Step 4: Commit**
```bash
git add frontend/lib/hooks/use-buy-advisor.ts frontend/app/dashboard/buy-advisor frontend/lib/types.ts frontend/components/sidebar.tsx frontend/components/mobile-nav.tsx
git commit -m "feat(styler): buy-advisor page (recs + search links + paste-to-size)"
```

---

## Final
- [ ] From `frontend/`: `npm run test` + `npx tsc --noEmit` + `npm run build` all green. Backend untouched by this plan (all endpoints exist).
- [ ] Do NOT push/deploy — merges with the B1 frontend (+ OIDC fix on main) then a single combined deploy.

## Self-Review (author checklist — completed)
- **Spec coverage:** cascading category→type→subtype selector → Tasks 1-2; measurement keys (bust/underbust/shoulders/wrist) → Task 3; style-profile + guidance display → Task 4; profile wizard (measurements/hints/photo/draft/confirm) → Task 5; buy-advisor (recs + search links + paste-to-size) → Task 6.
- **Placeholders:** none for logic (hooks/helpers/types shown); JSX pages reference the exact existing patterns (use-items token idiom, shadcn Select/Dialog/Card, nav array shape) rather than inlining full JSX — appropriate for frontend, with tsc/vitest gating.
- **Type consistency:** `useTaxonomy`/`categoryOfType`/`subtypesOfType`/`TypeSelector`, `useStyleProfile`/`useStyleDraft`/`useGuidance`/`useUpdateStyleProfile`, `useBuyAdvisor`/`useSizeForUrl`, and the `StyleProfile`/`Guidance`/`BuyRec`/`SizeResult` types used consistently across tasks.

## Out of scope
Shareable/giftable wishlist + auto-suggest products (roadmap 2c); cut-attribute (neckline/rise/silhouette/sleeve) edit controls in item-detail (optional polish — the AI sets them; the styler reads them); pixel/visual QA (post-deploy).
