# Blueprint

[![test](https://github.com/gurdasss/blueprint/actions/workflows/test.yml/badge.svg?branch=main)](https://github.com/gurdasss/blueprint/actions/workflows/test.yml)

**Declarative, deterministic Power BI report layouts.** Write a short YAML file, get a
PBIP report whose pages are built and aligned to your organisation's design guidelines —
no dragging, no nudging, no eyeballing.

```bash
bp apply pages/sales-overview.yaml --report ./SalesReport.Report
```

> **Status: pre-alpha.** Nothing here is stable. Every Power BI format fact the code relies on
> was verified in Desktop first — see [How the PBIP format is learned](#how-the-pbip-format-is-learned).
> Do not point this at a report you care about. Work on copies, under version control.

---

## Contents

- [Why this exists](#why-this-exists)
- [What Blueprint does and does not do](#what-blueprint-does-and-does-not-do)
- [Design principles](#design-principles)
- [Install](#install)
- [Quick start](#quick-start)
- [Page specs](#page-specs)
- [Guidelines and layering](#guidelines-and-layering)
- [The manifest](#the-manifest)
- [Project structure](#project-structure)
- [How the PBIP format is learned](#how-the-pbip-format-is-learned)
- [Fixtures and testing](#fixtures-and-testing)
- [Version compatibility](#version-compatibility)
- [Roadmap](#roadmap)
- [Non-goals](#non-goals)
- [Using this with client work](#using-this-with-client-work)
- [License](#license)

---

## Why this exists

Two things are true about Power BI report development:

1. **A large share of the work is mechanical.** Placing visuals, aligning them, matching
   sizes, applying the palette, getting margins consistent across pages. It takes hours
   and produces nothing anyone values.
2. **Design guidelines get ignored.** Not out of malice — following a style document by
   hand, under deadline, across several developers, simply doesn't hold. Reviewers end up
   policing consistency manually, report by report, team by team.

Blueprint attacks both by moving layout from *a thing a human does in a GUI* to *a thing
a program does from a spec*. Guidelines stop being a document people are asked to
remember and become configuration the generator enforces. Consistency becomes the
default rather than the exception.

A secondary benefit, arguably the bigger one: **report changes become reviewable.** A
page spec is a short text file. It diffs. It goes in a pull request. Reviewing
"added a page with four visuals bound to these measures" is tractable in a way that
reviewing a binary report file is not.

### Where this sits

Blueprint handles **report layout only**. It is designed to sit alongside, not replace:

| Concern | Tool |
|---|---|
| Semantic model — tables, columns, measures, relationships, DAX | [Power BI Modeling MCP server](https://github.com/microsoft/powerbi-modeling-mcp) |
| Report layout, page structure, visual placement, guideline conformance | **Blueprint** (this tool) |
| Live reload of a running Power BI Desktop instance | Power BI Desktop Bridge |

An AI agent driving this stack calls the Modeling MCP for the model and `bp` for the
report. Neither one writes PBIR JSON by hand.

---

## What Blueprint does and does not do

**Does:**

- Create pages from a declarative spec
- Place visuals according to named layouts (`standard-4-up`, `kpi-row-plus-detail`, …)
- Snap existing visuals to a grid (`bp fmt`; each edge to the nearest grid line)
- Enforce palette, margins, title placement and page density from a guidelines file
- Validate a report against guidelines without changing it (`bp check`)
- Emit a manifest mapping visual IDs to types, pages, titles and field bindings
- Support several guideline sets so different teams or clients can share one tool

**Does not:**

- Replace Power BI Desktop. You will still open it to verify, and for the last stretch of
  formatting this tool doesn't cover.
- Touch the semantic model. No measures, no DAX, no relationships.
- Move content between pages on its own. It will *warn* that a page is over budget.
  Deciding what to do about that is a human's job (see [Design principles](#design-principles)).
- Guess. Where the spec is ambiguous, Blueprint errors rather than inventing a layout.

---

## Design principles

**1. Deterministic.** The same spec plus the same guidelines produces byte-identical
output. No model in the generation path, no randomness, no token cost. An LLM may *write*
the spec; it never writes the PBIR.

**2. Generate loosely, validate strictly.** Producing files is one job; guaranteeing they
conform is another. The validator is a separate, dumb, deterministic pass. It is also
available on its own (`bp check`) so it can run in CI over reports Blueprint didn't build.

**3. Idempotent.** `bp fmt` run twice must produce no diff on the second run. This is a
test, not an aspiration — see `tests/test_idempotence.py`.

**4. Never destroy, never silently relocate.** Irreversible or surprising operations are
refused, not performed. A formatter that reformats a file is useful; one that moves code
into a different file is hated. Blueprint warns and exits non-zero instead.

**5. Config over code.** Grid size, margins, palette, density budgets and layout
definitions live in data, not in Python. The guidelines will change next quarter; that
must not mean a code change.

**6. Escape hatches are mandatory.** Someone will deliberately place a visual off-grid for
a good reason. `blueprint: ignore` on a visual must be honoured, or the tool gets switched
off permanently.

---

## Install

Built and tested on **WSL2 (Ubuntu) + Python 3.12**.

```bash
git clone https://github.com/gurdasss/blueprint.git
cd blueprint

python3.12 -m venv .venv
source .venv/bin/activate

pip install -e ".[dev]"
```

Verify:

```bash
bp --version
pytest
```

Blueprint reads and writes files on disk. It does not need Power BI Desktop installed, and
it does not need Windows. Desktop is only required to *look* at the result, and to run the
Desktop Bridge for live reload.

---

## Quick start

Against one of the bundled fixtures, so you can't break anything real:

```bash
# 1. Copy a fixture so the original stays pristine
cp -r fixtures/02-card-and-chart /tmp/demo
cd /tmp/demo && git init && git add -A && git commit -m "baseline" && cd -

# 2. Look at what's there
bp inspect --report /tmp/demo/Fixture.Report

# 3. Check it against the example guidelines (expect failures)
bp check --report /tmp/demo/Fixture.Report --guidelines guidelines/example.yaml

# 4. Build a page from a spec
bp apply examples/sales-overview.yaml \
        --report /tmp/demo/Fixture.Report \
        --guidelines guidelines/example.yaml

# 5. See exactly what changed (a new page, three visuals, pages.json and the manifest)
cd /tmp/demo && git status --short && cd -

# 6. Align the rest of the report: snap hand-placed visuals, apply the guidelines theme
bp fmt   --report /tmp/demo/Fixture.Report --guidelines guidelines/example.yaml
bp theme --report /tmp/demo/Fixture.Report --guidelines guidelines/example.yaml

# 7. Check: 0 errors. The two warnings left are judgement calls on the hand-built page
#    (its 1920x1080 size, and a visual at the page edge), which Blueprint reports but never forces.
bp check --report /tmp/demo/Fixture.Report --guidelines guidelines/example.yaml
```

Then open the report in Power BI Desktop and look at it.

### Commands

| Command | What it does |
|---|---|
| `bp inspect` | Print the report's pages, visuals, IDs and positions. Read-only. |
| `bp check` | Validate against guidelines. Read-only. Non-zero exit on violations. |
| `bp fmt` | Snap existing visuals to the grid (each edge to the nearest line). Idempotent. |
| `bp describe` | Everything a spec can use: spec syntax, visual types and slots, layouts and regions, guideline limits, and with `--report`, the model's fields in spec syntax and the pages specs built. Read-only. |
| `bp apply <spec>...` | Create or update pages from page specs (files or folders of them). All are checked before anything is written. |
| `bp manifest` | (Re)generate the manifest from the report's current state. |
| `bp theme` | Write a custom theme from the guidelines (palette, text colour, title/callout/card label fonts) and make the report use it. |

`--dry-run` is available on every mutating command and prints the planned file writes
without performing them. `inspect`, `check` and `describe` take `--json`; `check` also takes `--github`.

Every command that reads guidelines takes **`--set KEY=VALUE`** (layer 4), repeatable: the key is
a dotted path into the guidelines file and the value is read as YAML, so types survive.

```bash
bp check --report ./Sales.Report --set spacing.grid=4 --set page.max_visuals=8
bp fmt   --report ./Sales.Report --set spacing.grid=16
```

A key outside the core is refused there as in a file, naming the closest real one
(`--set spacing.margn=4` → `did you mean margin?`). `--grid` was the earlier, single-key form of
this and now names its replacement.

**For agents writing specs:** run `bp describe --report <report> --json` first. It's the whole
vocabulary in one call: which types, slots, layouts and fields exist, written the way a spec uses
them. `bp apply` reports every problem with its location (`visuals[2].slots.value: …`), and
`bp check --json` validates the result.

### In CI

`bp check --github` prints a GitHub Actions annotation per finding, on the `page.json` or
`visual.json` it's about, before the usual report. The repository is also a composite action
that installs Blueprint and runs it over one or more reports:

```yaml
# .github/workflows/report-standards.yml
name: report standards
on: [pull_request]
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: gurdasss/blueprint@v0.7.0        # a release tag (or commit SHA) pins Blueprint
        with:
          reports: |                           # one per line: .Report folder, .pbip, its folder, or a glob
            reports/Sales.Report
            reports/Operations.pbip
          guidelines: guidelines/corp.yaml     # optional; else $BLUEPRINT_GUIDELINES, else defaults
          strict: false                        # true fails on warnings too
```

The job fails if any report has errors (exit 1) or can't be read (exit 2). Each report's text
output goes to the job summary, and the `exit-code` output holds the worst exit code.
A report's own `.blueprint.yaml` still applies, as it does locally. GitHub shows at most 10 error and
10 warning annotations per step (50 per job) and drops the rest silently, so when a report has
more, `bp check --github` adds a notice saying how many aren't annotated; the job summary always
has every finding.

---

## Page specs

A page spec is the input a human — or an AI agent — writes. It describes *intent*, not
geometry.

```yaml
# specs/sales-overview.yaml (examples/ has runnable specs for the bundled fixtures)
# id: sales-overview    (optional; defaults to the file name. See "Which page a spec builds" below.)
page: Sales Overview
layout: standard-4-up

visuals:
  - type: header
    title: Sales Overview

  - type: kpi                  # fills the KPI row (a kpi's default region)
    title: Sales vs target
    slots:
      value: "[Total Sales]"
      trend: "Calendar[Month]"
      target: "[Sales Target]"

  - type: bar
    title: Sales by Category
    slots:
      category: "Product[Category]"
      value: "[Total Sales]"

  - type: column
    title: Sales by Geography
    slots:
      # an ordered list makes this a drill-down path
      category:
        - "Geography[Country]"
        - "Geography[State]"
        - "Geography[City]"
      value: "[Total Sales]"

  - type: table
    blueprint: ignore          # hand-placed on purpose; leave it alone
```

A visual may also set **options**, formatting choices its type declares (`bp describe` lists
them). Leaving one out keeps Desktop's default:

```yaml
  - type: line
    options: { labels: on, legend: right }   # data labels on, legend on the right (probe 23)
    slots: { category: "Calendar[Month]", value: ["[Total Sales]", "[Sales Target]"] }
```

A slot entry can say more than a field name. The long form is `{field, aggregate, format}`;
`"X"` is shorthand for `{field: X}`. `aggregate` summarises a **column** in the visual
(`sum`, `average`, `min`, `max`, `count`, `distinctcount`) and is allowed only in a slot that
takes a measure. `format` is a Power BI format string, written as given (probes 29 and 30):

```yaml
page: Sales Detail
layout: two-up

visuals:
  - type: column
    title: Average amount by country
    slots:
      category: "Sales[Country]"
      value: { field: "Sales[Amount]", aggregate: average, format: "#,0.00" }
    sort: { by: "Sales[Country]", direction: ascending }

  - type: table
    title: Orders
    slots:
      columns: ["Sales[Country]", { field: "Sales[Amount]", aggregate: sum, format: "$#,0" }]
```

A visual's `sort: {by, direction}` writes the visual's own sort (probe 31). `by` must be a field
the visual binds, because Desktop ignores any other. A spec with no `sort` leaves Desktop's sort,
or the one a user set, alone. `labels` and `legend` options are available on `column`, `bar` and
`line`.

`column`, `bar` and `line` also take a **Legend column** (`legend: "Sales[Region]"`, one column,
beside a drill-down if you like). Desktop refuses it together with several measures or a second
Legend column, so Blueprint does too (probe 32). `legend: off` hides the legend, and the
positions (`top`, `bottom`, `left`, `right`) show it: one option, one state. A table takes
`totals: "off"` to remove its Total row (`"on"` is Desktop's default):

```yaml
page: Sales Split
layout: two-up

visuals:
  - type: column
    title: Sales by country, by region
    options: { legend: bottom }
    slots: { category: "Sales[Country]", value: "[Total Sales]", legend: "Sales[Region]" }

  - type: table
    title: Orders
    options: { totals: "off" }
    slots: { columns: ["Sales[Country]", "Sales[Region]", "[Total Sales]"] }
```

### Visual types, and your own

The core ships every type a Desktop probe has verified: `header`, `card`, `multi-row-card`,
`kpi`, `column`, `bar`, `line`, `area`, `scatter`, `table`, `matrix`, `slicer`, `pie`, `donut`,
`map`, `stacked-column`, `stacked-column-100` and `stacked-bar`.

> **`map` needs turning on.** Power BI Desktop disables map visuals by default (File > Options
> and settings > Options > Global > Security). Where that is off, Desktop shows a message in
> place of the visual, whoever wrote the file. A spec naming anything else is refused, listing the types
that are loaded.

**Your own types.** A contract is a YAML file, so you can add types Blueprint doesn't ship —
per run, or for good in your guidelines:

```bash
bp apply spec.yaml --report <report> --visuals ./my-visuals
```

```yaml
# guidelines.yaml — relative to this file, like layouts.search_path
extensions:
  custom_visuals:
    search_path: ["my-visuals"]
```

`--visuals` is for trying a type in one run. A report that **keeps** visuals of your own type
should opt in through its guidelines (or its own `.blueprint.yaml`), because the manifest is
built from the contracts: a later `bp fmt` or `bp manifest` without the opt-in rewrites those
entries with the PBIR type and raw query roles instead of the spec type and slot names.

Every core type takes its own options, e.g.:

```yaml
  - type: slicer
    region: kpi-row
    options: { style: dropdown }   # the slicer as a dropdown (probes 20, 22)
    slots: { field: "Sales[Country]" }
```

### Which page a spec builds

`bp apply` marks the page it creates with the spec's **id** (the file name, or an explicit
top-level `id:`), and finds it again by that id:

- **Rename `page:` in the spec** and re-apply: the existing page is renamed and keeps its visuals.
  No second page is created.
- **Another spec uses the same page name:** `apply` refuses and names the spec that owns the page.
  If it's the same spec under a new file name, set `id:` to the old one. To hand the page over on
  purpose, pass `--take-over`.
- Pages built before spec ids existed are adopted on the next apply, without moving anything.

### Changing a spec and re-applying

Re-running `bp apply` with an edited spec updates the visuals it built, in place:

- **Fields:** change a slot (`value: "[Total Units]"` → `["[Total Units]", "[Sales $]"]`) and the
  visual is rebound. Its title, formatting and position stay; the plan says
  `rebind Category [Country]; Y [Total Amount] -> …`. Sorts and Desktop's automatic filters on
  fields that are gone are cleared; filters someone set by hand are kept.
- **Options** the spec sets are set; ones it leaves out are left to Desktop.
- **Layout and titles** follow the spec, as before.
- **Edited in Desktop?** If someone changed a Blueprint visual's fields in Desktop since Blueprint
  wrote them, `apply` refuses rather than undo their work, and says what's bound now. Put the
  change in the spec, or pass `--overwrite-edits`.
- **Type changes** (a `column` that becomes a `bar`) are refused: delete the visual in Desktop and
  re-apply. Visuals dropped from the spec are kept, with a warning.

### Typed slots

Each visual type declares the slots it accepts and what each slot takes — a dimension
column, a measure, or an ordered list for drill-down. A hierarchy built in the model is written
like a column (`category: "Sales[Geography]"`) and binds all its levels, as dragging it in
Desktop does. Column, bar, pie and line chart categories and the table's columns take one. Blueprint validates bindings
*before* writing anything, so a measure in a category slot is an error from `bp`, not a
confusing result in Desktop.

```yaml
# blueprint/visuals/archive/pie.yaml  (slot contract, not the template; probes 08 and 11)
type: pie
visual_type: pieChart
region: main
slots:
  category: { role: Category, accepts: column, required: true, ordered: true }   # "Legend"; a list drills down
  value:    { role: Y, accepts: measure, required: true }
  details:  { role: Series, accepts: column }                                  # "Details"
```

Each contract cites the probe that verified its PBIR shape. A type with no probe behind it doesn't
ship (see [How the PBIP format is learned](#how-the-pbip-format-is-learned)).

### Layouts

A layout maps an ordered list of visuals to positions. Layouts are data:

```yaml
# guidelines/layouts/standard-4-up.yaml
name: standard-4-up
canvas: { width: 1280, height: 720 }
regions:
  - { role: header,  x: 16,  y: 16,  w: 1248, h: 64 }
  - { role: kpi-row, x: 16,  y: 96,  w: 1248, h: 160 }
  - { role: main,    x: 16,  y: 272, w: 616,  h: 432 }
  - { role: main,    x: 648, y: 272, w: 616,  h: 432 }
```

Visuals fill regions in declaration order. Each visual takes the next free region of its
type's role (`region:` in its slot contract: `kpi` → `kpi-row`, `header` → `header`, everything
else → `main`), or of the role its spec names:

```yaml
  - type: card
    region: kpi-row          # a card in the KPI row instead of a main region
    slots: { value: "[Total Sales]" }
```

Running out of regions is an error, not a reflow. Shipped with the example guidelines
(`guidelines/layouts/`), all 1280×720, on the 8px grid, inside the 16px margin and at least the
16px gutter apart:

| Layout | Regions |
|---|---|
| `standard-4-up` | header, 1 KPI row, 2 main |
| `dashboard-6` | header, 3 KPI row, 3 main |
| `kpi-row-plus-detail` | header, 4 KPI row, 1 full-width main |
| `grid-2x3` | header, 6 main (2 rows of 3) |
| `two-up` | header, 2 full-height main |
| `one-up` | header, 1 full-width main |

A region no visual fills is left empty: a gap on the page. That's not a reflow either: `bp apply`
warns, naming the layouts on the search path that would place the same visuals with every region
filled (same canvas, within the guidelines), e.g. `layout 'standard-4-up' leaves kpi-row#1 empty,
a gap on the page; layout(s) that fit with no gap: two-up`.

`bp apply` refuses a layout that doesn't fit the guidelines it runs with: regions off the grid,
inside `spacing.margin`, or closer together than `spacing.gutter`.

---

## Guidelines and layering

The whole point of a guidelines file is that the rules outlive any one report and can
differ per team or per client, without forking the tool.

Resolution order, later overriding earlier:

```
1. built-in defaults          blueprint/defaults.yaml       (ships with the tool)
2. organisation guidelines    guidelines/<name>.yaml         (yours, usually private)
3. per-report overrides       <report>/.blueprint.yaml       (committed with the report)
4. command-line flags         --set spacing.grid=8
```

```yaml
# guidelines/example.yaml
version: 1
name: Example Corp Reporting Standard

canvas:
  width: 1280
  height: 720

spacing:
  grid: 8
  margin: 16
  gutter: 16      # minimum gap between neighbouring visuals

palette:
  categorical: ["#4E79A7", "#F28E2B", "#E15759", "#76B7B2", "#59A14F"]
  background: "#FFFFFF"
  text: "#333333"
  enforce: strict        # strict | warn | off

typography:
  page_title:   { font: Segoe UI Semibold, size: 20 }  # bp apply writes this onto header textboxes
  visual_title: { font: Segoe UI Semibold, size: 18 }  # weight is part of the face name
  body:         { font: Segoe UI, size: 12 }           # textboxes

page:
  require_title: true      # pages built from a spec need a `type: header` visual...
  title_region: header     # ...placed in a header region (hand-built pages aren't checked)
  max_visuals: 6
  density_policy: data     # named policy implemented in code, not an if-statement here

layouts:
  search_path: ["layouts"]     # relative to this file
  default: standard-4-up
```

### Core keys and extensions

The core file is small on purpose: `version`, `name`, `canvas` (width and height), `spacing`
(`grid`, `margin`, `gutter`), `page`, `palette`, `typography` (`page_title`, `visual_title`,
`body`) and `layouts`. Rule severities are fixed in code. Everything else is opt-in under
`extensions:`:

```yaml
extensions:
  severity: { grid: warning }          # override a rule's severity: error | warning | off
  decorative_types: [image, shape]     # may contain visuals; exempt from margin and gutter
  max_resize: 0.25                     # bp fmt skips a visual it would resize by more
  typography:                          # further text roles, checked like the core ones
    subtitle:   { font: Segoe UI, size: 12 }
    callout:    { font: Segoe UI Light, size: 32 }
    card_label: { font: Segoe UI, size: 12 }
  custom_visuals:
    search_path: ["../blueprint/visuals/archive"]   # see "Core types, and the archive"
```

**Upgrading from v0.5.x.** The old keys are refused, never ignored, and the error names the
replacement: `grid.size` is `spacing.grid`; `canvas.margin` and `canvas.gutter` are
`spacing.margin` and `spacing.gutter`; `grid.max_resize`, `check.severity` and
`check.decorative_types` moved under `extensions`; `grid.snap` is gone (`bp fmt` always snaps);
typography roles `header`, `title` and `textbox` are `page_title`, `visual_title` and `body`;
`subtitle`, `callout` and `card_label` moved to `extensions.typography`. The `bold` setting is
gone: a weight is part of the face name (`Segoe UI Semibold`). The one check this drops is a
textbox run's own `fontWeight`.

### Multi-tenant notes

- The tool is generic; **guideline files are the tenant-specific part.** Keep yours out of
  the public repo. `guidelines/example.yaml` exists so strangers can run the tool, and is
  entirely invented.
- `guidelines/` is gitignored except for `example.yaml` and `layouts/`.
- Select a tenant with `--guidelines <path>` or `BLUEPRINT_GUIDELINES=<path>`.
- Never put conditional logic in a guidelines file. When a rule needs branching, implement
  it in Python as a *named policy* and let the config select it (`density_policy: strict`).
  Config files that grow `if` statements become bad programming languages.

---

## The manifest

`.blueprint.manifest.json` (in the `.Report` folder, next to `.blueprint.yaml`) is the handoff
artifact between the layout half of the stack and the semantic-model half. Without it, an agent
has to re-derive the report structure by reading PBIR on every turn. `bp apply` rewrites it after
every change, and `bp manifest` rebuilds it from the report at any time.

```json
{
  "blueprint_version": "0.7.0",
  "guidelines": { "name": "Example Corp Reporting Standard", "version": 1 },
  "pbir_schema": { "page": ["2.1.0"], "visualContainer": ["2.13.0"] },
  "generated_at": "2026-11-09T04:00:00Z",
  "pages": [
    {
      "id": "b1df9ce53010a81607ce",
      "name": "Sales Overview",
      "spec_page": "Sales Overview",
      "layout": "two-up",
      "built_with": "Example Corp Reporting Standard@1",
      "size": { "w": 1280, "h": 720 },
      "visuals": [
        {
          "id": "b4f94ad3cfcc67642873",
          "type": "column",
          "visual_type": "clusteredColumnChart",
          "title": "Sales by Geography",
          "managed": true,
          "spec_id": "column-1",
          "region": "main#2",
          "position": { "x": 648, "y": 96, "w": 616, "h": 608 },
          "slots": {
            "category": ["Sales[Country]", "Sales[Region]"],
            "value": "[Total Amount]"
          }
        }
      ]
    }
  ]
}
```

- **Every page and visual is listed**, hand-built ones too. Those have `"managed": false`, their PBIR
  `visualType` as `type`, and query roles (`Category`, `Y`, …) as slot names. Visuals Blueprint
  created have their spec type, spec id, slot names and layout region (`<role>#<n>`).
- `layout`, `region` and `built_with` come from annotations `bp apply` leaves on the page and
  visuals. That's what makes the manifest rebuildable from the report alone, and it's how
  `bp check` can say which guidelines a page was built against.
- **It's deterministic.** `generated_at` changes only when something else does, so
  regenerating an unchanged report is a no-op. Set `SOURCE_DATE_EPOCH` for reproducible
  timestamps.
- `bp check` notes when the manifest is out of date (e.g. after a drag in Desktop).

It is **generated, never hand-edited**.

---

## Project structure

```
blueprint/
├── README.md
├── CHANGELOG.md
├── pyproject.toml
├── action.yml                  # composite GitHub Action: bp check over reports
├── blueprint/
│   ├── __init__.py
│   ├── cli.py                  # argparse entry points; one module per command in commands/
│   ├── defaults.yaml           # built-in guideline defaults (layer 1)
│   │
│   ├── commands/               # inspect, check, fmt, apply, describe, manifest, theme
│   │
│   ├── pbir/                   # everything that knows the on-disk format
│   │   ├── reader.py           # report dir -> in-memory model
│   │   ├── writer.py           # in-memory model -> report dir (atomic)
│   │   ├── jsonfmt.py          # the only JSON reader/writer: Desktop's bytes, exactly
│   │   ├── schemas.py          # validation against the vendored Microsoft schemas
│   │   ├── schemas/            # the vendored schemas (scripts/vendor_schemas.py)
│   │   ├── render.py           # minimal PBIR documents for new pages and visuals
│   │   ├── registry.py         # the only code that changes pages.json pageOrder
│   │   ├── ids.py              # deterministic ids in the format Desktop uses
│   │   ├── semantic.py         # read-only TMDL model: tables, columns, measures, hierarchies
│   │   ├── formatting.py       # colours and fonts found by shape
│   │   ├── theme.py            # the guidelines theme file
│   │   └── schema.md           # verified format facts, each with its evidence
│   │
│   ├── model.py                # Report / Page / Visual dataclasses
│   ├── spec.py                 # page spec parsing + validation
│   ├── guidelines.py           # layered config resolution; retired keys refused by name
│   ├── layouts.py              # named layout -> regions
│   ├── slots.py                # visual contracts (blueprint/visuals/*.yaml), inherits:
│   ├── grid.py                 # the one definition of "on grid"
│   ├── plan.py                 # planned file writes and warnings (--dry-run)
│   ├── validate.py             # guideline rules (used by `check`)
│   ├── policies.py             # named policies the config selects (e.g. density)
│   ├── manifest.py
│   └── visuals/                # one slot contract per visual type
│
├── guidelines/
│   ├── example.yaml            # invented; committed so the tool is runnable
│   ├── layouts/
│   └── .gitignore              # ignore everything except example.yaml + layouts/
│
├── examples/                   # runnable specs, and demo/ (the end-to-end demo's pages)
│
├── fixtures/                   # synthetic PBIP reports, built from scratch
│   ├── 01-blank-report/
│   ├── 02-card-and-chart/
│   └── README.md               # how each was made, so they can be rebuilt
│
├── docs/probes/                # raw Desktop diffs: the evidence behind schema.md
├── scripts/                    # probe builders (probe_*.py), demo.sh, desktop.sh, ci_check.sh
├── template/                   # the client-first design notes and plan for v0.6
│
└── tests/                      # includes golden/, pinned-layouts/, pinned-specs/ and
                                # test_probe_replay.py (every probe replayed against Blueprint)
```

**`pbir/` is the only package that knows the file format.** Everything above it works on
the in-memory model. When Microsoft changes PBIR, the blast radius is one directory.

---

## How the PBIP format is learned

Blueprint doesn't write PBIR from memory. Guessing at the format would produce a tool that
silently writes invalid files, so every format fact is established in Power BI Desktop first,
and the code relies only on facts recorded as verified. The method is a **probe**:

1. **Predict.** Write down what Desktop should produce before looking.
2. **Build a candidate.** A `scripts/probe_*.py` script writes the change into a copy of a
   fixture (or has Desktop make it), in a git repository on the Windows drive.
3. **Let Desktop judge.** Open it, check that it draws, press Ctrl+S, then `git diff`. What Desktop
   changes on save, and what it leaves alone, is the evidence.
4. **Record it.** The diff goes under `docs/probes/` (`python scripts/probe_evidence.py`), the
   fact goes into `blueprint/pbir/schema.md` marked verified, with the probe it came from, and
   the probe is added to `tests/test_probe_replay.py`, which rebuilds it from the evidence and
   tests Blueprint against Desktop's real output on every run.
5. **Only then ship it.** A visual contract, option or spec key cites its probe. Open items in
   `schema.md` are not used by the code.

Probes 01 to 31 cover pages and the registry, annotations, formatting and themes, fonts, every
shipped visual type and its bindings, drill-downs, hierarchies, chart options, aggregations and
formats, and sorts.

### The first questions

The first probes answered these, in this order. They are all answered; `schema.md` and the code
refer to them by number (`README Q4`).

| # | Question | Answer lives in |
|---|---|---|
| 1 | What does a report directory contain at rest? | `schema.md`, “Report folder” |
| 2 | What files appear when you add one blank page? | `schema.md`, “Creating pages and visuals” |
| 3 | Which existing file gets modified? (`pages.json`: creating the folder alone leaves the page invisible) | `schema.md`, “Pages” |
| 4 | What is the ID format, and is it validated? (20 hex characters; Blueprint's derived ids are accepted and kept) | `schema.md`, “Names and IDs”; `pbir/ids.py` |
| 5 | Is page order a registry or implied by folder names? (`pageOrder` in `pages.json`) | `schema.md`, “Pages” |
| 6 | What files appear when you add one card? | `schema.md`, “Visuals” |
| 7 | Where does a visual's position and size live? | `schema.md`, “Visuals” |
| 8 | Where does the visual title live? | `schema.md`, “Visuals” |
| 9 | What does a field binding look like? | `schema.md`, “Visuals” |
| 10 | What do the field wells look like per visual type? | `blueprint/visuals/*.yaml`, each citing its probe |
| 11 | How is a drill-down path represented? (an ordered list of projections in one role) | `schema.md`, “Visuals” |
| 12 | Is there a schema version string anywhere? (`$schema` on every document) | `schema.md`, “Schema versions” |
| 13 | Does Desktop reformat JSON on save? (not unchanged files; what it writes has one fixed style, which `jsonfmt` reproduces byte for byte) | `schema.md`, “File encoding”; `pbir/jsonfmt.py` |
| 14 | Can custom metadata survive a round trip? (yes, in `annotations`) | `schema.md`, “What Desktop changes on its own” (probe 01) |

`schema.md` is a living document. Each entry says what is verified and how:

```markdown
## Pages

**Verified 2026-11-09, PBIR schema <x>, Desktop <version>.**

- A page lives at `definition/pages/<page-id>/page.json`.
- Pages are registered in `definition/pages/pages.json`, which holds an ordered
  `pageOrder` array and `activePageName`.
- Creating the folder without updating `pages.json` leaves the page invisible.

_Evidence: `git diff` after adding one blank page — see `docs/probes/02-add-page.diff`._
```

When a Desktop update changes the format, the replays fail and the raw diffs show what moved.

---

## Fixtures and testing

Fixtures are **synthetic PBIP reports built from scratch**, committed to the repo. They
exist so that:

1. You can develop the entire tool at home, with no work files involved — ever.
2. Anyone who clones the repo can actually run it, which is what makes this a project
   rather than a script.
3. Schema drift surfaces as a failing test rather than as a surprise in a demo.

| Fixture | Contents | Exercises |
|---|---|---|
| `01-blank-report` | one empty 1920×1080 page | reader, page creation, registry update |
| `02-card-and-chart` | a card bound to `[Total Amount]` and a column chart with a Country → Region drill-down, both off-grid | slots, bindings, `fmt`, idempotence, `check` |

Over-budget pages and `blueprint: ignore` are covered by tests that copy a fixture or build a
synthetic report (`tests/builders.py`), so no hand-edited fixtures are needed.

`fixtures/README.md` records how each one was produced, so they can be rebuilt against a
newer PBIR schema.

**Golden-file tests.** For each fixture, `tests/test_apply_golden.py` runs a spec and
compares the output tree byte-for-byte against a committed expected tree. When Microsoft
changes the format, these fail loudly and the diff tells you exactly what moved.

**The idempotence test is not optional.** `fmt` twice must equal `fmt` once. It is the
cheapest guard against a formatter that churns diffs forever.

---

## Version compatibility

Three things version independently, and the manifest records all three:

| Thing | Where it's declared | Why it matters |
|---|---|---|
| Blueprint | `blueprint.__version__` | behaviour changes between releases |
| Guidelines | `version:` in the guidelines file | the standard evolves; old reports were built to old rules |
| PBIR schema | read from the report | Microsoft changes the format |

Policy:

- Blueprint refuses to write to a report whose PBIR schema it does not recognise, unless
  `--force-schema` is passed. Silently writing to an unknown format is how reports get
  corrupted.
- `bp check` reports which guideline version a report was built against versus which one is
  being applied, so "this was compliant last quarter" is answerable.
- Guideline files are versioned and additive. Renaming a key is a major version bump.

---

## Roadmap

**v0.1 — read and align.** No generation at all.
`bp inspect` and `bp fmt` on existing reports: snap to grid, normalise sizes. Idempotence
test passing. This version de-risks everything else — if reading PBIR, changing a position,
writing it back and reloading in Desktop doesn't work cleanly, nothing above it matters.

**v0.2 — validate.** `bp check` against a guidelines file. Useful on its own: it can run
over reports nobody generated and tell a reviewer what's off-standard.

**v0.3 — generate.** `bp apply` creates pages and places visuals from a spec, for three or
four visual types. Manifest emitted. No field bindings yet.

**v0.4 — bind.** Typed slots, measures and columns, drill-down paths. This is where the
tool becomes genuinely end-to-end with the Modeling MCP.

**v0.5 — breadth.** Drill-downs and legends on line and area, more chart options (done).

**v0.6 — the template rewrite.** Client-first input files: a small core guidelines schema with
opt-in `extensions:`, a core of seven visual types, `inherits:` for visual contracts, per-field
`aggregate` and `format`, `labels`/`legend` on all three chart types, `sort`, a Legend column
on clustered charts, `legend: off` and table `totals` (done).

**v0.7 — the core-20% audit.** A guidelines key outside the core is refused instead of ignored,
`--set KEY=VALUE` replaces `--grid` on every command that reads guidelines, and per-type PBIR
facts live in the visual contracts rather than in core code (done).

**Next, each needing a Desktop probe first:** axis titles, conditional formatting; and the visual
types real reports use that no contract covers (`map`, `scatter`, `multiRowCard`).

**Later, in no particular order.** Bookmarks. Relative layout positioning. Promoting archived
visual types into the core. A `bp new` scaffold. Theme file generation (done: `bp theme`). CI
action for `bp check` (done: [In CI](#in-ci)).

**Deliberately unscheduled:** an interactive wizard. The declarative spec is the primary
interface; a prompt-driven shell on top is a convenience, and conveniences come after the
thing works.

---

## Non-goals

- **No semantic model work.** That is the Modeling MCP's job.
- **No LLM in the generation path.** The tool must be deterministic and free to run.
- **No automatic content relocation.** Warn, exit non-zero, let a human decide.
- **No conditionals in config.** Named policies in code, selected by config.
- **No premature abstraction.** `create_page()` and `create_visual()` stay as separate
  concrete functions until the duplication is real and understood.
- **Not a Power BI replacement.** Desktop remains the place you look at the result.

---

## Using this with client work

This repository is generic tooling. It contains no organisation's guidelines, no client
data, no report files from any engagement, and it never should.

If you use Blueprint in a workplace:

- **Keep the guideline file internal.** It is configuration, which is exactly why it can
  live somewhere else. `guidelines/example.yaml` here is invented.
- **Never commit real report files, measure names, table names or data** — fixtures are
  built from scratch for this reason.
- **Go through your organisation's approval process** for both cloning the repo onto a work
  machine and running it against real reports. Even code you wrote yourself is third-party
  software once it is on a public host.
- **Don't carry files in either direction** outside those processes.
- **Check your employment agreement before publishing.** IP assignment clauses are often
  broad enough to cover work related to the employer's business regardless of whose machine
  it was written on. Ask, and get the answer in writing, before rather than after.

---

## License

MIT. See [LICENSE](LICENSE).
