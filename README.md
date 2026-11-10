# Blueprint

[![test](https://github.com/gurdasss/blueprint/actions/workflows/test.yml/badge.svg?branch=main)](https://github.com/gurdasss/blueprint/actions/workflows/test.yml)

**Declarative, deterministic Power BI report layouts.** Write a short YAML file, get a
PBIP report whose pages are built and aligned to your organisation's design guidelines —
no dragging, no nudging, no eyeballing.

```bash
bp apply pages/sales-overview.yaml --report ./SalesReport.Report
```

> **Status: pre-alpha.** Nothing here is stable. The PBIR schema sections below are
> deliberately marked as unverified — see [Learning the PBIP format](#learning-the-pbip-format).
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
- [Learning the PBIP format](#learning-the-pbip-format)
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
git clone https://github.com/<you>/blueprint.git
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
      - uses: gurdasss/blueprint@main          # pin a commit SHA for repeatable checks
        with:
          reports: |                           # one per line: .Report folder, .pbip, or its folder
            reports/Sales.Report
            reports/Operations.pbip
          guidelines: guidelines/corp.yaml     # optional; else $BLUEPRINT_GUIDELINES, else defaults
          strict: false                        # true fails on warnings too
```

The job fails if any report has errors (exit 1) or can't be read (exit 2). Each report's text
output goes to the job summary, and the `exit-code` output holds the worst exit code.
A report's own `.blueprint.yaml` still applies, as it does locally.

---

## Page specs

A page spec is the input a human — or an AI agent — writes. It describes *intent*, not
geometry.

```yaml
# examples/sales-overview.yaml
# id: sales-overview    (optional; defaults to the file name. See "Which page a spec builds" below.)
page: Sales Overview
layout: standard-4-up

visuals:
  - type: header
    title: Sales Overview

  - type: kpi-row
    slots:
      values:
        - "[Total Sales]"
        - "[Gross Margin %]"
        - "[Orders]"

  - type: pie
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
  - type: slicer
    region: kpi-row
    options: { style: dropdown }   # the slicer as a dropdown (probes 20, 22)
    slots: { field: "Sales[Country]" }

  - type: stacked-bar
    options: { labels: on, legend: right }   # data labels on, legend on the right (probe 23)
    slots: { category: "Sales[Country]", value: ["[Total Amount]", "[Target Amount]"] }
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
# blueprint/visuals/pie.yaml  (slot contract, not the template; verified in probes 08 and 11)
type: pie
visual_type: pieChart
region: main
slots:
  category: { role: Category, accepts: column, required: true, ordered: true }   # "Legend"; a list drills down
  value:    { role: Y, accepts: measure, required: true }
  details:  { role: Series, accepts: column }                                  # "Details"
```

> **Draft.** The slot vocabulary per visual type has to be harvested from real PBIR files,
> one visual type at a time. See [Learning the PBIP format](#learning-the-pbip-format).
> Expect this schema to change.

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

`bp apply` refuses a layout that doesn't fit the guidelines it runs with: regions off the grid,
inside `canvas.margin`, or closer together than `canvas.gutter`.

---

## Guidelines and layering

The whole point of a guidelines file is that the rules outlive any one report and can
differ per team or per client, without forking the tool.

Resolution order, later overriding earlier:

```
1. built-in defaults          blueprint/defaults.yaml       (ships with the tool)
2. organisation guidelines    guidelines/<name>.yaml         (yours, usually private)
3. per-report overrides       <report>/.blueprint.yaml       (committed with the report)
4. command-line flags         --grid 8
```

```yaml
# guidelines/example.yaml
version: 1
name: Example Corp Reporting Standard

grid:
  size: 8
  snap: true

canvas:
  width: 1280
  height: 720
  margin: 16
  gutter: 16

palette:
  categorical: ["#4E79A7", "#F28E2B", "#E15759", "#76B7B2", "#59A14F"]
  background: "#FFFFFF"
  text: "#333333"
  enforce: strict        # strict | warn | off

typography:
  title:    { font: Segoe UI Semibold, size: 18 }   # weight is part of the face name
  subtitle: { font: Segoe UI, size: 12 }
  header:   { font: Segoe UI Semibold, size: 20 }   # bp apply writes this onto header textboxes

page:
  require_title: true      # pages built from a spec need a `type: header` visual...
  title_region: header     # ...placed in a header region (hand-built pages aren't checked)
  max_visuals: 6
  density_policy: data     # named policy implemented in code, not an if-statement here

layouts:
  search_path: ["layouts"]     # relative to this file
  default: standard-4-up
```

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
  "blueprint_version": "0.0.1",
  "guidelines": { "name": "Example Corp Reporting Standard", "version": 1 },
  "pbir_schema": { "page": ["2.1.0"], "visualContainer": ["2.13.0"] },
  "generated_at": "2026-11-09T04:00:00Z",
  "pages": [
    {
      "id": "b1df9ce53010a81607ce",
      "name": "Sales Overview",
      "spec_page": "Sales Overview",
      "layout": "standard-4-up",
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
          "position": { "x": 648, "y": 272, "w": 616, "h": 432 },
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
├── pyproject.toml
├── blueprint/
│   ├── __init__.py
│   ├── cli.py                  # argparse entry points: inspect/check/fmt/apply/manifest
│   ├── defaults.yaml           # built-in guideline defaults (layer 1)
│   │
│   ├── pbir/                   # everything that knows the on-disk format
│   │   ├── __init__.py
│   │   ├── reader.py           # report dir -> in-memory model
│   │   ├── writer.py           # in-memory model -> report dir (atomic)
│   │   ├── registry.py         # the page/visual registry files (see note below)
│   │   ├── ids.py              # id generation, matching the format Desktop uses
│   │   └── schema.md           # NOTES on the real format. Filled by the diff study.
│   │
│   ├── model.py                # Report / Page / Visual / Slot dataclasses
│   ├── spec.py                 # page spec parsing + validation
│   ├── guidelines.py           # layered config resolution
│   ├── layouts.py              # named layout -> regions
│   ├── slots.py                # slot contracts per visual type
│   ├── render.py               # template + params -> files
│   ├── validate.py             # guideline checks (used by `check` and after `apply`)
│   ├── policies.py             # named policies the config selects (e.g. density)
│   └── manifest.py
│
├── templates/                  # harvested, parameterised PBIR fragments
│   ├── page/
│   └── visuals/
│       ├── card/
│       ├── pie/
│       ├── column/
│       └── table/
│
├── guidelines/
│   ├── example.yaml            # invented; committed so the tool is runnable
│   ├── layouts/
│   └── .gitignore              # ignore everything except example.yaml + layouts/
│
├── examples/
│   └── sales-overview.yaml
│
├── fixtures/                   # synthetic PBIP reports, built from scratch
│   ├── 01-blank-report/
│   ├── 02-card-and-chart/
│   └── README.md               # how each was made, so they can be rebuilt
│
└── tests/
    ├── test_reader.py
    ├── test_idempotence.py     # fmt twice == fmt once
    ├── test_validate.py
    ├── test_apply_golden.py    # golden-file comparison per fixture
    └── test_spec_errors.py
```

**`pbir/` is the only package that knows the file format.** Everything above it works on
the in-memory model. When Microsoft changes PBIR, the blast radius is one directory.

---

## Learning the PBIP format

**This section is the actual first task, and it is research, not coding.** The PBIP/PBIR
schema below is *not* documented here from memory, because guessing at it would produce a
tool that silently writes invalid files. Establish it empirically and record what you find
in `blueprint/pbir/schema.md`.

### Protocol

For each question, run the experiment and write down the answer *before* writing code.
Predict the result first — a prediction you record and then check is worth more than one
you form afterwards.

```bash
# Set up a sandbox
cp -r <a report> /tmp/probe && cd /tmp/probe
git init && git add -A && git commit -m "baseline"
```

Then, one change at a time in Power BI Desktop → save → `git status && git diff`.

### Questions to answer

| # | Question | Experiment |
|---|---|---|
| 1 | What does a report directory contain at rest? | `tree` a freshly saved PBIP |
| 2 | What files appear when you add **one blank page**? | add page, save, diff |
| 3 | **Which existing file gets modified?** | same diff — look for a file listing pages and their order |
| 4 | What is the ID format, and is it validated? | read the real IDs; do not assume `uuid4` is acceptable |
| 5 | Is page order stored in a registry or implied by folder names? | reorder pages in Desktop, save, diff |
| 6 | What files appear when you add **one card**? | add card, save, diff |
| 7 | Where does a visual's position and size live? | move and resize it, save, diff |
| 8 | Where does the visual title live? | set a title, save, diff |
| 9 | What does a **field binding** look like? | bind one measure, save, diff |
| 10 | What do the field wells look like for pie / column / table? | one visual type at a time |
| 11 | How is a drill-down path represented? | add three levels to a category slot, save, diff |
| 12 | Is there a schema version string anywhere? | grep the report for `schema`/`version` |
| 13 | Does Desktop reformat or reorder JSON on save? | save twice without changes, diff |
| 14 | Can arbitrary custom metadata survive a round trip? | add a key by hand, open and save in Desktop, diff |

Question 3 is the one that will cost you an evening if you skip it: creating a page folder
is almost certainly not enough to make the page appear.

Question 13 matters for golden-file tests: if Desktop normalises JSON differently from
your writer, every save will churn the diff.

Question 14 decides whether tagging-in-Desktop is viable at all. If custom keys are
stripped, the CLI-first approach in this README is the only workable one — which is why it
is the design here.

### Recording findings

`blueprint/pbir/schema.md` is a living document. Suggested shape per entry:

```markdown
## Pages

**Verified 2026-11-09, PBIR schema <x>, Desktop <version>.**

- A page lives at `definition/pages/<page-id>/page.json`.
- Pages are registered in `definition/pages/pages.json`, which holds an ordered
  `pageOrder` array and `activePageName`.
- Creating the folder without updating `pages.json` leaves the page invisible.

_Evidence: `git diff` after adding one blank page — see `docs/probes/02-add-page.diff`._
```

Commit the raw diffs under `docs/probes/`. They are your evidence, and they are how you
tell what changed when a Desktop update breaks something.

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

**Later, in no particular order.** Conditional formatting. Bookmarks. More visual types.
Theme file generation (done: `bp theme`). A `bp new` scaffold. CI action for `bp check`
(done: [In CI](#in-ci)).

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
