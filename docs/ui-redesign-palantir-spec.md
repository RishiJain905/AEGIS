# AEGIS Command — Palantir-Style UI Redesign Specification

Status: **SPEC ONLY**. Nothing in this document has been implemented. No product code, styling, or token file has been changed as part of authoring this spec. This is a theme, layout, and interaction redesign — it must not alter functionality, data flow, wiring, routes, or component APIs. Every button, mutation, query, and keyboard shortcut described elsewhere in the codebase keeps working exactly as it does today; only how things look and how dense/precise the layout feels should change.

Author's method: walked the running app at `http://localhost:3000` in a fresh dev-login session (Admin Alpha), inventoried every operator-facing surface, and read the current design-system source in `packages/ui/src` and `apps/web`. File paths below are exact and current as of this writing.

## 1. Design principles

Target aesthetic: a blend of Palantir **Gotham** (dense, dark, mission-console) and **Foundry/Maven** (cleaner data-app chrome, light-mode-capable, more restrained chip/badge language). Five principles govern every decision below:

1. **Precision over decoration.** The current UI leans on radial glows, soft gradients, and generous rounding (`--aegis-radius-lg: 0.875rem`, panel gradients like `linear-gradient(145deg, var(--aegis-surface-panel), var(--aegis-surface-elevated))`). Palantir surfaces read as flat, hairline-bordered, almost architectural. Redesign direction: **flatten** panel/card backgrounds to a single surface color, **tighten** the radius scale by roughly 40%, and **replace** glow-shadows with 1px hairline borders plus a very small ambient shadow only on truly elevated layers (dialogs, drawers, dropdowns).
2. **Density is a feature.** Operators are triaging incidents across dozens of assets; UI chrome should never be the biggest thing on screen. Reduce vertical padding in list rows and table cells, tighten label letter-spacing, and let data (IDs, timestamps, counts) set the visual rhythm via monospace tabular figures.
3. **Color is reserved for state.** The existing semantic system (`packages/ui/src/tokens/status-tokens.ts`, `packages/ui/src/semantic/risk.ts`, `packages/ui/src/semantic/status.ts`) already does this correctly — status/risk color never appears as decoration. Keep that discipline. The redesign narrows the *chrome* accent (the cyan used for buttons, focus rings, active nav) to a single restrained hue so it doesn't compete visually with risk/status color, which must always read as the "something needs attention" signal.
4. **Legible at a glance, dense on inspection.** Display type (`--aegis-font-display`) marks section/panel titles so they scan fast; monospace (`--aegis-font-mono`) marks anything an operator might copy-paste or correlate (IDs, timestamps, checksums, sequence numbers) — already partially done (`apps/web/src/app/globals.css:45-51` forces mono on `code, kbd, time`), just needs to be applied more consistently (see §4).
5. **Quiet by default, loud only for signal.** Idle/normal state should be nearly monochrome. Reserve saturated color for risk bands, node status, and destructive actions. Loading/empty/error/disconnected states (`packages/ui/src/composed/state-shells.tsx`) already follow this — keep it as the reference pattern for every new empty state.

## 2. Design tokens

All values below map onto the **existing** CSS custom-property names in `packages/ui/src/styles/tokens.css` — no new token names, no renamed Tailwind utility classes in `packages/ui/src/tokens/tokens.ts`. Where a value changes, only the value inside `:root { --aegis-*: ... }` changes; every component that already references `var(--aegis-surface-panel)` etc. inherits the new look automatically.

### 2.1 Theme strategy: dark stays primary, light is added

The app is currently dark-only (`html { color-scheme: dark; }` in `apps/web/src/app/globals.css:14-18`, no light branch anywhere in the token file). Palantir's Foundry/Maven line ships both. Add a light theme **without disturbing dark as the default**:

- Keep the dark values as the `:root` defaults (dark-first product, matches the "command console" framing on the sign-in page: *"Defensive operations, in one field of view."*).
- Add a `:root[data-theme="light"]` block in `packages/ui/src/styles/tokens.css` overriding the same variable names.
- `html { color-scheme: light dark; }` once both branches exist, so native form controls (scrollbars, checkboxes) pick the right rendering.
- Theme switch is a `data-theme` attribute toggle (consistent with how the Artifact runtime and most design systems key light/dark), driven by a new preference in `apps/web/features/shell/contracts/panel-preferences.ts` (a **UI preference**, not a functional change — persists like the existing rail-collapsed/mobile-rail preferences already do). Default to dark; respect OS `prefers-color-scheme` only if the operator has never chosen explicitly.
- Surface the toggle in the Operations rail footer (see §5.1) and on the Design System page's token showcase, not buried in Admin.

### 2.2 Color tokens

**Surfaces** (`packages/ui/src/styles/tokens.css:1-10`)

| token | dark (current, keep) | light (new) |
|---|---|---|
| `--aegis-surface-base` | `#05090e` | `#f3f5f7` |
| `--aegis-surface-canvas` | `#04080d` | `#eef1f3` |
| `--aegis-surface-elevated` | `#09121b` | `#ffffff` |
| `--aegis-surface-panel` | `#0d1722` | `#ffffff` |
| `--aegis-surface-rail` | `#071019` | `#eceff2` |
| `--aegis-surface-overlay` | `#122230` | `#ffffff` |
| `--aegis-surface-raised` | `#172a3a` → flatten to `#111d29` (see §1.1) | `#f7f9fa` |
| `--aegis-surface-hover` | `#142535` | `#e7ebee` |

Rationale for the dark `--aegis-surface-raised` change: today `Card`, `Panel` headers, and `MetricTile` all use a diagonal gradient from `surface-raised` to `surface-elevated` (`packages/ui/src/composed/card.tsx:16`, `packages/ui/src/composed/panel.tsx:59`, `packages/ui/src/composed/metric-tile.tsx:25`). Flattening `raised` closer to `elevated` and dropping the gradient (see §3) removes the "glossy panel" look in favor of a flat one with only a hairline top highlight.

**Text** (`tokens.css:12-20`)

| token | dark | light |
|---|---|---|
| `--aegis-text-primary` | `#f0f6fa` (keep) | `#10161c` |
| `--aegis-text-secondary` | `#b3c2cd` (keep) | `#3d4954` |
| `--aegis-text-muted` | `#8297a8` (keep) | `#5f6d78` |
| `--aegis-text-faint` | `#617788` (keep) | `#8794a0` |
| `--aegis-text-inverse` | `#041016` (keep) | `#f3f5f7` |

**Operator accent** (`tokens.css:22-26`) — narrowed from a bright cyan glow to a more restrained "signal blue," Foundry-style:

| token | dark | light |
|---|---|---|
| `--aegis-accent-cyan` | `#4fb8de` (was `#59c9ea`; slightly desaturated) | `#0d6e90` |
| `--aegis-accent-strong` | `#7fd3ee` (was `#91e2f7`) | `#0a5875` |
| `--aegis-accent-soft` | `#0d3040` (keep) | `#e3f1f6` |
| `--aegis-accent-line` | `#2b7188` (keep) | `#4a94ac` |

**Spacing, borders, radius, depth, focus** — spacing stays untouched (the 4px grid in `tokens.css:28-38` is already good practice and needs no redesign). Borders and radius tighten:

| token | dark | light |
|---|---|---|
| `--aegis-border-default` | `#263a49` (keep) | `#d7dde2` |
| `--aegis-border-subtle` | `#182834` (keep) | `#e6eaed` |
| `--aegis-border-strong` | `#3b586c` (keep) | `#b7c1c8` |
| `--aegis-border-highlight` | `rgb(185 226 244 / 0.10)` (was `0.13`, slightly quieter) | `rgb(16 22 28 / 0.06)` |
| `--aegis-radius-sm` | `0.25rem` (was `0.375rem`) | same |
| `--aegis-radius-md` | `0.375rem` (was `0.625rem`) | same |
| `--aegis-radius-lg` | `0.5rem` (was `0.875rem`) | same |
| `--aegis-radius-xl` | `0.625rem` (was `1.125rem`) | same |

**Depth** (`tokens.css:50-63`) — replace glow-heavy shadows with flatter, single-purpose ones. Keep the same four token names, new values:

```css
/* dark */
--aegis-shadow-panel: inset 0 1px 0 rgb(255 255 255 / 0.03), 0 0 0 1px rgb(38 58 73 / 0.6), 0 2px 6px rgb(0 0 0 / 0.24);
--aegis-shadow-panel-hover: inset 0 1px 0 rgb(255 255 255 / 0.04), 0 0 0 1px var(--aegis-accent-line), 0 2px 8px rgb(0 0 0 / 0.28);
--aegis-shadow-control: inset 0 1px 0 rgb(255 255 255 / 0.04), 0 0 0 1px rgb(38 58 73 / 0.5);
--aegis-shadow-dialog: 0 0 0 1px var(--aegis-border-strong), 0 20px 48px rgb(0 0 0 / 0.5);
--aegis-shadow-rail: 1px 0 0 var(--aegis-border-default);

/* light */
--aegis-shadow-panel: 0 0 0 1px var(--aegis-border-default), 0 1px 3px rgb(16 22 28 / 0.06);
--aegis-shadow-panel-hover: 0 0 0 1px var(--aegis-accent-line), 0 2px 6px rgb(16 22 28 / 0.08);
--aegis-shadow-control: 0 0 0 1px var(--aegis-border-default);
--aegis-shadow-dialog: 0 0 0 1px var(--aegis-border-strong), 0 16px 40px rgb(16 22 28 / 0.16);
--aegis-shadow-rail: 1px 0 0 var(--aegis-border-default);
```

The point: no more soft ambient glow (`0 14px 34px rgb(0 0 0 / 0.28)`) on every panel. Elevation now comes from a crisp 1px edge, matching Palantir's flat-panel look. Reserve a visible drop shadow for things that are genuinely floating above the page (`DialogContent`, `DrawerContent`, `DropdownMenuContent`, `TooltipContent` — all in `packages/ui/src/primitives/`).

**Focus** (`tokens.css:65-68`) — keep `--aegis-focus-width: 2px`; dark ring stays `#7adbf4` → tune to `#5fc3e6` to match the desaturated accent; light theme ring `#0a5875`.

**Risk bands** (`tokens.css:70-78`, consumed by `packages/ui/src/semantic/risk.ts`)

| band | dark fg / bg (keep) | light fg / bg (new, tuned for ≥4.5:1 on white) |
|---|---|---|
| low | `#63d6a2` / `#0b291f` | `#16794f` / `#e3f5ec` |
| medium | `#f1c257` / `#30240c` | `#8a5b06` / `#fbf0d9` |
| high | `#ff9b55` / `#321a0d` | `#a8460d` / `#fbe7d8` |
| critical | `#ff7078` / `#351116` | `#c0242f` / `#fce4e5` |

**Status** (`tokens.css:80-98`, consumed by `status.ts` / `Badge`) — same fg colors as the matching risk band conceptually (normal↔low, suspicious↔medium, compromised↔critical), plus:

| status | dark (keep) | light (new) |
|---|---|---|
| under-investigation | `#68d0ee` / `#0d2d3b` | `#0d6e90` / `#e3f1f6` |
| contained | `#9aa8ff` / `#1c2140` | `#4c4fc4` / `#e9e9fb` |
| loading | `#9db1c0` / `#142331` | `#5f6d78` / `#eef1f3` |
| disconnected | `#bac5cd` / `#18232d` | `#5f6d78` / `#e6eaed` |
| empty | `#9db1c0` / `#111d27` | `#5f6d78` / `#eef1f3` |

**Every value above is a calibrated starting point, not a final answer.** Before shipping, run the light-theme pairs through the same contrast check the a11y suite already uses (see §8) — several (medium/high risk on light) sit close to the 4.5:1 line and may need ±2% lightness adjustment once rendered.

### 2.3 Typography scale

Font stacks stay as-is — `--aegis-font-sans`, `--aegis-font-display`, `--aegis-font-mono` (`tokens.css:13-15`) already separate UI text, headings, and data. Two changes:

1. **Widen the fallback stacks for cross-platform parity.** `Bahnschrift` and `Aptos` are Windows-only; `Cascadia Code` ships with Windows Terminal/VS Code but isn't universal. Anyone on macOS/Linux currently silently falls back several tiers deep. Add explicit cross-platform fallbacks *before* the generic keyword, still system/self-hosted only (no CDN, per CSP):
   ```css
   --aegis-font-sans: 'Aptos', 'Segoe UI Variable', 'Segoe UI', 'Inter', system-ui, sans-serif;
   --aegis-font-display: 'Bahnschrift', 'DIN Alternate', 'Aptos Display', 'Segoe UI', 'Inter', sans-serif;
   --aegis-font-mono: 'Cascadia Code', 'Cascadia Mono', 'SFMono-Regular', 'JetBrains Mono', Consolas, 'Menlo', monospace;
   ```
   If the product owner wants pixel-identical typography across OSes, self-host one variable display face (e.g. bundle a woff2 under `apps/web/public/fonts/` and add an `@font-face` in `globals.css`) — this stays CSP-compliant (`font-src 'self'` already permits local files per `apps/web/next.config.ts:28`) but is an explicit follow-up decision, not assumed here.
2. **Formalize a numeric scale** on top of the existing `typographyTokens` (`packages/ui/src/tokens/tokens.ts:9-20`, currently `uiXs` 12px → `uiXl` 20px). Add display-specific sizes so panel/page titles stop ad-hoc-declaring `text-sm font-semibold uppercase` inline (as `Panel.tsx:64` and `Card.tsx:24` do today):

   | role | size / line-height | weight | tracking | family |
   |---|---|---|---|---|
   | `display-xl` (page hero, sign-in headline) | 28px / 34px | 600 | -0.01em | display |
   | `display-lg` (page title, e.g. "Incident queue") | 20px / 26px | 600 | 0 | display |
   | `display-md` (panel/section title) | 13px / 18px | 600 | 0.06em, uppercase | display |
   | `body-lg` | 15px / 22px | 400 | 0 | sans |
   | `body-md` (default UI text) | 14px / 20px | 400 | 0 | sans |
   | `body-sm` | 13px / 18px | 400 | 0 | sans |
   | `eyebrow` (labels, table headers, badges) | 11px / 16px | 600 | 0.08em, uppercase | sans |
   | `mono-md` (IDs, checksums) | 13px / 18px | 500 | 0.01em, tabular-nums | mono |
   | `mono-sm` (timestamps, sequence numbers) | 11px / 16px | 500 | 0.02em, tabular-nums | mono |

   Add these as new keys on `typographyTokens` (`displayXl`, `displayLg`, `displayMd`, `bodyLg`, `bodyMd`, `bodySm`, `eyebrow`, `monoMd`, `monoSm`) so components reference `typographyTokens.displayMd` instead of repeating `'text-[0.6875rem] font-semibold uppercase tracking-[0.075em]'` inline (currently duplicated near-verbatim in `panel.tsx:64`, `data-table.tsx:44`, `metric-tile.tsx:32`, `graph-controls/index.tsx:109`).

### 2.4 Spacing, density, elevation

- Spacing scale (`tokens.css:28-38`, 4px grid) is already correct for a dense console — no change.
- `densityTokens` (`tokens.ts:58-63`) already exposes compact/comfortable/spacious — audit usage so **tables, queues, and the timeline default to `compact`**, and only detail panels (incident detail, after-action, reports) use `comfortable`. Today `Panel` defaults to `comfortable` everywhere (`panel.tsx:46`), which is why the incident queue and admin tables (see screenshots, §6) feel slightly loose for how much operators scan them.
- Elevation model: 3 layers only.
  1. **Base** — page background (`surface-base`/`surface-canvas`).
  2. **Panel** — cards, panels, tables, the graph frame. Flat surface + hairline border (`shadow-panel`).
  3. **Overlay** — dialogs, drawers, dropdowns, tooltips, the mobile rail drawer. Real shadow (`shadow-dialog`), sits above a scrim.
  No 4th "raised-above-panel" layer — remove the extra gradient step currently used in `MetricTile`/`Card`/`Panel` header backgrounds.

## 3. Component-by-component restyle guidance

All in `packages/ui/src/`. None of these need prop/API changes — only class-name/token changes inside each file.

- **`primitives/button.tsx`** — `buttonVariants` (lines 8-38): drop the `active:scale-[0.96]` micro-bounce (reads as a mobile-app affordance, not console chrome) in favor of a background/border color shift only. Reduce `shadow-[var(--aegis-shadow-control)]` reliance since the flattened token already does less. Keep all five variants (default/destructive/outline/ghost/secondary) — they map cleanly to Palantir's primary/danger/secondary/tertiary button language already.
- **`primitives/badge.tsx`** — keep pill shape (`rounded-full`, line 10) as the one deliberately "soft" shape in the system, reserved for status/risk chips only, reinforcing point 3 in §1 (color = state, and state gets the one rounded shape). No structural change.
- **`primitives/alert.tsx`** — the `border-l-[3px]` left-accent bar (line 7) is a good Palantir-ish pattern, keep. Tighten `rounded-[var(--aegis-radius-md)]` per the new radius scale automatically.
- **`primitives/tabs.tsx`** — `TabsList` background (line 18) should use `surface-elevated` not `surface-elevated` at a lighter step than currently painted (currently blends into `Panel`'s own background too closely in some contexts, e.g. Admin's Users & Roles / Policy / Platform tabs, replay's Normal/Cinematic tabs) — give it one visible step of contrast in both themes.
- **`primitives/dialog.tsx` / `primitives/drawer.tsx`** — reduce overlay opacity slightly (`bg-[rgb(1_5_9_/_0.78)]` → `0.6`) so context behind the modal stays legible (a Palantir habit: overlays dim, they don't blackout). Keep the top-hairline `before:` accent.
- **`primitives/dropdown-menu.tsx` / `primitives/tooltip.tsx`** — both correctly use `surface-overlay` + `shadow-dialog` already; only the tightened radius/shadow tokens from §2 apply automatically. No structural change.
- **`primitives/skeleton.tsx`** — keep as-is; the animated gradient sweep (`aegis-motion-pulse`) is already reduced-motion-aware via `motion.css:52-57`.
- **`composed/card.tsx`** — remove the diagonal gradient background (line 16) in favor of flat `bg-[var(--aegis-surface-panel)]`; keep the `before:` top hairline highlight.
- **`composed/panel.tsx`** — same flattening for the header gradient (line 59) → flat `surface-raised`. Default `density` prop usage should shift to `compact` at call sites for list-like panels (see §2.4); the component API itself doesn't need to change.
- **`composed/data-table.tsx`** — this is the single highest-leverage file for the "dense operational console" feel. Reduce header/cell padding (`px-4 py-3` → `px-3 py-2`, lines 44/74), reduce header font (`text-[0.6875rem]` is already right — keep), and add a `data-testid`-stable zebra-row option (alternating `surface-panel`/`surface-elevated` at ~4% difference) for wide tables like the Admin permission matrix and the Incident queue. Row hover (`hover:bg-[var(--aegis-surface-hover)]`, line 67) stays.
- **`composed/metric-tile.tsx`** — drop the gradient background (line 25) for flat `surface-panel`; keep the left accent bar (`before:` rule) — that's a good Palantir-style "spine" marker for a stat tile. Value typography should use the new `mono-md`/`display` scale rather than raw `text-3xl`.
- **`composed/rail.tsx`** — background gradient (`linear-gradient(180deg, ...)`, line 7) → flat `surface-rail`. Keep the collapse-width transition; it's a nice touch and already `prefers-reduced-motion`-safe via the shared duration tokens.
- **`composed/state-shells.tsx`** — this file is already the best example of the target aesthetic (dashed border, radial-but-restrained background, icon + message + optional retry). Keep the pattern; just flatten its background per §2 and reuse it as the canonical template for any *new* empty/loading/error surface introduced elsewhere (several feature panels roll their own ad hoc "No data" text instead of using `EmptyState` — e.g. `incident-proposals.tsx`'s "No proposals" block visible in the incident-detail screenshot, §6.2 — migrate those to the shared component during implementation).
- **`composed/timeline-mark.tsx`** — keep the connected-dot-and-line structure; it already reads as a proper mission-timeline. Active-state color (`under-investigation` accent, line 26) stays as the one place a status color is allowed to double as an interaction-state color.
- **`graph-controls/index.tsx`** (chrome around the graph, not the graph canvas itself — explicitly in scope) — `GraphSearchInput`, `GraphLayerControls`, `GraphCameraControls`, `GraphIsolationControls`, `GraphOverlayToggle`, `GraphLegend`. All are button/badge/input compositions already using tokens correctly; they inherit the flattened radius/shadow automatically. One concrete change: `GraphLegend`'s swatch glow (`shadow-[0_0_10px_currentColor]`, line 123) is exactly the kind of decorative glow §1 argues against — drop it for a plain 1px ring, keep the shape-coding (circle/diamond/triangle/hexagon/line/ring) which is good semantic design.

## 4. Per-surface layout redesign notes

Every surface below was walked live in this session (`http://localhost:3000`, Admin Alpha dev identity) unless noted.

### 4.1 Sign-in / first-run — `apps/web/src/app/sign-in/page.tsx`, `apps/web/features/auth/sign-in-panel.tsx`

Observed: two-column card (brand/tagline left, form right), a first-run "Create admin account" flow with a "Development identities" picker below it (5 role buttons). Currently sits centered in a large empty viewport with soft background radial gradients (`aegis-command-shell`, `globals.css:82-105`).
Redesign: keep the two-column structure (it reads well, Foundry's own sign-in follows the same split). Flatten the outer card per §3, tighten the vertical rhythm between the four form fields (username/display name/password/confirm), and give the "Development identities" block a visually distinct, slightly recessed treatment (`surface-canvas` background, not the same panel surface as the form) so operators can't mistake dev-login buttons for part of the real auth form — reinforce the existing "LOCAL ONLY" badge with the tightened badge style from §3. Background gridlines (`.aegis-command-shell`, lines 86-96) stay but should be quieter (lower the line opacity ~30%) so they read as texture, not pattern.

### 4.2 Scenarios — `apps/web/src/app/(shell)/scenarios/page.tsx`

Observed: a "Scenario selection" table (name / ID / actions) plus a fixture-backed "Timeline" panel below, inspector on the right showing "No selection." Straightforward; apply the tightened `DataTable` padding (§3) and compact `Panel` density. The "Design system showcase" link currently sits as a bare text link under the table (screenshot, low visual weight) — give it a small `Badge`-style pill treatment so it reads as an intentional secondary entry point, not a stray link.

### 4.3 Active run — `apps/web/features/shell/components/command-centre-shell.tsx` + `visualization-slot.tsx`, `apps/web/features/operational-graph/*`, `apps/web/features/live-run/*`

Observed: `StatusStrip` sticky header (Control link / run id / status / sim time / operator badge), graph frame with Data Layers / Signal Overlays / Investigation Focus / Analysis Actions button groups plus a `GraphLegend`, then the 2D/3D canvas, then the Timeline panel, with Inspector + Incidents + Alerts stacked in the right rail.
Redesign: this is the densest, highest-value screen — apply §3's data-table/metric-tile/panel flattening throughout. The four button-group clusters (Data Layers, Signal Overlays, Investigation Focus, Analysis Actions) currently sit in an unlabeled flat grid (`.graph-command-bar`/`.graph-control-deck`, `globals.css:126-133`); give each cluster a small `eyebrow`-style label (already present per `.graph-control-label`, `globals.css:139-147` — keep, just apply the new type scale) and tighten the gap between clusters so the whole control deck reads as one coherent toolbar rather than four separate boxes. `StatusStrip` (`status-strip.tsx:54`) already backdrop-blurs and sticks — keep that, just swap its ad hoc `bg-[rgb(9_18_27_/_0.94)]` for a token-driven `surface-rail`-at-95%-opacity so it stays in sync with theme switching.

### 4.4 Incidents — queue (`apps/web/src/app/(shell)/incidents/page.tsx`, `features/incidents/components/incident-queue.tsx`) and case detail (`incidents/[incidentId]/page.tsx`, `incident-workspace.tsx`, `incident-detail.tsx`, `incident-triage-timeline.tsx`, `incident-alerts-evidence.tsx`, `incident-proposals.tsx`, `incident-agent-roster.tsx`)

Observed queue: four `MetricTile`-style stat cards (Total/Active/High-Critical/Resolved) above a dense "Open cases" table with severity chip, investigating badge, alert count, age. Observed detail: header strip (status/severity/id/run/opened/updated/linked alerts/pending approvals), triage timeline, response proposals (empty state today), linked alerts & evidence, agent activity roster (Watchtower/Trace/Oracle/Bastion/Warden all "IDLE"), candidate affected assets.
Redesign: the queue's stat row and table are the clearest case for the tightened `DataTable` padding + zebra rows (§3) since rows will only get denser as more incidents open. In the detail view, the six-agent "Agent activity" roster (right rail) is a great candidate for the `eyebrow` label + `mono-sm` timestamp treatment — right now each agent card repeats a generic "IDLE" badge with no visual distinction between agents; give each agent role a fixed 1-letter/2-letter monospace glyph badge (W/T/O/B/W/S for Watchtower/Trace/Oracle/Bastion/Warden/Scribe) consistent with the `RailIdentity` "A" glyph pattern already used in the nav rail (`operations-rail.tsx:92`), so the roster scans as fast as the rail does.

### 4.5 Replay — `apps/web/src/app/(shell)/replay/[runId]/page.tsx`, `features/replay/components/*`, `features/replay/replay-provider.tsx`

Observed: an amber "Historical replay — read-only" banner (mode/read-only/cursor/provenance inline), Normal replay / Cinematic replay tabs, transport controls (Start/Step-/Play/Step+/End/Speed controls/Return to live), a timeline scrubber, then the same graph frame as Active Run but captioned "Historical · sequence N," and a right-rail "Historical inspector" with Replay cursor / Incidents / Evidence / Proposals-Approvals ("Approval mutations are disabled in historical mode") / Reports.
Redesign: the read-only banner is exactly the right pattern (color-coded, explicit, impossible to miss) — keep it, just restyle via the tightened `Alert` variant. The transport control row is currently a flat button strip with no visual grouping between "position" controls (Start/Step/Play/Step/End) and "rate" controls (Speed −/1x/Speed +/0.5x/1x/2x/4x) — add a `Separator` (already exists, `primitives/separator.tsx`, currently unused here) between the two groups. "Return to live" should get the `secondary` button variant with an accent-line border so it's visually distinct from playback controls as the one action that changes context entirely.

### 4.6 After-action — `apps/web/src/app/(shell)/after-action/[runId]/page.tsx`, `features/after-action/use-after-action-queries.ts`

Observed: "After-action review · completed" header with a large letter-grade badge ("B") and score bar (89.3/100, "Passed"), a "Hidden cause revealed" callout, a six-row score breakdown (Detection speed/Evidence coverage/Hypothesis quality/False-positive cost/Response proportionality/Service impact) each with a progress bar + weight/contribution, and a "Score explanation" detail panel with rule/events/evidence references and a "Jump to replay" deep link.
Redesign: this page already has the best "signal over decoration" instinct in the app (a single grade badge, clear bars). Apply §2's flattened progress-bar track color and the `mono-sm` treatment to all the `rule-criterion-*` / `evt_*` / `evidence:*` reference chips (currently plain text, screenshot shows them same weight as prose — should read as copy-able identifiers, matching how `Reports` already treats them, see §4.7).

### 4.7 Reports (SCRIBE) — `apps/web/src/app/(shell)/reports/page.tsx`, `features/reports/{reports-workspace,reports-panel,report-ui}.tsx`

Observed: "Versions" rail (immutable version list, v1/current/Completed) + main report body with title, checksum/created/session metadata row, "Chronology" description, and a "Grounded claims" card grid (Observed fact / Investigation evidence / Oracle hypothesis / Bastion proposal / Warden decision / Agent inference — each a colored eyebrow tag + confidence % + reference chip). This claim-card grid is the strongest existing example of the target density-with-clarity balance — keep the structure, apply the flattened `Card` background and the formal `mono-md` scale to every reference chip (`evt_*`, `evidence:*`, `hyp_*`, `prp_*`) so they read identically to the after-action page's chips (currently two different ad hoc treatments for what's conceptually the same "evidence reference" chip — unify into one `EvidenceChip`-style pattern during implementation, still no new component API needed beyond a shared class/utility).

### 4.8 Admin — `apps/web/src/app/(shell)/admin/page.tsx`, `features/admin/{admin-console,users-panel,policy-panel,platform-panel}.tsx`

Observed: Users & Roles / Policy / Platform tabs. Users & Roles: a 5-row identity table (identity/status/roles/effective permissions). Policy: a role→permission matrix (5 roles × up to 16 permission chips each) plus an "Action classes (0-3)" callout grid (Class 0 Read-only/Class 1 Low impact auto-allowed, Class 2 Operational/Class 3 Critical approval-required) and an "Allowlisted scenario commands" table below the fold.
Redesign: the Policy tab is the densest table in the whole app (permission chips wrap across up to 3 lines per row) — this is the strongest candidate for the compact-density + zebra-row treatment, and the permission chips themselves should shrink to the `eyebrow` scale with tighter horizontal padding so more fit per line without wrapping as aggressively. The four "Action classes" cards already use badge-style "auto-allowed"/"approval required" tags in the top-right corner — good pattern, keep, just apply flattened `Card` background.

### 4.9 Inspector / Context Channel — `apps/web/features/shell/components/inspector-panel.tsx`

Observed: persistent right-rail panel present on every workspace surface (scenarios, active run, incidents, replay, after-action, reports), labeled "Context channel" / "Inspector," defaulting to a centered "No selection" empty state (`EmptyState`-style icon + message), and repurposing its content per-surface (After-action-report-not-ready notice + Incidents + Alerts on Active Run; Historical cursor + Incidents + Evidence + Proposals/Approvals + Reports on Replay).
Redesign: since this rail is reused with very different content per surface, give it one **consistent chrome** (the "Context channel" eyebrow + collapsible `›` affordance already exists, screenshot shows a `›` control top-right — confirm/keep it wired) and let inner cards vary. Apply the flattened `Panel`/`Card` treatment uniformly so switching surfaces doesn't change the rail's structural weight, only its contents.

### 4.10 Design System page — `apps/web/src/app/design-system/page.tsx`

Observed: "Command-Centre Design System" — a live token swatch grid (Surfaces/Text/Operator accent/Risk bands/... , each swatch shows name, `--var()`, hex, and a copy button — 38 live tokens per the page's own caption), rendered outside the operational shell chrome (own "← Back to command centre" link, no rail/status-strip).
Redesign: this page is the natural home for the light/dark theme toggle preview (§2.1) — add a live theme switcher at the top of the token grid so implementers and reviewers can flip themes and see every swatch update in place. Since this page already renders "outside the operational data context" (per its own subtitle) it's also the right place to eventually add a component playground (buttons/badges/alerts/tabs in both themes) — out of scope to build here, but the layout should reserve a section for it (a `## Components` heading below `## Design tokens`) so implementation has a slot to land in.

## 5. Nav rail, status strip, and shell chrome

- **`apps/web/features/shell/components/operations-rail.tsx`** — the `RailIdentity` glyph pattern (line 92: a bordered square with a single bold letter) is the single best "Palantir-ish" detail already in the app. Reuse this exact pattern (bordered glyph box, `accent-soft` background, `accent-line` border) for the per-agent glyphs proposed in §4.4, keeping visual language consistent between "who is AEGIS" (rail) and "which agent is this" (incident roster).
- Add the theme toggle (§2.1) as a small icon button in the rail's identity block or directly above "Collapse rail" — collapsed-rail state should still expose it (icon-only, like the other collapsed nav items already do via `title`/`aria-label`, `operations-rail.tsx:135-136`).
- **`status-strip.tsx`** — keep the sticky+backdrop-blur behavior; swap the hardcoded `bg-[rgb(9_18_27_/_0.94)]` (line 54) for `bg-[var(--aegis-surface-rail)]` at a token-driven opacity so it themes correctly. The `Alert` banners it conditionally renders (offline/reconnecting/stale, lines 109-121) already use the right variant machinery — no change beyond the global `Alert` restyle in §3.

## 6. Motion guidance

- Keep the existing token-driven durations/easings (`packages/ui/src/tokens/motion-tokens.ts`, `packages/ui/src/styles/motion.css`) — they're already well-designed: `instant/fast/normal/slow` (0/120/200/320ms), three easing curves, and a global `prefers-reduced-motion` override (`motion.css:11-26`) that zeroes every transition/animation duration and forces `scroll-behavior: auto`. **Do not introduce any new animation that bypasses these tokens.**
- Remove `active:scale-[0.96]` from `Button` (§3) — it's the one motion effect in the system not gated through the duration tokens' transition list explicitly for `transform` scale on press; a Palantir-style console prefers a border/background flash over a squash-and-stretch press effect.
- Any new theme-toggle transition (surface/text color swap) must use `--aegis-motion-duration-normal` with `ease-standard`, and must respect `prefers-reduced-motion` by collapsing to an instant swap (already guaranteed globally by `motion.css:11-26`, since `transition-duration` is forced to `0.01ms` — just don't add a `will-change`/JS-driven cross-fade that ignores CSS transitions).
- Graph canvas motion (camera moves, node layout animation, cinematic replay) is explicitly **out of scope** for this document — see §7.

## 7. Graphs (2D + 3D) — APPROVED

> **Implementer: Fable 5 (high effort).** This section was proposed separately (graph visuals were explicitly out of scope for the rest of this spec's authoring pass), relayed to the product owner, and **approved as written below**, including the owner-requested 9th point (alive edges). Route implementation of this section specifically to a Fable 5 agent at high reasoning effort — it touches shader/animation work across both the Sigma (2D) and Three.js (3D) renderers and needs the judgment to keep both in visual lockstep, not a mechanical restyle pass.

Same ground rules as the rest of this document: no change to `GraphStore` semantics, node/edge data, selection state, or the click→inspector wiring. Per the architecture contract and the on-screen copy already in the app ("2D analysis is authoritative; 3D is the read-only semantic presentation"), 2D remains the source of truth for layout and analysis; 3D is a restyled *presentation* of the same store. Everything below is encoding/shader/animation work layered on top of the existing data flow.

Relevant files: `apps/web/features/cinematic-graph/**` (in particular `shaders/risk-halo.ts`, `lib/capability.ts`, `lib/scene-quality.ts`, `contracts/render-quality-tier.ts`, `contracts/scene-node.ts`, `contracts/scene-edge.ts`, `components/graph-view-mode-toggle.tsx`), `apps/web/features/operational-graph/**` (in particular `adapters/sigma-operational-graph-adapter.ts`, `semantic/graph-semantic-styles.ts`, `semantic/graph-highlights.ts`, `components/sigma-canvas.tsx`), `packages/ui/src/graph-controls/index.tsx` (chrome, already covered in §3), and `apps/web/src/app/globals.css:149-243` (`.operational-graph-frame`, `.cinematic-canvas-shell`, `.cinematic-canvas-vignette`, `.cinematic-node-label`, `.cinematic-node-tag`).

### 7.1 Node color = risk/status (point 1)

Today the 3D scene renders every node as an identical uniform-blue sphere (confirmed live: Semantic 3D Graph view, Operation Silent Relay run — 38 nodes, all one color, only a red-highlighted edge trace breaks the uniformity), while 2D already color/shape-codes by asset type and halos high-risk nodes. Close this gap: drive each 3D node's material color from the **same** risk/status token values already defined in §2.2 (`riskTokens` / `uiStatusTokens`, `packages/ui/src/tokens/tokens.ts`, `packages/ui/src/tokens/status-tokens.ts`) via an emissive tint, not a base-color swap, so nodes stay readable against the dark canvas at every camera distance. Map: risk band or node status (status wins when both are set, matching the 2D legend's own precedence) → emissive color; default/no-signal nodes keep a quiet neutral emissive (current uniform blue, desaturated) so the risk-colored nodes still pop by contrast. Wire this through `contracts/scene-node.ts`'s existing node shape (add the resolved color as a derived field in the semantic scene adapter, `contracts/semantic-scene-adapter.ts`, not a new network/store field).

### 7.2 Node type via size-tier + billboard glyph (point 2)

Keep spheres as the base primitive — true polyhedra-per-type (cube for Database, tetrahedron for Device, etc.) get visually noisy at the camera distances this scene is actually viewed from, and would cost more to light/shade consistently across the risk-color tinting in §7.1. Instead, differentiate type two ways: (a) a **size tier** (e.g. Service/Database render slightly larger than Device/generic infra, mirroring the 2D legend's implicit hierarchy where circles read as more central than diamonds), and (b) a **billboard glyph sprite** — a small always-camera-facing 2D icon plane in front of each node reusing the same icon set as the 2D `GraphLegend` (`packages/ui/src/graph-controls/index.tsx`) and `StatusIcon`/`RiskIcon` (`packages/ui/src/semantic/icons.tsx`), so an operator who's learned the 2D legend recognizes the same glyphs in 3D. This keeps the type language in one place (`semantic/icons.tsx`) instead of duplicating shape logic in two renderers.

### 7.3 Risk halo + emissive glow (point 3)

For critical/high-risk nodes, add a sprite-based halo billboard behind the node, reusing the existing `RISK_HALO_VERTEX`/`RISK_HALO_FRAGMENT` GLSL in `apps/web/features/cinematic-graph/shaders/risk-halo.ts` (it already implements exactly this: a radial `smoothstep` falloff driven by a `uColor`/`uOpacity` uniform pair) — extend, don't rewrite. Feed `uColor` from the same risk-band color resolved in §7.1, and scale `uOpacity` by risk severity (critical brightest, high dimmer, medium/low no halo at all — matching 2D, where only "High risk" gets the halo treatment per its own legend). Layer a subtle matching emissive glow on the node's own material at the same intensity so the halo and the node read as one coherent risk signal rather than two competing effects.

### 7.4 Semantic edge color/weight (point 4)

Edges currently render as a flat thin line in 3D with only the active selection trace picked out in red. Bring over the same three edge semantics the 2D `GraphLegend` already documents — **high-risk path** (selected trace), **neighborhood** (one-hop focus), and **incident scope** (containment) — as shared color/weight rules defined once (in `semantic/graph-semantic-styles.ts` if that module is generalized to export renderer-agnostic style resolvers, or a new sibling module consumed by both `sigma-operational-graph-adapter.ts` and the 3D scene edge material) so 2D and 3D can't visually drift apart over time. Default edges stay thin and muted (low emissive/opacity) in both renderers; the active/selected trace is thicker and brighter; incident-scope edges get the dashed treatment 2D already uses (2D: literal dash pattern; 3D: a dashed/segmented shader or alpha-striped material for the equivalent read).

### 7.5 Hover/select floating node labels (point 5)

Keep labels off by default at the current dense-graph zoom level (38+ nodes) to avoid label soup — this matches the "read at a glance, dense on inspection" principle in §1. On hover or selection, show the floating node card that already exists in CSS (`.cinematic-node-label` / `.cinematic-node-tag`, `globals.css:202-243`) — it just needs the flattened/restyled treatment from §2-§3 (tighter radius, quieter glow, the new `mono-sm`/`eyebrow` type scale for the ID/tag sub-line) rather than a new component. No new markup structure required, only class/token updates plus wiring it to trigger on 3D hover/select the same way the 2D canvas's tooltip-equivalent already triggers on hover/select there (confirm parity, don't reinvent).

### 7.6 Risk-skyline Z-height mapping (point 6 — owner-approved)

In addition to color/halo, map each node's **Z-height** (altitude above the ground plane) to its risk score: higher risk floats higher. This is a 3D-only signal with no 2D equivalent — intentional, since the owner approved it as a distinguishing feature of the "semantic presentation" layer rather than a like-for-like port of 2D. Keep X/Y positions synced to the 2D layout per the architecture contract (`GraphStore` remains authoritative for placement in-plane); only Z is derived client-side from risk score at render time, so this stays presentation-only and never feeds back into the shared layout state. Keep the altitude range modest (a "skyline," not a tower) so the scene stays legible from the default camera angle and low/no-risk nodes don't sit so far below eye level they're hard to reach with orbit controls.

### 7.7 Camera + interaction (point 7)

Add orbit controls with fit-to-selection, mirroring the 2D `GraphCameraControls` button set (`packages/ui/src/graph-controls/index.tsx:166-194`: Fit / Zoom in / Zoom out / Reset) so the same four actions exist in both views — reuse that component's button group rather than inventing new 3D-only camera chrome, wired to the Three.js camera instead of the Sigma camera. Quiet the ground grid and vignette (`.cinematic-canvas-shell`, `.cinematic-canvas-vignette`, `globals.css:180-200`) per the flattened-dark-theme direction in §2: lower the grid line opacity roughly 30-40% so it reads as ambient texture/orientation aid, not a competing pattern against the risk-colored nodes it's supposed to set off.

### 7.8 Keep Three.js (point 8)

Confirmed: keep Three.js / React Three Fiber for this view. `CLAUDE.md` explicitly scopes "Three.js/R3F only for the derived cinematic view," and the product's own on-screen copy already frames 3D as a deliberate read-only semantic layer, not a 2D replacement — dropping it would be an architectural change, out of scope for a visual-only redesign, and was never on the table in the approved proposal.

### 7.9 Dynamic "alive" edges/arrows (point 9 — owner-added)

Directed edges in **both** 2D and 3D should feel alive: an animated flow cue — a moving gradient segment, dash-offset sweep, or traveling particle — running along each edge in the direction of its relationship, communicating "activity/data flow along this path" rather than a static connector. This is most important during a **live** scenario run: an edge should visibly pulse when a new event/evidence/telemetry item traverses that relationship in real time (wire the pulse trigger to the same live-run event stream already driving `apps/web/features/live-run/*` and the GraphStore delta application — an edge "lights up" on the same tick its underlying relationship receives a new event, not a separate polling mechanism).

Concrete direction per renderer:
- **2D (Sigma)**: a lightweight animated dash-offset or gradient-position CSS/canvas technique on the edge program in `sigma-operational-graph-adapter.ts` — Sigma supports custom edge programs; keep the animation to a single interpolated uniform (offset/phase) updated per animation frame, not a full re-render of edge geometry.
- **3D (Three.js)**: a scrolling-UV or dash-offset shader on the edge line material (same shader-uniform-driven approach as the risk-halo in §7.3 — one more small GLSL program, same review posture: local, reviewed, no remote shader loading).

Behavior rules (all mandatory):
- **Default state**: muted/subtle — a slow, low-contrast pulse, clearly secondary to node risk color and the halo treatment in §7.3.
- **Active/selected trace**: brighter, faster, more visible pulse — reinforces (doesn't replace) the existing "selected trace" color/weight treatment from §7.4.
- **`prefers-reduced-motion: reduce`: edges MUST render fully static** — semantic color/weight/dash-for-containment from §7.4 still apply, but zero flow animation. This is not a "slow it down" case, it's "no motion at all," consistent with the global reduced-motion contract already enforced in `packages/ui/src/styles/motion.css:11-26` and restated in §6 and §8 of this document. Gate this the same way the rest of the app does — `capability.ts`'s `probeCapabilityReport` already captures `reducedMotion` and folds it into the recommended render tier; the edge-animation code path should read that same flag (or the live `prefers-reduced-motion` media query for the 2D canvas, which doesn't run through the 3D capability probe) rather than re-deriving it.
- **Performance**: bounded, allocation-free per frame — drive the animation from a single time-uniform/phase value per edge material or a shared clock uniform across all edges, never per-frame object/array allocation, geometry rebuild, or React re-render. Gate the effect behind the existing `RenderQualityTier` (`contracts/render-quality-tier.ts`): `HIGH` gets full per-edge animated flow; `MEDIUM` gets a coarser/shared-phase version (e.g. fewer distinct phase offsets, or animate only edges touching the current selection/neighborhood instead of the whole graph); `LOW` and `FALLBACK_2D` render edges fully static (same visual endpoint as reduced-motion, reached via the performance gate rather than the motion-preference gate — both paths must converge on "static, semantic color only").
- Both the 2D and 3D implementations must independently respect reduced-motion and their own quality/capability signal — a user with reduced motion set must see static edges in 2D even if 3D is never opened, and vice versa.

## 8. Accessibility requirements

- **Contrast**: every text/background pairing in §2.2 must hit WCAG AA (4.5:1 normal text, 3:1 large text/UI components) in both themes. The light-theme risk/status pairs are flagged in §2.2 as needing verification once rendered — run the existing `vitest-axe`/Storybook a11y tooling (see §10) against both themes before sign-off.
- **Keyboard**: no change to existing keyboard behavior is in scope, but the redesign must not regress it. Specifically preserve: `apps/web/features/shell/hooks/use-keyboard-shortcuts.ts` global shortcuts, the replay transport's documented keyboard map ("Space play/pause · ←/→ step · Home/End jump · [/] speed · B next bookmark", observed on the Replay surface), and Radix's built-in focus trapping in `Dialog`/`Drawer`/`DropdownMenu`/`Tabs`.
- **Focus visibility**: the global `:focus-visible` outline (`globals.css:76-79`) and `focusTokens.ring` (`tokens.ts:47-49`) must remain visible against both new theme backgrounds — verify the ring color (`--aegis-focus-ring`) at both its dark and light values against the surfaces it appears on (buttons, table rows, tabs, nav links).
- **Motion**: covered in §6 — the existing global reduced-motion override must continue to zero every duration; nothing in this redesign may ship an animation outside the token system that could bypass it.
- **Semantics**: don't touch ARIA roles/labels already present (`role="status"`, `aria-live="polite"` on `StatusStrip` and `DisconnectedState`; `role="alert"` on `Alert`/`ErrorState`; `aria-label` on icon-only nav/collapsed states) — the redesign is purely visual on top of this existing (correct) semantic layer.

## Verification checklist

- [ ] Every surface inventoried in §4 (sign-in/first-run, scenarios, active run, incidents queue + detail, replay, after-action, reports, admin ×3 tabs, inspector/context channel, design system) has been restyled per its section's guidance.
- [ ] All token changes in §2 are applied only inside `packages/ui/src/styles/tokens.css` (plus the new `:root[data-theme="light"]` block) and `packages/ui/src/tokens/*.ts` — no component hardcodes a color/radius/shadow value that bypasses a token.
- [ ] Both dark and light themes render correctly across every surface in §4, toggled via the mechanism in §2.1, with no FOUC/flash on load and no persisted-preference regression.
- [ ] All light-theme color pairs from §2.2 pass WCAG AA contrast (verified with real rendered output, not just the calibrated hex starting points).
- [ ] `prefers-reduced-motion: reduce` still zeroes all transitions/animations (§6) and the removed button press-scale doesn't reappear.
- [ ] Keyboard navigation, focus order, and all documented shortcuts (global shell shortcuts, replay transport keys) are unchanged and focus rings are visible in both themes.
- [ ] **Zero functional regressions**: every mutation, query, route, WebSocket subscription, approval flow, replay transport action, and admin control still triggers the exact same handler it did before — only class names/tokens/markup structure for presentation changed. No prop APIs on any `packages/ui` component changed in a way that breaks existing call sites.
- [ ] All existing `data-testid` attributes referenced by Playwright/vitest tests remain present and attached to the same logical element.
- [ ] CSP is untouched: no new external font/script/style/connect origins introduced (`apps/web/next.config.ts`); any new font remains system-stack or self-hosted+bundled under `apps/web/public/`.
- [ ] The Graphs section (§7) is only replaced with real content after explicit owner approval of the separately-relayed proposal — not filled in speculatively.

## Testing to-do

**Visual, per-surface** (manual, using the Chrome walk in §4 as the checklist):
- [ ] Sign-in / first-run (fresh-install "Create admin account" state, dev-identity picker) — both themes.
- [ ] Scenarios (empty scenario list vs. populated with an active run) — both themes.
- [ ] Active run — 2D graph, then 3D graph, with the four control clusters and the legend — both themes.
- [ ] Incidents queue (zero/some/many incidents) and case detail (with and without proposals/evidence populated) — both themes.
- [ ] Replay — transport controls at rest and mid-playback, Normal vs. Cinematic tab — both themes.
- [ ] After-action — passed vs. failed grade, score breakdown expanded — both themes.
- [ ] Reports — claim-card grid with all six claim types represented — both themes.
- [ ] Admin — Users & Roles, Policy (matrix + action classes + allowlisted commands), Platform tabs — both themes.
- [ ] Inspector/Context channel — empty state and populated state on at least two different host surfaces — both themes.
- [ ] Design System page itself, including the new theme-toggle preview — both themes.

**Automated:**
- [ ] `pnpm --filter @aegis/web test` and `pnpm --filter @aegis/ui test` (if a `packages/ui` test target exists) — full vitest suite, unchanged pass rate.
- [ ] `vitest-axe` / Storybook a11y checks re-run against both themes, not just dark (currently the only theme, so these suites have never exercised a light branch — expect to add theme as a Storybook global/toolbar control).
- [ ] `pnpm test:e2e` (Playwright, `apps/web`) — full suite green with no selector changes needed (confirms `data-testid` stability from the checklist above).
- [ ] `pnpm typecheck`, `pnpm lint`, `pnpm format:check` — clean (token/class changes shouldn't touch types, but new `typographyTokens` keys must be typed).
- [ ] `pnpm build` — production build succeeds with both theme branches in the shipped CSS.

**Manual Chrome pass:**
- [ ] Re-walk every surface in this spec end-to-end in Chrome exactly as this authoring session did, in both themes, at desktop width.
- [ ] Confirm no console errors/warnings introduced (`read_console_messages`).

**Responsive + keyboard:**
- [ ] Mobile rail drawer (`<lg` breakpoint, `operations-rail.tsx`'s `Drawer` branch) opens/closes correctly in both themes with the new chrome.
- [ ] Tab through each restyled surface top-to-bottom; confirm focus order and visible focus ring at every stop, both themes.
- [ ] Resize from desktop → tablet width on the Active Run and Incidents surfaces (the two most control-dense screens) and confirm no overflow/clipping introduced by the tightened padding/density changes.
