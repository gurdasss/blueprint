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

**The rule for this version:** the core is deliberately dumb and follows the
client's files to the letter, in one client-friendly unit per thing. It
verifies what the client wrote and refuses what breaks the guidelines; it
does not derive, infer or compute on the client's behalf. Anything that
needs a second unit, or a judgement call the client didn't make, is an
extension — that is what dropped step 2 (see below), and it is the test to
apply to steps 4-6 as well.

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

The PBIR layer, model, and render path are untouched. The guideline schema is
the one area that changes significantly. The layout format doesn't change at
all (see "Layouts" below), and the page spec changes are small.

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

#### Layouts — unchanged (100% compatible)

The pixel format stays: `canvas` + `regions` with explicit `x/y/w/h`. The
structural-rows engine that an earlier draft of this plan called for is **not
built** — it is a later version, recorded in `template/extensions.md`.

| Module | Why it's unchanged |
|--------|-------------------|
| `layouts.py` | `parse()` keeps reading pixel regions. No `compute_regions()`. `place()`, `find()`, `available()`, `load()`, `conflicts()`, `unused()` already do their jobs. |
| `guidelines/layouts/*.yaml` | The six shipped layouts are already in the final format, already on the grid, already inside the margin. |
| `tests/pinned-layouts/` | Probes 9/14/17/19 pinned `standard-4-up` at 120px; nothing has to be re-pinned. |

**Why:** one unit, stated by the client, verified by the tool. `conflicts()`
already refuses a layout that is off the grid, inside the margin or closer
than the gutter, naming the breakage, so an explicit coordinate is checked
rather than trusted. A generative engine would instead make three silent
choices (widen which gutter, place the leftover pixels where, round which
way) that nothing else in Blueprint takes the liberty of making — and the
arithmetic is cheap for the client that actually writes these files, an LLM
agent. `template/layout.template.yaml` carries the worked numbers.

#### Tests

| Test area | Impact |
|-----------|--------|
| `tests/test_guidelines.py` | Rewrite — tests the guideline schema directly. |
| `tests/test_layouts.py` | Minor — field paths only (`g.spacing.*`). Layout parsing and placement tests stay. |
| `tests/test_spec.py` | Add tests — pipe syntax, long-form slots, named formats. |
| `tests/test_validate.py` | Minor — remap field paths, typography role names. |
| `tests/test_apply_golden.py` | Unchanged until steps 5-6. Guidelines and layout changes must not alter a byte. |
| `tests/test_probe_replay.py` | Minor — probe 15's guidelines fixture only; layout fixtures untouched. |
| `tests/test_robustness.py` | Minor — adapt to the new guideline shape. |
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
rather than being deleted.

`bold` is gone everywhere, which **drops a check**: for a visual's text a weight is part
of the face name (`Segoe UI Semibold`), so nothing is lost there, but a textbox run does
carry its own `fontWeight` (probe 03) and a guidelines file could previously require or
forbid it. Bold textboxes now go unchecked. Re-add it as an extension rule if clients
want it back.

**Carried forward:** one item of the old step 3 depends on a later step and is *not*
done — `describe.py` listing named formats (moved to step 6). The other, `apply.py`
passing layout rows through `compute_regions()`, no longer exists: step 2 is dropped.

**Tests:** `test_guidelines.py` rewritten (new paths, retired-key errors, role mapping).
Old YAML in the other tests rewritten. `test_apply_golden.py` and `test_probe_replay.py`
pass **without** `BLUEPRINT_UPDATE_GOLDEN=1` — nothing in this step may change apply's
output, and `example.yaml`'s `page_title` is the old `header` value. `scripts/demo.sh`
runs clean and is still idempotent.

**Result:** 582 passed, `ruff` clean.

### Step 2 (dropped): layout structural format

**Decision:** not built in this version. Layouts stay explicit pixels, the
format `layouts.py` already reads. Relative positioning (rows, column
counts, computed coordinates) is a later version, written up as an extension
point in `template/extensions.md` with the remainder rule it would need, so
it doesn't have to be re-derived.

**What replaced it:** `template/layout.template.yaml` restored to the pixel
format (canvas width/height back, explicit regions), with the column and row
arithmetic worked out in the file — including what a region flush to the
margin needs (`margin % grid == 0`, and the usable span a grid multiple) —
a condition on that convention, not on the guidelines, since a grid of 10
with margin 16 is fine for regions starting at 20 — and the solved column
table (2 -> 616/16,
3 -> 400/24, 4 -> 288/32, 5 -> 224/32, 6 -> 168/48). A test parses the
template and asserts `conflicts()` finds nothing against the template
guidelines, so the two template files can't drift apart.

**Still open, cheap, not done:** `conflicts()` could warn when a `kpi-row`
region is under 160px. That number is measured (bridge screenshots: at 120px
Desktop clips a KPI's goal line and a titled card's label) and currently
lives only in a comment in six layout files.

### Step 4 (done): core seven visual types, and `inherits:`

**4a — the core ships seven types.** `header`, `card`, `kpi`, `column`, `line`,
`bar`, `table`. The eight other probe-verified contracts (`pie`, `donut`,
`slicer`, `matrix`, `area`, `stacked-column`, `stacked-column-100`,
`stacked-bar`) moved to `blueprint/visuals/archive/`, which the loader doesn't
glob. Archived, not deleted: each still cites its probe.

A client opts them back in, per the seam `template/extensions.md` promised:

```yaml
extensions:
  custom_visuals:
    search_path: ["../blueprint/visuals/archive"]   # relative to this file
```

or `--visuals DIR` for one run (`apply`, `describe`, `manifest` — guideline
layer 4). `contracts(extra)` keys the path into its cache, loads core-first,
and refuses a type — or a PBIR `visual_type` — claimed twice. Every production
call site passes `rules.visuals`: a missing contract doesn't fail loudly in
`manifest`, it quietly drops slot names.

Evidence kept, not traded away: the probe replays, `test_visual_types`,
`test_options` and the real-report test opt in, so Desktop's shapes for all
15 types still replay. The demo opts in through its `.blueprint.yaml` and its
output is byte-identical to a pre-change run. `tests/pinned-specs/` (new, like
`pinned-layouts/`) holds probe 9's spec, which used `pie`.

**4b — `inherits:`** resolves as `template/visuals.md` documents: the parent's
`slots`, `options` and `region` are copied and the child overrides them key by
key, so it can change one slot without restating the rest. `type` and
`visual_type` are never inherited — a contract that didn't name its own PBIR
type would silently claim its parent's. Refused: cycles (naming the chain),
self-inheritance, an unknown parent (listing what is loaded), a core contract
inheriting from outside the core (the core must load on its own), and two
types claiming one `visual_type`.

**A defect worth remembering:** `--visuals` first went in as a plain override layer, and
`merge()` replaces lists — so passing it to a report that already opted in through its
guidelines silently dropped that opt-in. It also wasn't on `check` or `fmt`, both of which
render the manifest, so a `bp fmt` after an archived-type `apply` rewrote those entries as
`"type": "pieChart"` with raw query roles (`Category`/`Y`). Reproduced, then fixed:
`guidelines.load(visuals=...)` **adds** the directories, and the flag is on every command
that reads contracts. Two regression tests cover it. The lasting opt-in belongs in
guidelines; the flag is for one run.

**The shipped contracts deliberately don't use it.** `bar`'s slots are
`column`'s, but `options` aren't slots: probe 23 verified data labels and
legend position on the column and stacked charts, never on the clustered bar,
so `bar: inherits: column` would ship an option no probe checked. Inheritance
is for types a client adds. A test pins that reasoning.

**Result:** 598 passed, `ruff` clean, demo byte-identical.

### Step 5 + 6 (done): one way to say more about a field

**The decision.** A slot's field is a **string**; anything further is a **mapping key**:

```yaml
value: "[Total Revenue]"                       # a field, the common case
value: {field: "Sales[Amount]", aggregate: sum, format: "#,0.00"}
```

Pipe syntax is dropped: `"Sales[Amount] | distinctcount"` was a second language inside a string,
invisible to YAML and to the parser's error locations, saying what `aggregate:` says. The short
string stays as the shorthand for "just the field" — `"X"` means `{field: X}`.

**Probe 29 settled both shapes** (`docs/probes/29-aggregate-format.diff`), each aggregation taken
on a *fresh* field because one changed in place keeps its old `queryRef`:

| Desktop's menu | `Function` | `queryRef` | `nativeQueryRef` |
|---|---|---|---|
| Sum | 0 | `Sum(Sales.Amount)` | `Sum of Amount` |
| Average | 1 | `Avg(Sales.Amount)` | `Average of Amount` |
| Count (Distinct) | 2 | `Count(Sales.Amount)` | `Count of Amount` |
| Minimum | 3 | `Min(Sales.Amount)` | `Min of Amount` |
| Maximum | 4 | `Max(Sales.Amount)` | `Max of Amount` |
| Count | 5 | `CountNonNull(Sales.Amount)` | `Count of Amount` |

Guessing would have been wrong twice over: the codes don't follow the menu order, and the UI's
"Count" is 5 while "Count (Distinct)" is 2.

A per-visual format is a **projection key**, exactly where the vendored schema said:
`"format": "\"₹\" #,0.###############;…"`. Desktop wrote the *locale's* currency symbol, which
settles the named-format question: a `currency` alias would make Blueprint invent a symbol the
client never stated, so the core takes the string and the template lists copyable ones. A
measure's format is a different thing and lives in TMDL, which Blueprint only reads.

**What shipped:** the long form in `spec.py` (`FieldRef.aggregate`/`.format`), the shapes in
`render.Binding`, the codes in `reader.AGGREGATE_FUNCTIONS` so a re-read round-trips, the
`aggregate`-needs-a-measure-slot rule, a changed format rewriting the query on re-apply, and
`bp describe` listing both keys. Two fields Desktop would name alike (count and distinct count of
one column) are refused rather than guessing its suffix rule.

**Verified end to end.** Probe 30 applied all six aggregations and four format strings across
cards, column charts and a table; Desktop drew every one, wrote its own subtitles from the
bindings, and its save changed nothing Blueprint wrote (only the `$schema` bump, its auto
`filterConfig` and `activePageName`). Both probes replay in CI.

### Step 7 (mostly done): shipped layouts and example files

**What's left:** nothing for layouts — the six shipped files are already in
the format the tool reads, on the grid and inside the margin. `example.yaml`
moved to the new guidelines schema in step 1, and `scripts/demo.sh` runs
clean and idempotent.

**What remains for later steps:** demo specs may gain named formats and
aggregation syntax once steps 5 and 6 land; the demo is the integration test
for those.

**Golden output:** must stay byte-identical. No step may need
`BLUEPRINT_UPDATE_GOLDEN=1` unless it deliberately changes what `apply`
writes (steps 5 and 6 will; nothing before them does).

### Step 8 (done): test sweep

**What it turned out to be.** The plan expected this step to regenerate golden output and fix
fixtures still on the old schema. Neither was needed: each step fixed its own tests as it
landed, and **golden output is byte-identical to `main` across the whole branch**
(`git diff main -- tests/golden` is empty). So the sweep became a hunt for the drift this branch
kept producing — a key renamed in code but not in the file a client copies — plus the checks
that make that drift fail loudly in future.

**Found and fixed:**
- `bp fmt` warned `96% > grid.max_resize 25%`, naming a key the loader refuses. Now
  `extensions.max_resize`.
- `scripts/probe_annotations.py` wrote a `.blueprint.yaml` of `grid: {size: 16, max_resize: …}`,
  so re-running probe 01 would have failed at guidelines load.
- `template/interactions.md` described guidelines as `grid: 8, margin: 16, gutter: 16`.
- **A packaging hazard, found by building a wheel rather than trusting the globs:** setuptools
  copies into `build/lib` and never removes anything, so a wheel built in a tree with a stale
  `build/` shipped the eight archived contracts as `blueprint/visuals/*.yaml`. A pip-installed
  client would have seen 15 core types and no archive. A clean build is correct (7 + 8), the
  hazard is documented next to the build command, and a test fails on a stale `build/lib`.

**New: `tests/test_consistency.py`**, pinning the claims the shipped files make:
- no file in `guidelines/`, `template/` or `examples/` uses a retired key (parametrised per file)
- every `extensions.*` key the core reads is documented in **both** `defaults.yaml` and the
  guidelines template, and every key those files show actually loads (`guidelines.EXTENSION_KEYS`
  is now the single source)
- the core contract set matches `slots.CORE_TYPES` and the files on disk
- every `*.yaml` under `blueprint/` matches a `package-data` glob (globs don't recurse)
- no string literal in `blueprint/` names a retired key (checked over the AST, so attribute
  access like `rules.check.severity` doesn't false-positive)
- every rule id has a severity and vice versa (ids are a CI contract)
- the README's command lines only use flags that exist
- nothing stale lingers in `build/lib`

**Verified green:** 633 passed, `ruff` clean, `bp check` exit 0 on both real samples,
`scripts/demo.sh` clean and idempotent, demo output byte-identical to a pre-branch run apart
from its opt-in lines, and a clean wheel ships 7 core + 8 archived contracts.

---

## Step dependency graph

```
Step 1 + 3 (guidelines schema, wired into consumers)  [done]
  │
  ├──▶ Step 2 (layout structural format)  [dropped: pixels stay]
  │       └──▶ Step 7 (shipped layouts + examples)  [already conform]
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

### Basic richness for the core seven (probe 31)

The core was minimal in the wrong places: `column` carried `labels` and `legend` while the
equally-core `bar` and `line` carried none, and the **archived** stacked charts were richer than
either. That was an accident of probe history — probe 23 happened to cover column and the stacked
charts — not a decision.

Probe 31 fixed both halves of that:

- **Options parity.** Probe 23's shapes, written onto a clustered bar and a line as candidates,
  drew in Desktop and survived its save untouched. `bar` and `line` now ship `labels` and
  `legend`, so the three core chart types behave the same. A side effect: `bar` became identical
  to `column` apart from the PBIR type, so it is the shipped set's one `inherits:` user — the
  feature built in step 4 finally earns its place, and only once a probe allowed it.
- **Sort.** `sort: {by, direction}` per visual, writing `query.sortDefinition` **without**
  `isDefaultSort`. The probe showed that flag marks only the sort Desktop adds by itself, and
  that sorting back to Desktop's own choice does not bring it back — so a sort Blueprint writes
  is an explicit one. `by` must be a field the visual binds, or Desktop ignores it. A spec with
  no `sort` leaves whatever is there, which also fixes a quiet bug: a sort set in Desktop used to
  be discarded whenever a rebind changed the fields.

Probe 32 reversed part of that. A survey of two real reports (48 visuals, counts only) found a
Legend column on 3 of 6 clustered column/bar charts, `legend.show = false` on 5 of 18 legends
and `total.totals` set on 2 of 2 tables, and none of it had a probe. The core could not draw
"sales by region, split by category" at all (only the archived stacked charts could), so the
earlier "not basic" call was wrong for the legend binding, and it follows the same
one-unit-per-thing rule as `category`: one column in one well, nothing derived. Now core:

- **A Legend column on `column` and `bar`** (`legend` slot, role `Series`, no `active`), one
  column, with `value` excluding a list beside it, exactly as `line` has had since probes 27/28.
  Desktop refused several measures with a Legend, and two Legend columns, on the clustered
  charts too.
- **`legend: off`** (`legend.show = false`) on column, bar and line. One option is one state:
  choosing `off` removes `position` and choosing a position removes `show`, so a legend moved from
  `off` to `top` isn't left hidden.
- **`totals: on|off`** on `table` (`total.totals`). Desktop's default is on.

Still left out, as not "basic": axis titles (zero uses in the survey, and no `valueAxis` at all),
conditional formatting (zero shapes), and the `map`, `scatter` and `multiRowCard` types, which
real reports use and neither the core nor the archive covers.

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
- [x] Step 2: Layout structural format — dropped, pixels stay (see above)
- [x] Step 4: Core seven visual types + `inherits:`
- [x] Step 5: One way to say more about a field (probe 29 settled the shapes)
- [x] Step 6: Aggregation and format wired into render
- [x] Step 7: Shipped layouts and examples (layouts already conform)
- [x] Step 8: Test sweep + consistency checks
