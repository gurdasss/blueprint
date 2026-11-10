# How the three templates interact

> Guidelines → Layout → Page Spec: a dependency chain where each file
> constrains the next. The guidelines own the numbers (canvas, grid,
> margin, gutter). The layout describes structure (rows, columns). The
> engine connects them and computes every pixel coordinate.

---

## The dependency chain

```
┌─────────────┐       feeds into       ┌──────────┐     constrains     ┌───────────┐
│  Guidelines  │ ──────────────────────▶│  Engine   │ ──────────────────▶│ Page Spec │
│              │                        │           │                    │           │
│  canvas      │   canvas, grid,        │  computes │   region count,    │  layout   │
│  spacing     │   margin, gutter       │  pixel    │   roles, sizes     │  visuals  │
│  page rules  │   ─────────────────▶   │  regions  │   constrain what   │  slots    │
│  palette     │                        │  from     │   the spec can do  │           │
│  typography  │       ┌──────────┐     │  both     │                    │           │
│  layouts     │       │  Layout  │────▶│  inputs   │                    │           │
│              │       │          │     │           │                    │           │
│              │       │  rows    │     └──────────┘                    └───────────┘
│              │       │  roles   │          ▲                               │
│              │       │  heights │          │         references            │
│              │       │  columns │          └───────────────────────────────┘
└─────────────┘       └──────────┘            (page spec names a layout)
```

---

## 1. Guidelines + Layout → Engine (coordinate computation)

The layout describes **structure** — rows and columns. The guidelines provide
**numbers** — canvas size, grid, margin, gutter. Neither file contains pixel
coordinates. The engine connects them.

### What the engine computes

Given guidelines `canvas: 1280×720` and `spacing: {grid: 8, margin: 16, gutter: 16}`, and
layout `rows: [{header, 64}, {kpi-row, 160, columns: 2}, {main, columns: 2}]`:

```
Step 1 — Usable area
  usable_width  = canvas.width  − 2 × margin = 1280 − 32 = 1248
  usable_height = canvas.height − 2 × margin = 720  − 32 = 688

Step 2 — Row heights
  header:  64px (explicit)
  kpi-row: 160px (explicit)
  gutters: 2 × gutter = 32px (between header→kpi-row and kpi-row→main)
  main:    688 − 64 − 160 − 32 = 432px (fills remaining space)

Step 3 — Column widths (per row)
  header (1 col):  1248px
  kpi-row (2 col): (1248 − 16) / 2 = 616px each
  main (2 col):    (1248 − 16) / 2 = 616px each

Step 4 — Snap every value to grid (nearest multiple of 8)
  All values already on grid ✓

Step 5 — Compute x, y for each region
  header   → x:16  y:16  w:1248 h:64
  kpi-row₁ → x:16  y:96  w:616  h:160
  kpi-row₂ → x:648 y:96  w:616  h:160
  main₁    → x:16  y:272 w:616  h:432
  main₂    → x:648 y:272 w:616  h:432
```

### What guidelines provide to the engine

| Guideline key | What the engine uses it for |
|---|---|
| `canvas.width` / `canvas.height` | The bounding box. All regions live inside it. |
| `spacing.grid` | Snap target. Every computed edge rounds to the nearest multiple. |
| `spacing.margin` | Inset from page edges. Regions start at `(margin, margin)`. |
| `spacing.gutter` | Gap between adjacent regions — both horizontal (between columns) and vertical (between rows). |
| `layouts.search_path` | Where to find layout files. |
| `layouts.default` | The layout used when a page spec doesn't name one. |

### What the layout provides to the engine

| Layout key | What the engine uses it for |
|---|---|
| `name` | Identity — what the page spec references. |
| `rows[].role` | The region role visuals fill (`header`, `kpi-row`, `main`). |
| `rows[].height` | Explicit row height in pixels. Omitted = fill remaining space. |
| `rows[].columns` | How many side-by-side regions. Default 1. |

### What neither file provides

Pixel coordinates. Those are the engine's output, not anyone's input.

---

## 2. Computed regions → Page Spec

The computed regions **constrain** what a page spec can ask for.

| Computed property | What it constrains on the page spec |
|---|---|
| Region count per role | The spec can place at most N visuals of a given role. Exceeding the count is an error ("running out of regions"), never a reflow. |
| Region roles available | A spec can only use roles the layout defines. If the layout has no `kpi-row` row, a KPI visual (whose default role is `kpi-row`) needs an explicit `region: main` override or a different layout. |
| Region dimensions | The visual gets exactly the computed region size. No stretching, no splitting. |

**What the computed regions do NOT constrain:** which visual types go in a
region, what fields are bound, or the visual's title. Those are the spec's job.

---

## 3. Page Spec → Layout (the back-reference)

The page spec **references** a layout by name.

```yaml
# in the page spec
layout: standard-dashboard    # ← must exist on the guidelines search_path
```

`bp apply` resolves this name against the guidelines' `layouts.search_path`
directories. If the layout file isn't found, the error names the directories
it searched.

When the spec omits `layout:`, the guidelines' `layouts.default` is used.
If that's also unset, it's an error.

---

## 4. Page Spec ↔ Guidelines (direct constraints)

Some guideline keys constrain the page spec directly, without going through
the layout engine.

| Guideline key | What it constrains on the page spec |
|---|---|
| `page.require_title` | If `true`, the spec must include a `type: header` visual. |
| `page.max_visuals` | The spec can't exceed this count (counted by `density_policy`). |
| `page.density_policy` | How visuals are counted: `all`, `visible`, or `data` (excludes headers/textboxes). |
| `palette.*` | `bp check` validates that the built page's colours match the palette. |
| `typography.*` | `bp check` validates that fonts and sizes match the typography rules. |

---

## 5. The semantic model (external input)

The page spec's `slots` reference fields from the Power BI semantic model
(TMDL), which is outside all three templates. `bp apply` resolves field
references against the model before writing anything:

```
Page Spec                    Semantic Model (TMDL)
─────────                    ────────────────────
"[Total Revenue]"    ──────▶  measures in the model
"Geography[Region]"  ──────▶  columns in the model
"Sales[Geography]"   ──────▶  hierarchies in the model
```

A field that doesn't exist in the model is an error from `bp apply`, not a
confusing result in Desktop. This is validated before any file is written.

---

## What each file is responsible for

| Concern | Guidelines | Layout | Engine | Page Spec |
|---|:---:|:---:|:---:|:---:|
| Page dimensions | ✅ declares | — | ✅ reads | — |
| Grid / margin / gutter | ✅ declares | — | ✅ reads | — |
| Row structure (roles, heights, columns) | — | ✅ declares | ✅ reads | — |
| Region pixel coordinates | — | — | ✅ computes | — |
| Region roles | — | ✅ declares | ✅ passes through | ✅ fills |
| Which layout to use | ✅ default | — | — | ✅ selects |
| Visual types | — | — | — | ✅ declares |
| Data bindings (fields) | — | — | — | ✅ declares |
| Colour rules | ✅ declares | — | — | — (checked after) |
| Font rules | ✅ declares | — | — | — (checked after) |
| Density limit | ✅ declares | — | — | ✅ must obey |
| Title requirement | ✅ declares | — | — | ✅ must obey |

---

## The runtime flow

```
1. Client writes guidelines.yaml, layouts/*.yaml, and page-spec.yaml
2. `bp apply page-spec.yaml --report R --guidelines guidelines.yaml`

   a. Load guidelines (defaults ← org file ← report override ← CLI flags)
   b. Parse the page spec
   c. Resolve the layout name → load the structural layout from search_path
   d. Compute pixel regions from layout + guidelines (grid, margin, gutter)
   e. Validate page spec against guidelines (title, density)
   f. Resolve field references against the TMDL model
   g. Place visuals into computed regions by role
   h. Write PBIR files (or refuse if anything failed)
   i. Run `bp check` rules on the result (palette, typography, etc.)
   j. Regenerate the manifest
```

Steps d–f happen **before** any file is written. Every problem is collected
with its location and reported together. Nothing is half-written.

---

## Minimal working set

The smallest complete set of files a client needs:

```
my-guidelines.yaml           ← 7 sections, ~30 lines
layouts/
  standard-dashboard.yaml    ← name + rows, ~10 lines
pages/
  overview.yaml              ← page name + layout + visuals, ~20 lines
```

Plus the PBIP project folder and its TMDL model (which already exist —
Blueprint doesn't create those).
