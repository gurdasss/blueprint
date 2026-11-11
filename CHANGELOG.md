# Changelog

Blueprint is pre-alpha: anything can change between releases. Every Power BI format fact the
code relies on was verified in Desktop first (`blueprint/pbir/schema.md`, evidence in
`docs/probes/`).

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
