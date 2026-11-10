# How the three templates interact

> Guidelines → Layout → Page Spec: a dependency chain where each file
> constrains the next.

---

## The dependency chain

```
┌─────────────┐     constrains     ┌──────────┐     constrains     ┌───────────┐
│  Guidelines  │ ──────────────────▶│  Layout   │ ──────────────────▶│ Page Spec │
│              │                    │           │                    │           │
│  canvas      │   canvas must      │  canvas   │   layout must      │  layout   │
│  spacing     │   match; regions   │  regions  │   match; visuals   │  visuals  │
│  page rules  │   must obey grid,  │           │   fill regions     │  slots    │
│  palette     │   margin, gutter   │           │   by role           │           │
│  typography  │                    │           │                    │           │
│  layouts     │                    │           │                    │           │
└─────────────┘                    └──────────┘                    └───────────┘
                                        ▲                               │
                                        │         references            │
                                        └───────────────────────────────┘
                                          (page spec names a layout)
```

---

## 1. Guidelines → Layout

The guidelines file **constrains** which layouts are valid.

| Guideline key | What it constrains on the layout |
|---|---|
| `canvas.width` / `canvas.height` | The layout's `canvas` must match exactly. A 1920×1080 layout is refused under 1280×720 guidelines. |
| `spacing.grid` | Every region edge (x, x+w, y, y+h) must land on a multiple of the grid size. |
| `spacing.margin` | Every region must be at least `margin` pixels from every page edge. |
| `spacing.gutter` | Every pair of adjacent regions must be at least `gutter` pixels apart. |
| `layouts.search_path` | Tells `bp apply` where to find layout files. Paths are relative to the guidelines file. |
| `layouts.default` | The layout used when a page spec doesn't name one. |

**Enforcement point:** `bp apply` calls `layouts.conflicts()` before placing
anything. A layout that violates grid, margin or gutter is refused — the error
names the specific region and the rule it breaks. This prevents `apply` and
`fmt` from fighting each other (apply places, fmt snaps, apply moves back…).

**What guidelines do NOT constrain:** the number of regions, which roles
exist, or the visual arrangement. Those are the layout's job.

---

## 2. Layout → Page Spec

The layout **constrains** what a page spec can ask for.

| Layout property | What it constrains on the page spec |
|---|---|
| Region count per role | The spec can place at most N visuals of a given role. Exceeding the count is an error ("running out of regions"), never a reflow. |
| Region roles available | A spec can only use roles the layout defines. If the layout has no `kpi-row` regions, a KPI visual (whose default role is `kpi-row`) needs an explicit `region: main` override or a different layout. |
| Region dimensions | The visual gets exactly the region's size. No stretching, no splitting. |

**What the layout does NOT constrain:** which visual types go in a region,
what fields are bound, or the visual's title. Those are the spec's job.

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
the layout.

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

| Concern | Guidelines | Layout | Page Spec |
|---|:---:|:---:|:---:|
| Page dimensions | ✅ declares | ✅ must match | — |
| Grid / margin / gutter | ✅ declares | ✅ must obey | — |
| Region positions and sizes | — | ✅ declares | — |
| Region roles (header, kpi-row, main) | — | ✅ declares | ✅ fills |
| Which layout to use | ✅ default | — | ✅ selects |
| Visual types | — | — | ✅ declares |
| Data bindings (fields) | — | — | ✅ declares |
| Colour rules | ✅ declares | — | — (checked after) |
| Font rules | ✅ declares | — | — (checked after) |
| Density limit | ✅ declares | — | ✅ must obey |
| Title requirement | ✅ declares | — | ✅ must obey |

---

## The runtime flow

```
1. Client writes guidelines.yaml, layouts/*.yaml, and page-spec.yaml
2. `bp apply page-spec.yaml --report R --guidelines guidelines.yaml`

   a. Load guidelines (defaults ← org file ← report override ← CLI flags)
   b. Parse the page spec
   c. Resolve the layout name → load the layout file from search_path
   d. Validate layout against guidelines (grid, margin, gutter)
   e. Validate page spec against guidelines (title, density)
   f. Resolve field references against the TMDL model
   g. Place visuals into layout regions by role
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
  standard-dashboard.yaml    ← 1 canvas + N regions, ~15 lines
pages/
  overview.yaml              ← 1 page name + 1 layout + N visuals
```

Plus the PBIP project folder and its TMDL model (which already exist —
Blueprint doesn't create those).
