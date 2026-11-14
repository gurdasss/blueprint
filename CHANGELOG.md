# Changelog

Blueprint is pre-alpha: anything can change between releases. Every Power BI format fact the
code relies on was verified in Desktop first (`blueprint/pbir/schema.md`, evidence in
`docs/probes/`).

## v0.10.1 (2026-11-14)

Packaging only; no behaviour change. First release published to PyPI as `blueprint-pbi`:
`pip install blueprint-pbi` gives the `bp` command, the 18 visual contracts, `defaults.yaml`
and the vendored PBIR schemas, and nothing else. Release metadata (SPDX licence, classifiers,
keywords, project URLs) and a `MANIFEST.in` that keeps the test suite out of the sdist, since
it needs `fixtures/` and the probe evidence that a release artifact doesn't carry.

## v0.10.0 (2026-11-13)

The rest of a Power BI theme's colour palette, and the one piece of conditional formatting a
real-report survey justified. Every fact was verified in Desktop as a candidate and then accepted
from Blueprint's own output (probes 42-51).

- **Sentiment colours: `palette.good`, `palette.neutral`, `palette.bad`.** `bp theme` writes them
  as the theme's own top-level keys. A KPI draws `good` at or **at-or-above** its goal and `bad`
  below it; a KPI with no goal draws no sentiment colour at all. **Nothing was ever seen to draw
  `neutral`** — it is written and kept, but what reads it is still open (probes 42, 43).
- **Divergent colours: `palette.minimum`, `palette.center`, `palette.maximum`.** They go to the
  theme, which makes them the defaults of every conditional-format gradient a person adds in
  Desktop. A **saved** gradient stores plain hex and does not follow a later theme change, so a
  theme key alone can only change future gradients (probe 44).
- **A table column can ask for a gradient**: `{field: ..., aggregate: sum, gradient: 2|3}` writes a
  `FillRule` background built from those three colours, so a client's colours land in the visual
  itself. Re-applying after the guidelines change rewrites the stops in place; a gradient the spec
  stops asking for is left alone, the user's other `values` entries survive, and rebinding a field
  drops the gradient that named it. Declared per contract (`gradient: true` on a table's `columns`)
  and verified from `bp apply` in probe 45.
- **Structural colours: `palette.second_level`, `third_level`, `fourth_level`, `disabled_text`**,
  named as Power BI's *Customize current theme* dialog labels them (first-level is `palette.text`,
  background is `palette.background`). Measured, not guessed: `second_level` paints the secondary
  grey text, `third_level` a dropdown slicer's border, `fourth_level` a multi-row card's accent
  bars, `disabled_text` the Filters pane edge (probes 46, 48, 49).
- **`bp check` compares all of these with the report's theme** and names the client's key, not the
  theme's internal one. The colours also count as approved colours for the palette rule. A
  gradient's own colours inside a visual are still an unchecked "colour expression".

**Deliberately not added**, each because a probe showed there was nothing to promise: the five
structural keys `backgroundNeutral`, `foregroundNeutralLight`, `backgroundDark`, `tableAccent` and
`shapeStroke`. A gallery of every visual type Blueprint builds showed **zero** pixels of them, and
probe 50 then ruled out hover, selection, focus, a table style preset, an inserted shape and an
inserted button too.

**Format facts settled along the way**, now in `blueprint/pbir/schema.md`:

- `ThemeDataColor.ColorId`, open since probe 02, is resolved: **0 is a fixed white and 1 a fixed
  black** (not the theme's background and foreground), `n >= 2` is `dataColors[n-2]` for the
  **first eight** data colours only, and `Percent` is a signed RGB tint (probe 47).
- Power BI's **modern** structural names (`secondLevelElements`, ...) are read by Desktop, but it
  writes the **legacy** names back and the legacy value wins when a file holds both — which is why
  Blueprint writes the legacy form (probe 51).

**New probe tooling**, both standard-library or built-in only:

- `scripts/probe_pixels.py` — a PNG reader that samples a pixel or counts a colour across a
  capture, so "what does this theme key paint?" is answered by measurement rather than by eye.
- `scripts/hover_capture.ps1` — moves the real cursor, optionally clicks or sends Tab, then
  photographs the screen, because the Desktop bridge's page screenshot can never show a hover,
  selection or focus state.

## v0.9.0 (2026-11-11)

The options and hierarchy wells the core was still missing, each verified in Desktop as a
candidate and then accepted from `bp apply` (probes 37-40).

- **`pie` and `donut` take `labels` and `legend`.** Their `labels` carries **both** values
  (`"on"` and `"off"`), because Desktop's default on these two types is labels *on* — every
  other chart ships `"on"` alone. Probe 37.
- **`scatter` and `map` take `legend`**, including on the map, which renders through a different
  control and might have had its own properties. They deliberately take **no `labels`**: probe 38
  wrote that object on both and Desktop's save *deleted* it.
- **A matrix's `rows` and a slicer's `field` accept a model hierarchy** (`Table[Hierarchy]`),
  which every chart's category already did. Probe 39 recorded Desktop's two shapes, which differ:
  a matrix marks the first level active and writes an explicit `"active": false` below it, a
  slicer marks every level. `matrix.columns` still refuses one — no probe has put a hierarchy
  there. A contract says which it wants with `active_levels: first|all` on the slot.
- **Probe 40 is the acceptance half**: five pages where every visual, option and hierarchy came
  from a spec, with nothing patched. Desktop changed no option and no projection Blueprint wrote,
  `bp check` found nothing, and a re-apply over its save changed nothing at all. Every legend
  position drew on every type, including the cells the candidate probes never saw.

## v0.8.1 (2026-11-11)

A fix and a documentation pass. The fix changes behaviour, so it is worth a line even though
nothing it refuses was ever doing anything: a wrong `--visuals` path now says so.

- `--visuals DIR` refuses a directory that doesn't exist, naming the flag, the way
  `extensions.custom_visuals.search_path` already did. It used to load nothing and exit 0, so a
  path that had gone away — `blueprint/visuals/archive`, removed in v0.8.0 — looked like it
  still worked.
- The docs caught up to v0.8.0, where the archive's removal and the three new types had left
  claims that were no longer true: `template/visuals.md` described a core of seven with the rest
  "deferred", the README's probe range stopped at 31, and `blueprint/defaults.yaml` offered
  `custom_visuals` as a way to reach types that are core now.

## v0.8.0 (2026-11-11)

Every visual type a Desktop probe has verified is now core. **Breaking:**
`blueprint/visuals/archive/` is gone, so a guidelines file that opts into it fails (see below).

- **Three new visual types**: `scatter` (`category`, `x`, `y`, `size`, `legend`),
  `multi-row-card` (one `fields` well taking columns and measures mixed — a column makes one row
  per value) and `map` (`category`, `size`, `legend`). Verified in probe 34 and accepted from
  `bp apply` in probe 36. **`map` draws only where Desktop's "Map and filled map visuals"
  security setting is on**, which is off by default.
- **Every probe-verified visual type is core**, so a spec uses all 18 with no opt-in and
  `bp describe` lists them: `area`, `bar`, `card`, `column`, `donut`, `header`, `kpi`, `line`,
  `map`, `matrix`, `multi-row-card`, `pie`, `scatter`, `slicer`, `stacked-bar`, `stacked-column`,
  `stacked-column-100`, `table`. The archive was a holding pen for the v0.6 refactor, not a
  permanent split: its eight types were promoted in batches as their Desktop evidence was
  confirmed (slicer and matrix: probes 20-21; pie and donut: 08, 11, 22-24; area and the stacked
  charts: 22-24 and 35).
- `area`, `stacked-column`, `stacked-column-100` and `stacked-bar` gained the `labels` and
  `legend` options (positions and `off`) the core's charts already had, so all seven chart types
  behave alike (probe 35).
- Hand-built visuals are unaffected: the manifest has always named those by PBIR type and query
  role, whatever contracts are loaded.

### Breaking: `blueprint/visuals/archive/` is gone

Every type it held is core, so nothing needs the opt-in any more. `--visuals DIR` and
`extensions.custom_visuals.search_path` stay — they are for contracts of **your own** now.

**Upgrading:** a guidelines file or `.blueprint.yaml` that still points a `search_path` at
`blueprint/visuals/archive` now fails with `... is not a directory`. Delete that
`custom_visuals` entry; the types it used to load are in the core.

## v0.7.0 (2026-11-11)

What a core-20% audit of the codebase found and fixed. **Breaking twice:** a guidelines file with
a key Blueprint doesn't implement is now refused instead of loading, and `--grid` is gone.

- **Guidelines: a key outside the core is refused, not ignored.** `spacing: {margn: 16}` used to
  load with the default margin, so the file said one thing and `bp check` did another. Unknown
  keys and sub-keys are now an error naming the closest real key (`did you mean margin?`).
  `extensions:` stays open, so an extension's own keys still pass through untouched.
- **Layer 4 covers the whole guidelines file.** `--set KEY=VALUE` (repeatable, value read as
  YAML) on every command that reads guidelines — `check`, `fmt`, `apply`, `describe`, `manifest`,
  `theme` — instead of `--grid` on two of them. `--grid` is refused by name, with `--set
  spacing.grid=N` given as its replacement. `fmt` and `apply` now pass the same overrides to the
  manifest they rebuild afterwards, which silently used the un-overridden guidelines.
- Which query well carries Desktop's `"active"` flag is declared by each visual contract
  (`active: true` on the slot) instead of a table of visual-type names in core code. No output
  changes; a custom visual can now declare it without a code change, and core code no longer
  carries the shape of the archived types a client never opted into.
- `template/guidelines.template.yaml`, the annotated file a client starts from, was missing two
  implemented core keys (`page.title_region`, `palette.extra`).

### Upgrading from v0.6.x

- Run `bp check` once against each guidelines file you keep. A key Blueprint doesn't implement
  now fails with the closest real key named, where before it loaded and quietly did nothing.
- Replace `--grid N` with `--set spacing.grid=N`. It is refused by name, so nothing fails silently.

## v0.6.0 (2026-11-11)

The template rewrite: Blueprint's input files redone from the client's side. **Breaking:** the
guidelines schema changed, and the old keys are refused with the replacement named.

### Breaking: guidelines schema

- Core keys are `version`, `name`, `canvas` (width, height), `spacing` (`grid`, `margin`,
  `gutter`), `page`, `palette`, `typography` and `layouts`. Rule severities are baked into code.
- Retired keys: `grid.size` → `spacing.grid`; `canvas.margin`/`canvas.gutter` →
  `spacing.margin`/`spacing.gutter`; `grid.snap` (gone, `bp fmt` always snaps); `grid.max_resize`,
  `check.severity`, `check.decorative_types` → `extensions.*`.
- Typography roles are `page_title`, `visual_title` and `body`; `subtitle`, `callout` and
  `card_label` live under `extensions.typography`. `bold` is gone (a weight is part of the face
  name), which drops the check of a textbox run's own `fontWeight`.
- Opt-in settings live under `extensions:` (`severity`, `decorative_types`, `max_resize`,
  `typography`, `custom_visuals`). Findings and theme notes name the client's key.
- `bp describe` reports `spacing: {grid, margin, gutter}`.

### Visual types

- The core ships seven types: `header`, `card`, `kpi`, `column`, `line`, `bar`, `table`. The
  other eight (`pie`, `donut`, `slicer`, `matrix`, `area`, `stacked-column`,
  `stacked-column-100`, `stacked-bar`) are archived in `blueprint/visuals/archive/` and load only
  through `extensions.custom_visuals.search_path` or `--visuals DIR` on `apply`, `describe` and
  `manifest`. Their behaviour is unchanged.
- A visual contract can `inherits:` another; `bar` now inherits `column`.

### Specs

- A slot entry may be `{field, aggregate, format}`. `aggregate` (`sum`, `average`, `min`, `max`,
  `count`, `distinctcount`) summarises a column in the visual; `format` is a Power BI format
  string, written as given (probes 29 and 30).
- `sort: {by, direction}` per visual (probe 31). `by` must be a field the visual binds. A spec
  without `sort` leaves Desktop's or the user's sort alone; before, a user's sort was discarded
  when a re-apply changed the fields.
- `labels` and `legend` options now work on `bar` and `line` as well as `column` (probe 31).
- A Legend column on `column` and `bar` (`legend: "Sales[Region]"`), one column, with a
  drill-down allowed beside it. Several measures with it, or a second Legend column, are
  refused, as Desktop does (probe 32).
- `legend: off` on `column`, `bar` and `line` (`legend.show = false`). One option is one state:
  choosing it removes `position`, and choosing a position removes `show`.
- `totals: on|off` on `table` (`total.totals`; Desktop's default is on).
- Desktop accepts what `bp apply` writes for all of these, and keeps it through a refresh and save
  (probe 33, which also showed `legend: off` -> `top` on re-apply leaves the legend visible).

### Under the hood

- Probe replays and tests extended through probe 31 (687 tests). Apply's golden output is
  byte-identical to v0.5.1 apart from the version in the manifest.

## v0.5.1 (2026-11-10)

Fixes from an audit (fresh installs, a real report, fuzzing, Windows-style input, Desktop checks):

- Specs, guidelines and layouts in UTF-16 (Windows PowerShell 5's default) or with a BOM load;
  undecodable bytes are a clear error. They crashed with a traceback.
- Fuzzing found tracebacks on spec keys that are numbers or null, and on wrong-typed guidelines
  values; both are clear errors now (0 crashes in 6000 specs, 4800 guidelines, 1500 layouts).
- A field the model doesn't have gets a suggestion: the same name in the model's case, or close
  spellings (`no measure [total amount] … (did you mean [Total Amount]?)`).
- `bp describe` shows which slot lists exclude another slot (several measures with a Legend).
- `bp theme --replace-theme` works on a report with no base theme (Microsoft's Retail sample).
- The CI action: a notice when GitHub won't annotate every finding (10 errors and 10 warnings per
  step), and `reports` lines may be globs.
- The README's spec example used a `kpi-row` visual type that never existed; README specs and
  guidelines are now tested. The quick start's spec and `describe`'s example no longer leave a
  gap. Clearer messages for a spec marking several pages and for an empty layouts search path.

## v0.5.0 (2026-11-10)

- `line` and `area` take a drill-down of plain columns on `category`
  (`category: ["Sales[Country]", "Sales[Region]"]`), verified in Desktop (probe 27).
- Probe 27 also showed Desktop refuses a second Legend column on line and area charts ("too many
  columns in the Legend bucket"), so the Legend stays one column.
- A drill-down together with a Legend is allowed on line, area and the stacked charts (probe 28).
  Several measures together with a Legend stay refused: Desktop draws the same error.
- Chart option `legend: bottom` (probe 28, against a theme defaulting to Top).

## v0.4.0 (2026-11-10)

The first release, covering roadmap v0.1–v0.4: read, align, validate, generate and bind.

### Commands

- `bp inspect`: pages, visuals, IDs and positions (`--json`).
- `bp fmt`: snap visuals to the guidelines grid, idempotently. Skips `blueprint.ignore`
  visuals, grouped visuals and pages with no fixed size.
- `bp check`: validate against guidelines. Rules `bounds`, `grid`, `margin`, `gutter`,
  `overlap`, `page-size`, `density`, `palette`, `typography`, `title` and `format`
  (schema validation against vendored Microsoft schemas). Exit 0 clean, 1 failing findings,
  2 unreadable; `--strict`, `--json`, `--github`.
- `bp apply`: build or update pages from YAML page specs; several specs or folders at once,
  all checked before anything is written. Re-applying updates positions, titles, fields and
  options in place, and refuses to undo edits made in Desktop unless `--overwrite-edits`.
- `bp describe`: everything a spec writer (or an LLM agent) can use, in one call, including the
  model's fields in spec syntax (`--json`).
- `bp manifest`: the `.blueprint.manifest.json` handoff file, rebuilt from the report.
- `bp theme`: a custom theme from the guidelines (palette, text colour, title, callout and card
  label fonts), as overrides on the base theme.

### Visuals and bindings

- 15 visual types: card, column, bar, line, area, pie, donut, table, matrix, KPI (with target),
  slicer (list or dropdown), stacked column, 100% stacked column, stacked bar, and the page
  header textbox.
- Bindings: measures, columns, drill-downs, date columns and model hierarchies; several
  measures on column, bar and line values; chart options `labels` and `legend`.

### Layouts

- `standard-4-up`, `dashboard-6`, `kpi-row-plus-detail`, `grid-2x3`, `two-up` and `one-up`,
  all 1280×720 on the 8px grid. KPI rows are 160px.
- A spec visual's `region:` can override its type's role (cards in a KPI row).
- `bp apply` warns when a layout leaves a region empty and names the layouts that fit the spec
  with no gap. Layouts are never reflowed.

### CI

- A composite GitHub Action: `uses: gurdasss/blueprint@v0.4.0` runs `bp check` over one or
  more reports, annotating each finding on its `page.json` or `visual.json`, with each
  report's output in the job summary.

### Known limits

- PBIP projects in the PBIR format only (PBIR-Legacy is refused), with the TMDL model
  alongside; thin reports are out of scope.
- Open format questions (not yet used by the code) are listed in `blueprint/pbir/schema.md`.
