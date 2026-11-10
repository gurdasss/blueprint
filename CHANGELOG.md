# Changelog

Blueprint is pre-alpha: anything can change between releases. Every Power BI format fact the
code relies on was verified in Desktop first (`blueprint/pbir/schema.md`, evidence in
`docs/probes/`).

## Unreleased

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
