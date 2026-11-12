# How the three templates interact

> Guidelines → Layout → Page Spec: a dependency chain where each file
> constrains the next. The guidelines own the numbers (canvas, grid,
> margin, gutter). The layout states every region's pixel coordinates.
> The engine checks the layout against the guidelines and places the
> spec's visuals into its regions.

---

## The dependency chain

```
┌─────────────┐       feeds into       ┌──────────┐     constrains     ┌───────────┐
│  Guidelines  │ ──────────────────────▶│  Engine   │ ──────────────────▶│ Page Spec │
│              │                        │           │                    │           │
│  canvas      │   canvas, grid,        │  checks   │   region count,    │  layout   │
│  spacing     │   margin, gutter       │  the      │   roles, sizes     │  visuals  │
│  page rules  │   ─────────────────▶   │  layout,  │   constrain what   │  slots    │
│  palette     │                        │  places   │   the spec can do  │           │
│  typography  │       ┌──────────┐     │  visuals  │                    │           │
│  layouts     │       │  Layout  │────▶│  into its │                    │           │
│              │       │          │     │  regions  │                    │           │
│              │       │  canvas  │     └──────────┘                    └───────────┘
│              │       │  regions │          ▲                               │
│              │       │  x y w h │          │         references            │
│              │       │  roles   │          └───────────────────────────────┘
└─────────────┘       └──────────┘            (page spec names a layout)
```

---

## 1. Guidelines + Layout → Engine (checking, not computing)

The layout states **where every region is**, in pixels. The guidelines state
the **numbers those regions must obey** — canvas size, grid, margin, gutter.
The engine's job here is to refuse a layout that breaks them, before anything
is written.

Pixels are the only unit in this version, and the client writes each one.
Relative positioning — rows, column counts, coordinates Blueprint derives —
is a later version, written up as an extension point in
`template/extensions.md` §5. Until then the arithmetic is the client's, and
`template/layout.template.yaml` works it out at the bottom of the file
(the solved column table, and what a region flush to the margin needs).

### What the engine checks (`layouts.conflicts`)

Given guidelines `canvas: 1280×720` and `spacing: {grid: 8, margin: 16, gutter: 16}`,
every region in the layout must satisfy all three:

```
On the grid       Every edge on a multiple of spacing.grid.
                  The page edges always count as grid lines.
                    region main#2 is off the 8px grid (right=1277.55)

Inside the margin Every edge at least spacing.margin from the page edge.
                    region header#1 is inside the 16px margin (left)

Gutter apart      Regions sharing part of a row or column at least
                  spacing.gutter apart.
                    regions main#1 and main#2 are 8px apart, less than
                    the 16px gutter
```

A failure refuses **the layout**, not the spec. The reason: a region off the
grid or inside the margin would make `bp apply` and `bp fmt` undo each other
forever, and regions closer than the gutter would build pages `bp check` then
flags.

A region extending outside the layout's own canvas is refused earlier still,
by `layouts.parse`.

One thing is only a **warning**: a `kpi-row` region under 160px. At 120px
Desktop clips a KPI visual's goal line and a titled card's label (measured),
so `bp apply` says so and builds the page anyway — region heights aren't
something the guidelines state, and a report Desktop has already saved may
use a shorter row.

### What guidelines provide to the engine

| Guideline key | What the engine uses it for |
|---|---|
| `canvas.width` / `canvas.height` | What `bp check` compares a page against, under the `page-size` rule. The page's actual size comes from the *layout's* canvas, so keep the two equal or every spec-built page is reported. |
| `spacing.grid` | Every region edge must land on a multiple. |
| `spacing.margin` | Minimum distance from every region edge to the page edge. |
| `spacing.gutter` | Minimum gap between regions that share part of a row or column. |
| `layouts.search_path` | Where to find layout files. |
| `layouts.default` | The layout used when a page spec doesn't name one. |

### What the layout provides to the engine

| Layout key | What the engine uses it for |
|---|---|
| `name` | Identity — what the page spec references. Must match the file name. |
| `canvas.width` / `canvas.height` | The size `bp apply` gives the page it creates. On a re-run it errors if the page it finds isn't this size: it never scales a layout. |
| `regions[].role` | The region role visuals fill (`header`, `kpi-row`, `main`, or any lowercase name of the client's own). |
| `regions[].x` / `.y` | The region's top-left corner, in pixels. |
| `regions[].w` / `.h` | The region's width and height, in pixels. |

### What neither file provides

Which visual goes where. That is the spec's job, matched by role.

---

## 2. Regions → Page Spec

A layout's regions **constrain** what a page spec can ask for.

| Region property | What it constrains on the page spec |
|---|---|
| Region count per role | The spec can place at most N visuals of a given role. Exceeding the count is an error ("running out of regions"), never a reflow. |
| Region roles available | A spec can only use roles the layout defines. If the layout has no `kpi-row` region, a KPI visual (whose default role is `kpi-row`) needs an explicit `region: main` override or a different layout. |
| Region dimensions | The visual gets exactly the region's size. No stretching, no splitting, no spanning two regions. |

Visuals fill regions **in declaration order**: each takes the next unused
region whose role matches — the visual's own `region:` if it has one, else the
role its type's contract declares. A `blueprint: ignore` visual takes no
region.

A region no visual was placed in is a gap on the page. `bp apply` warns
(`layouts.unused`) and names layouts that place the spec with every region
filled, but it never stretches other regions into the gap.

**What the regions do NOT constrain:** which visual types go in a region, what
fields are bound, or the visual's title. Those are the spec's job.

---

## 3. Page Spec → Layout (the back-reference)

The page spec **references** a layout by name.

```yaml
# in the page spec
layout: standard-dashboard    # ← must exist on the guidelines search_path
```

`bp apply` resolves this name against the guidelines' `layouts.search_path`
directories. If the layout file isn't found, the error names the directories
it searched. Entries on that search path resolve relative to the guidelines
file that declares them, not the current directory.

When the spec omits `layout:`, the guidelines' `layouts.default` is used.
If that's also unset, it's an error.

---

## 4. Page Spec ↔ Guidelines (direct constraints)

Some guideline keys constrain the page spec directly, without going through
the layout.

| Guideline key | What it constrains on the page spec |
|---|---|
| `page.require_title` | If `true`, the spec must include a `type: header` visual. |
| `page.title_region` | The region role that header must sit in. |
| `page.max_visuals` | A page over this count is reported by `bp check` under the `density` rule. `bp apply` doesn't count: it will build a page that exceeds the limit, and `check` is what says so. |
| `page.density_policy` | How visuals are counted for that rule: `all`, `visible`, or `data` (excludes headers/textboxes). |
| `palette.*` | `bp check` validates that the built page's colours match the palette. |
| `typography.page_title` | `bp apply` writes this onto the header textbox it creates. |
| `typography.*` | `bp check` validates that fonts and sizes match the typography rules. |

The title rules are the one place `apply` warns rather than refuses: a spec
that would fail `page.require_title` or `page.title_region` is still applied,
with a warning naming what `bp check` will report. Whether a page must have a
title is the guidelines' call, and `check` is what enforces it.

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
| Page dimensions | ✅ declares | ✅ declares | ✅ compares | — |
| Grid / margin / gutter | ✅ declares | — | ✅ enforces | — |
| Region pixel coordinates | — | ✅ declares | ✅ checks | — |
| Region roles | — | ✅ declares | ✅ passes through | ✅ fills |
| Which layout to use | ✅ default | — | — | ✅ selects |
| Visual types | — | — | — | ✅ declares |
| Data bindings (fields) | — | — | — | ✅ declares |
| Colour rules | ✅ declares | — | — | — (checked after) |
| Font rules | ✅ declares | — | — | — (checked after) |
| Density limit | ✅ declares | — | — | ✅ must obey |
| Title requirement | ✅ declares | — | — | ✅ should obey |

---

## The runtime flow

```
1. Client writes guidelines.yaml, layouts/*.yaml, and page-spec.yaml
2. `bp apply page-spec.yaml --report R --guidelines guidelines.yaml`

   a. Load guidelines (defaults ← org file ← report override ← --set flags)
   b. Parse the page spec
   c. Resolve the layout name → load the layout from search_path
   d. Check the layout's regions against the guidelines
      (grid, margin, gutter) — refuse the layout if any edge is off
   e. Check the page spec's header against the title rules (a warning)
   f. Resolve field references against the TMDL model
   g. Place visuals into regions by role
   h. Write PBIR files (or refuse if anything failed)
   i. Regenerate the manifest
```

Steps c–g happen **before** any file is written. Every problem is collected
with its location and reported together. Nothing is half-written. Given
several specs, all of them are pre-flighted and nothing is written if any
one fails.

`bp apply` does not run the `bp check` rules on what it wrote. It reports what
it changed, warns about the title rules and about a new visual overlapping a
hand-placed one, and leaves the rest to `bp check`.

---

## Minimal working set

The smallest complete set of files a client needs:

```
my-guidelines.yaml           ← 8 sections, ~30 lines
layouts/
  standard-dashboard.yaml    ← name + canvas + regions, ~10 lines
pages/
  overview.yaml              ← page name + layout + visuals, ~20 lines
```

Plus the PBIP project folder and its TMDL model (which already exist —
Blueprint doesn't create those).
