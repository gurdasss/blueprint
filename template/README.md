# Start here

This folder is what a client copies and fills in. Blueprint takes three
files from you — **guidelines**, one or more **layouts**, and a **page
spec** per page — and writes Power BI PBIR pages from them.

| File | What it is | What to do with it |
|---|---|---|
| `guidelines.template.yaml` | Your house standard: canvas, grid, margin, gutter, palette, fonts, page rules. One per organisation. | **Copy it.** Save as anything, e.g. `my-guidelines.yaml`. |
| `layout.template.yaml` | One named arrangement of regions on the canvas. | **Copy it** to `layouts/<name>.yaml` — see the warning below. |
| `page.template.yaml` | One page: which visuals, and what data goes in them. One per page. | **Copy it** per page, e.g. `overview.yaml`. |
| `interactions.md` | How those three files constrain each other, and what `bp apply` does in what order. | **Read it** when something is refused and you want to know which file owns the number. |
| `visuals.md` | How a visual type is defined, and how to write one of your own. | **Read it** only if you need a type Blueprint doesn't ship. |
| `extensions.md` | Where settings outside the core would go. | **Skip it.** Parked on purpose — most of what it sketches isn't built. |
| `plan.md` | Internal history: how the template rewrite was planned and what was dropped. | **Skip it.** Not documentation. |

---

## Two things that will bite you

**1. A layout file's name must match its `name:` key.** This file is called
`layout.template.yaml` but says `name: standard-dashboard`, so copying it as
is gives you:

```
layout 'standard-dashboard' not found in <your layouts dir>
```

Save it as `layouts/standard-dashboard.yaml` — or rename the `name:` key to
match whatever you call the file. Also note `layouts.search_path` in the
guidelines resolves **relative to the guidelines file**, not to your shell's
current directory, so this is the layout that works:

```
my-guidelines.yaml          layouts: {search_path: ["layouts"]}
layouts/
  standard-dashboard.yaml   name: standard-dashboard
overview.yaml               layout: standard-dashboard
```

**2. Every field name in `page.template.yaml` is invented.**
`[Total Revenue]`, `Geography[Region]` and the rest are there to show the
syntax. They are not in your model, so applying the template unedited gives
you one error per field. Run `bp describe --report <your report>` first and
use what it lists.

---

## A first run that needs no editing

Nothing here touches your own report. Copy a fixture, build a page in it,
then look at what happened.

```bash
cp -r fixtures/02-card-and-chart /tmp/my-report

# What can a spec use? Types, slots, options, layouts, and your model's fields.
bp describe --report /tmp/my-report --guidelines guidelines/example.yaml

# What would be written, without writing it
bp apply examples/sales-overview.yaml --report /tmp/my-report \
    --guidelines guidelines/example.yaml --dry-run

# Write it
bp apply examples/sales-overview.yaml --report /tmp/my-report \
    --guidelines guidelines/example.yaml
```

That creates a page `Sales Overview` with a header, a card and a column
chart, on the `two-up` layout. Open `/tmp/my-report` in Power BI Desktop to
see it.

Then:

```bash
bp check --report /tmp/my-report --guidelines guidelines/example.yaml
```

**This exits 1, and that is the right answer.** It reports 5 errors and 2
warnings — none of them about the page you just built. They are the
fixture's own hand-built `Overview` page (off the grid, 1920×1080 against a
1280×720 standard) and its stock Power BI theme (whose colours and fonts
aren't the example palette). That is what `check` is for: it reads the whole
report, not only Blueprint's part of it. `bp fmt` fixes the grid findings
and `bp theme` the theme ones.

---

## Your own report

```bash
# 0. Work on a copy until you trust it.
cp -r <your-pbip> /tmp/trial

# 1. Copy the three templates.
cp template/guidelines.template.yaml  my-guidelines.yaml
mkdir -p layouts
cp template/layout.template.yaml      layouts/standard-dashboard.yaml
cp template/page.template.yaml        overview.yaml

# 2. Find out what you can actually write. Field names come from here.
bp describe --report /tmp/trial --guidelines my-guidelines.yaml

# 3. Edit the three files:
#    - my-guidelines.yaml: your canvas, palette and fonts
#    - layouts/standard-dashboard.yaml: regions, if the shipped ones don't fit
#    - overview.yaml: real field names, and a `layout:` that exists
#
# 4. See what it would do. Nothing is written, and every problem in every
#    spec is reported at once.
bp apply overview.yaml --report /tmp/trial --guidelines my-guidelines.yaml --dry-run

# 5. Do it. Re-running is safe: it updates the page it built before.
bp apply overview.yaml --report /tmp/trial --guidelines my-guidelines.yaml

# 6. Check the result against your guidelines.
bp check --report /tmp/trial --guidelines my-guidelines.yaml
```

`bp apply` takes several specs or a folder of them, pre-flights all of them,
and writes nothing if any one fails.

---

## Before you write a layout

You may not need to. `bp describe` lists every layout on your search path
with its region counts:

```
Layouts
  dashboard-6: 1280x720; 1 header, 3 kpi-row, 3 main
  grid-2x3: 1280x720; 1 header, 6 main
  kpi-row-plus-detail: 1280x720; 1 header, 4 kpi-row, 1 main
  one-up: 1280x720; 1 header, 1 main
  standard-4-up (default): 1280x720; 1 header, 1 kpi-row, 2 main
  two-up: 1280x720; 1 header, 2 main
```

Six ship with Blueprint, all 1280×720. Write your own when none has the
regions you need, or when your canvas is a different size — and read
`layout.template.yaml` first, which works out the arithmetic.

---

## What Blueprint will not do

Knowing these saves time arguing with it:

- **It never reflows.** Too many visuals for a layout's regions is an error,
  not a rearrangement. A region left empty is a gap, and it stays a gap.
- **It never moves content between pages.**
- **It never silently undoes a Desktop edit.** If you rebind a visual's
  fields in Desktop and the spec disagrees, `apply` refuses and tells you to
  pass `--overwrite-edits`.
- **It never touches a visual you placed by hand**, or one marked
  `blueprint: ignore`.
- **It doesn't delete.** A visual dropped from a spec is left on the page,
  with a warning.

---

## When something is refused

The errors name the file and the key. A few that come up first:

| Message | What to change |
|---|---|
| `layout '<name>' not found` | The layout file's name, or `layouts.search_path` in the guidelines. See snag 1 above. |
| `no measure [X] in the semantic model` | The field name in the spec. `bp describe` lists the real ones. |
| `two fields in Values would both be called 'X'` | Two entries in one slot whose display name is the same (e.g. a column and a measure both named `Amount`). Bind one of them. |
| `no free 'main' region left in layout` | Remove a visual, choose a layout with more regions, or set `region:` on one. |
| `layout <name> doesn't fit the guidelines` | The layout's region coordinates: off the grid, inside the margin, or closer than the gutter. |
| `'<type>' is not a supported visual type` | The type name. The error lists all of them; `visuals.md` covers adding your own. |
| `page '<name>' is built by spec '<id>'` | You renamed the spec file. Set `id:` back to the old name, as the error says. |
| `unknown key <k>. Known here: …` | A typo in the guidelines. The core refuses unknown keys rather than ignoring them, and names the closest real one. |
