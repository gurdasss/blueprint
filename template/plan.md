# Template Plan

> Client-perspective-first redesign of Blueprint's input files.

---

## Goal

Strip the guidelines spec to its **absolute essence** — the 20% of keys that
cover 80% of real client work — and make that core bulletproof. Advanced
features ship later through an **extension system** that clients opt into,
so the base file stays small and learnable.

This branch (`claude/amazing-sagan-ejiuec`) refactors the main-branch code
toward these templates. Reusable code from main is kept; the schema and
validation layer are rewritten.

---

## Scope: the three client inputs

A client (human or LLM agent) provides:

1. **Guidelines** — the organisation-wide design contract.
2. **Layout** — the structural description of a page shape (referenced by name).
3. **Page spec** — which visuals go on a page, with their bindings.

We design them **in this order**, because each one constrains the next.

---

## Core 20% summary

### Core keys (guidelines)

```yaml
version: 1
name: "<Client> Reporting Standard"

canvas:
  width: 1280
  height: 720

spacing:
  grid: 8
  margin: 16
  gutter: 16

page:
  max_visuals: 8
  density_policy: data
  require_title: true

palette:
  categorical: ["#4E79A7", "#F28E2B", "#E15759", "#76B7B2", "#59A14F"]
  background: "#FFFFFF"
  text: "#333333"
  enforce: strict

typography:
  page_title:    { font: Segoe UI Semibold, size: 18 }
  visual_title:  { font: Segoe UI, size: 12 }
  body:          { font: Segoe UI, size: 10 }

layouts:
  search_path: ["layouts"]
  default: standard-4-up
```

### Core features beyond guidelines

| Feature | How it works |
|---------|-------------|
| Drill-down paths | Ordered list in a slot: `category: ["Country", "State", "City"]` |
| Named data formats | `format: currency` / `whole_number` / `decimal` / `percentage` |
| Inline aggregation | Pipe syntax: `"Table[Column] \| distinctcount"` |
| Visual inheritance | `inherits: column` in visual YAML — reuse slots |
| Model hierarchies | `"Table[Hierarchy]"` binds all levels automatically |

### Core visual types

header, card, kpi, column, line, bar, table (7 types).

---

## Compatibility analysis: current system vs. new design

### Overall: ~75% compatible

The PBIR layer, model, and render path are untouched. The guideline schema
and layout format are the two areas that change significantly. The page spec
changes are small.

### Module-by-module assessment

#### Untouched (100% compatible) — keep as-is

| Module | Why it's unchanged |
|--------|-------------------|
| `pbir/reader.py` | Reads PBIR JSON → model objects. No guideline knowledge. |
| `pbir/writer.py` | Patches PBIR documents in place. No guideline knowledge. |
| `pbir/jsonfmt.py` | Byte-identical JSON formatting. No guideline knowledge. |
| `pbir/schemas.py` | Schema validation. No guideline knowledge. |
| `pbir/formatting.py` | Colour/font extraction. No guideline knowledge. |
| `pbir/render.py` | Builds PBIR JSON from model inputs. Already shape-agnostic. |
| `pbir/semantic.py` | Reads TMDL model. No guideline knowledge. |
| `pbir/ids.py` | Deterministic name generation. No guideline knowledge. |
| `pbir/registry.py` | Manages `pages.json`. No guideline knowledge. |
| `pbir/theme.py` | Writes theme JSON. Reads palette/typography from guidelines but only the values, not the schema structure (it receives a `Guidelines` object). |
| `model.py` | Report/Page/Visual/Rect/Field etc. Format-agnostic. |
| `grid.py` | Grid snapping. Takes `grid_size` as an int, not a Guidelines object. |
| `policies.py` | Density counting functions. No guideline knowledge. |
| `manifest.py` | Builds manifest from model annotations. No guideline knowledge. |

**14 modules, ~3,500 lines — zero changes needed.**

#### Minor adaptation (~80% compatible) — small targeted edits

| Module | What changes | What stays |
|--------|-------------|-----------|
| `slots.py` | Add `inherits:` resolution in `_load()`. Add `format` field to `Slot`. | `Contract`, `Slot`, `Option` dataclasses. `contracts()` caching. All validation logic. The YAML format is almost identical. |
| `spec.py` | Add pipe syntax parsing (`\| distinctcount`). Add long-form slot (`{field, format}`). | `PageSpec`, `VisualSpec`, `FieldRef` dataclasses. All structural validation. Field reference parsing. Options validation. |
| `validate.py` | Remap typography role names (`header` → `page_title`, `title` → `visual_title`). Read `spacing.*` instead of `canvas.margin`/`canvas.gutter`. | Every rule function body (bounds, grid, margin, gutter, overlap, density, palette). `Finding`/`CheckResult`. Theme checking. The `_Collector` pattern. ~90% of the file. |
| `commands/check.py` | Adapt guideline field paths. Remove `check.severity` from guidelines (bake defaults into code). | Command structure, output formatting, exit codes, `--github` annotations. |
| `commands/apply.py` | Adapt guideline field paths. Pass new `format` data through to render. | The entire apply flow: pre-flight, placement, creation, re-run detection, binding, manifest regen. |
| `commands/fmt.py` | Read grid/margin from `spacing.*` instead of `grid.*`/`canvas.*`. | All formatting logic. |
| `commands/inspect.py` | Minimal — reads report, not guidelines. | Everything. |
| `commands/describe.py` | Add named formats to output. | Structure, JSON output, TMDL reading. |
| `commands/theme.py` | Adapt guideline field paths for typography roles. | Theme generation logic. |
| `commands/manifest.py` | No change expected. | Everything. |

**10 modules — small, surgical edits totalling ~200-300 lines changed.**

#### Significant rewrite (~30% compatible) — new schema, keep the pattern

| Module | What's rewritten | What's kept |
|--------|-----------------|-----------|
| `guidelines.py` | **Schema structure:** `Grid`/`Canvas`/`CheckRules` dataclasses → new `Spacing` dataclass, `Canvas` simplified (no margin/gutter), `CheckRules` removed (defaults baked in). **Typography roles:** 6 → 3 (`page_title`, `visual_title`, `body`). **Validation severity:** removed from YAML, defaults in code. **`_build()` function:** new field paths throughout. | **Layering system:** `load()`, `merge()`, `_read()`, `_anchor()` — the 4-layer resolution is identical. **Validation helpers:** `_int()`, `_bool()`, `_hex()`, `_hex_list()`, `_palette()` — reusable as-is. **`Palette` dataclass** — identical. **`Layouts` dataclass** — identical. **`Guidelines` wrapper** — same pattern, different fields. |
| `defaults.yaml` | New shape matching the template. | Same purpose, same layer-1 role. |
| `guidelines/example.yaml` | New shape matching the template. | Same purpose, same example role. |

**1 module + 2 YAML files — the core of the rewrite, ~400 lines.**

#### Layouts — the structural change (~40% compatible)

| Module | What changes | What stays |
|--------|-------------|-----------|
| `layouts.py` | **Input format:** `canvas` + `regions` with pixel coords → `rows` with role/height/columns. **`parse()` function:** rewritten to read structural rows instead of explicit regions. **New:** `compute_regions()` function (the engine that turns rows + guidelines into pixel regions). | **`Layout` dataclass** output shape (name, width, height, regions) — identical. **`Region`/`Placement` dataclasses** — identical. **`place()` function** — identical (it works with computed regions, doesn't care how they were made). **`find()`/`available()`/`load()`** — identical. **`conflicts()`** — identical. **`unused()`** — identical. |
| `guidelines/layouts/*.yaml` | New structural format (rows instead of pixel regions). | Same file names, same layout names, same roles. |

**1 module — `parse()` rewritten + `compute_regions()` added. ~150 lines. Everything downstream of `Layout` is unchanged.**

#### Tests

| Test area | Impact |
|-----------|--------|
| `tests/test_guidelines.py` | Rewrite — tests the guideline schema directly. |
| `tests/test_layouts.py` | Partial rewrite — layout parsing tests change, placement tests stay. |
| `tests/test_spec.py` | Add tests — pipe syntax, long-form slots, named formats. |
| `tests/test_validate.py` | Minor — remap field paths, typography role names. |
| `tests/test_apply_golden.py` | Regenerate golden output after guidelines/layout format changes. |
| `tests/test_probe_replay.py` | Minor — update guidelines/layout fixtures used in replays. |
| `tests/test_robustness.py` | Minor — adapt to new guideline/layout shapes. |
| All other tests | Unchanged — they test PBIR, model, grid, formatting. |

---

## Incremental change plan

Each step is small, isolated, and independently testable. The system works
after every step — no step leaves things half-broken.

### Step 1 + 3 (done): guidelines schema rewrite, wired into every consumer

**What:** `guidelines.py`, `defaults.yaml`, `guidelines/example.yaml`, and every consumer
of a guideline field path, in one step.

**Why merged:** the plan assumed step 1 could land alone because "the `Guidelines` object
is the same interface". It isn't — the *field paths are* the interface. `validate.py` and
the commands read `rules.grid.size` / `rules.canvas.margin` / `rules.canvas.gutter`
directly, so the schema and its consumers have to move together. A first attempt that
kept backward-compatible shims (`_GridCompat`, `_CanvasCompat`) also broke layering:
`defaults.yaml` sets `spacing.*`, so a higher layer's old `grid.size` (including
`--grid`) could never win.

**Changes:**
- `Spacing(grid, margin, gutter)` replaces `grid.size`, `canvas.margin`, `canvas.gutter`
- `Canvas` is width/height only
- Severity defaults (`DEFAULT_SEVERITY`), decorative types and `max_resize` (0.25) are
  baked into code; `grid.snap` is gone (`bp fmt` always snaps)
- `extensions:` is live for the four things the core dropped: `severity`,
  `decorative_types`, `max_resize` and extra `typography` roles
- Pre-template keys are **refused with their replacement named** (`guidelines.RETIRED`,
  checked per layer so the offending file is named), never ignored — ignoring `grid.size`
  would silently leave the grid at 8 ("refuse rather than surprise")
- Consumers read `rules.spacing.*` / `rules.max_resize`; `--grid` overrides `spacing.grid`;
  the `gutter` finding now says `spacing.gutter is Npx`
- `bp describe --json` reports `spacing: {grid, margin, gutter}` and `canvas: {width, height}`
- Findings and theme notes name the client's key (`visual_title size 18pt…`,
  `extensions.typography.card_label: …`), never the internal role

**Typography:** the three client roles map onto the internal checking roles at parse time,
so `validate.py`, `pbir/theme.py` and `apply.py` keep working unchanged:

| Client role (`typography:`) | Internal role | What it covers |
|---|---|---|
| `page_title` | `header` | the textbox `bp apply` writes for `type: header` |
| `visual_title` | `title` | a visual's own title |
| `body` | `textbox` | every other textbox |

`subtitle`, `callout` and `card_label` stay reachable under `extensions.typography.*`
(same internal names). They are probe-verified behaviour (probes 07, 15), so they moved
rather than being deleted. `bold` is gone everywhere: a weight is part of the face name.

**Carried forward:** two items of the old step 3 depend on later steps and are *not*
done — `apply.py` passing layout rows through `compute_regions()` (moved to step 2) and
`describe.py` listing named formats (moved to step 6).

**Tests:** `test_guidelines.py` rewritten (new paths, retired-key errors, role mapping).
Old YAML in the other tests rewritten. `test_apply_golden.py` and `test_probe_replay.py`
pass **without** `BLUEPRINT_UPDATE_GOLDEN=1` — nothing in this step may change apply's
output, and `example.yaml`'s `page_title` is the old `header` value. `scripts/demo.sh`
runs clean and is still idempotent.

**Result:** 582 passed, `ruff` clean.

### Step 2: Layout structural format

**What:** Rewrite `layouts.py` `parse()` to read structural rows. Add
`compute_regions()` that takes rows + guidelines → pixel regions.

**Changes:**
- `parse()` reads `rows:` instead of `canvas:` + `regions:`
- New `compute_regions(rows, canvas, spacing)` → list of `Region` with pixel coords
- `Layout` dataclass output is identical — downstream code sees the same thing
- Rewrite `guidelines/layouts/*.yaml` to structural format
- `commands/apply.py`: pass the parsed rows through `compute_regions()`
  (carried over from the old step 3, which otherwise landed with step 1)

**Tests:** Rewrite layout parsing tests. Placement tests (`place()`, `unused()`,
`conflicts()`) stay — they work with `Region` objects, not the raw YAML.

**Risk:** Low. The `Layout` object is the same shape. Everything downstream
of `parse()` is unchanged.

### Step 4: Visual inheritance

**What:** Add `inherits:` support to `slots.py`.

**Changes:**
- `_load()` resolves `inherits: <type>` by loading the parent first,
  copying its slots/options/region, then applying the child's overrides
- Add cycle detection (A inherits B inherits A)
- `Contract` dataclass unchanged — the loader produces the same object

**Tests:** Add tests for inheritance resolution, overrides, cycle detection.
Existing visual definition tests stay.

**Risk:** Low. The `Contract` output is identical. Nothing downstream changes.
Existing visual YAMLs don't use `inherits:` yet — they keep working as-is.

### Step 5: Spec enhancements (pipe syntax, long-form slots, named formats)

**What:** Extend `spec.py` to parse the new syntax.

**Changes:**
- `parse_field()`: handle `"Table[Column] | distinctcount"` pipe syntax
- `_slots()`: handle long-form `{field: ..., format: ...}` alongside short-form strings
- `FieldRef`: add optional `aggregation` field
- `VisualSpec`: add optional `formats` dict (slot name → named format)
- Add `NAMED_FORMATS` constant: `{general, whole_number, decimal, currency, percentage}`

**Tests:** Add tests for pipe syntax, long-form slots, format validation.
Existing spec tests stay — the short-form syntax is unchanged.

**Risk:** Low. All changes are additive. Existing specs parse exactly as before.

### Step 6: Wire formats and aggregation into render

**What:** Make `commands/apply.py` pass aggregation and format data through
to `pbir/render.py`.

**Changes:**
- `_resolve()` in apply.py: pass aggregation from `FieldRef` into `Binding`
- `render.py`: write `QueryAggregateFunction` when aggregation is specified
- `render.py`: write data format properties when named format is specified
- `commands/describe.py`: list the named formats a spec may use
  (carried over from the old step 3, which otherwise landed with step 1)
- Need to determine exact PBIR shape for named formats (may need a probe)

**Tests:** Add golden output tests for aggregation and format rendering.

**Risk:** Medium. The PBIR format for named data formats needs verification
against Desktop (a probe). Aggregation is already partially supported in
the reader (`reader.AGGREGATE_FUNCTIONS`).

### Step 7: Update shipped layouts and example files

**What:** Convert all `guidelines/layouts/*.yaml` to structural format.
Update `guidelines/example.yaml` to new schema. Update demo specs if needed.

**Changes:**
- Rewrite 6 layout files (standard-4-up, dashboard-6, kpi-row-plus-detail,
  grid-2x3, two-up, one-up) from pixel regions to structural rows
- Update example.yaml to new guidelines schema
- Verify demo still works: `scripts/demo.sh`

**Tests:** Run `test_probe_replay.py` and `test_apply_golden.py` with
`BLUEPRINT_UPDATE_GOLDEN=1` to regenerate expected output.

**Risk:** Low. The layouts produce the same pixel regions — just described
differently. The demo is the integration test.

### Step 8: Update remaining tests and golden output

**What:** Final test sweep. Regenerate all golden output. Ensure full
test suite passes.

**Changes:**
- `BLUEPRINT_UPDATE_GOLDEN=1 pytest tests/test_apply_golden.py`
- Fix any test fixtures still using old guideline/layout format
- Update probe replay fixtures
- Run `ruff check .`

**Tests:** Full suite must pass. `scripts/demo.sh` must produce the same report.

**Risk:** Low. This is cleanup — no logic changes.

---

## Step dependency graph

```
Step 1 + 3 (guidelines schema, wired into consumers)  [done]
  │
  ├──▶ Step 2 (layout structural format)
  │       │
  │       └──▶ Step 7 (shipped layouts + examples)
  │                │
  │                └──▶ Step 8 (test sweep)
  │
  ├──▶ Step 4 (visual inheritance)  [independent]
  │
  └──▶ Step 5 (spec enhancements)  [independent]
            │
            └──▶ Step 6 (wire into render)
```

Steps 4 and 5 can happen in parallel with step 2. Step 1 had to be first
because everything reads from `Guidelines` — and step 3 turned out to be
inseparable from it (the field paths *are* the interface), so the two
landed together.

---

## Status

- [x] Read the codebase and map current vs. proposed
- [x] Finalise guidelines core keys
- [x] Write `template/guidelines.template.yaml`
- [x] Phase 2: `template/layout.template.yaml`
- [x] Phase 3: `template/page.template.yaml`
- [x] Write `template/interactions.md`
- [x] Write `template/visuals.md` (visual type system — runtime, inheritance)
- [x] Write `template/extensions.md` (extension points by layer)
- [x] Compatibility analysis and incremental plan (this section)
- [x] Step 1: Guidelines schema rewrite (merged with step 3)
- [x] Step 3: Wire guidelines into consumers (done with step 1)
- [ ] Step 2: Layout structural format
- [ ] Step 4: Visual inheritance
- [ ] Step 5: Spec enhancements
- [ ] Step 6: Wire into render
- [ ] Step 7: Update shipped layouts and examples
- [ ] Step 8: Final test sweep
