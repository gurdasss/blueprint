# Start here

This folder is what a client copies and fills in. Blueprint takes three
files from you — **guidelines**, one or more **layouts**, and a **page
spec** per page — and writes Power BI PBIR pages from them.

| File | What it is | What to do with it |
|---|---|---|
| `guidelines.template.yaml` | Your house standard: canvas, grid, margin, gutter, palette, fonts, page rules. One per organisation. | **Copy it.** Save as anything, e.g. `my-guidelines.yaml`. |
| `layout.template.yaml` | One named arrangement of regions on the canvas. | **Copy it** to `layouts/<name>.yaml` — see the warning below. |
| `page.template.yaml` | One page: which visuals, and what data goes in them. One per page. | **Copy it** per page, e.g. `overview.yaml`. |

That's the whole folder: three files to copy, and this page. Reference
material lives in [`docs/`](../docs/) — you don't need it to get a page
built, and the two worth knowing about are:

- [`docs/interactions.md`](../docs/interactions.md) — how those three files
  constrain each other, and what `bp apply` does in what order. Read it when
  something is refused and you want to know which file owns the number.
- [`docs/visuals.md`](../docs/visuals.md) — the visual contract format, and
  how to add a type Blueprint doesn't ship.

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
then look at what happened. **Run these from the repository root**, since
the paths are relative to it.

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
chart, on the `two-up` layout. Open the `.pbip` in Power BI Desktop to see
it — and if you're running Blueprint under WSL, copy the folder somewhere
Windows can reach first (`/mnt/c/...`), because Desktop can't open a path
inside the WSL filesystem.

Then:

```bash
bp check --report /tmp/my-report --guidelines guidelines/example.yaml
```

**This exits 1, and that is the right answer.** It reports 5 errors and 2
warnings — none of them about the page you just built. They are the
fixture's own hand-built `Overview` page (off the grid, 1920×1080 against a
1280×720 standard) and its stock Power BI theme (whose colours and fonts
aren't the example palette). That is what `check` is for: it reads the whole
report, not only Blueprint's part of it.

Those errors are the two other commands' job, so fix them and look again:

```bash
bp theme --report /tmp/my-report --guidelines guidelines/example.yaml   # palette + fonts
bp fmt   --report /tmp/my-report --guidelines guidelines/example.yaml   # snap to the grid
bp check --report /tmp/my-report --guidelines guidelines/example.yaml
```

Now `check` exits 0, with two warnings left. Both are things neither
command will do for you: nothing resizes a page, so the fixture's
hand-built 1920×1080 page stays that size, and `fmt` only snaps edges to
the grid — so the visual that was 10.29px from the left edge is now at 8,
on the grid but still inside the 16px margin. Moving it out of the margin
would be a judgement about someone's layout, so `check` reports it and
leaves it to you.

---

## Your own report

Keep your files in a directory of your own — they're yours, not
Blueprint's, and nothing below writes into the Blueprint repo.

```bash
# 0. Somewhere of your own, and a copy of the report until you trust it.
mkdir -p ~/my-standard/layouts && cd ~/my-standard
cp -r <your-pbip> /tmp/trial

# 1. Copy the three templates (BP = where you cloned Blueprint).
cp $BP/template/guidelines.template.yaml  my-guidelines.yaml
cp $BP/template/layout.template.yaml      layouts/standard-dashboard.yaml
cp $BP/template/page.template.yaml        overview.yaml

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

You may not need to. Blueprint ships several, and `bp describe` lists every
layout on your search path with its region counts — two lines of it, as an
example of the shape:

```
Layouts
  grid-2x3: 1280x720; 1 header, 6 main
  standard-4-up (default): 1280x720; 1 header, 1 kpi-row, 2 main
```

Match the counts against the visuals your spec needs, by role. Write your
own when none of them has the regions you want, or when your canvas is a
different size — and read `layout.template.yaml` first, which works out the
arithmetic.

---

## What `bp apply` will not do

Knowing these saves time arguing with it:

- **It never reflows.** Too many visuals for a layout's regions is an error,
  not a rearrangement. A region left empty is a gap, and it stays a gap.
- **It never moves content between pages.**
- **It never touches a visual you placed by hand**, or one marked
  `blueprint: ignore`. (`bp fmt` is the exception: snapping to the grid is
  its whole job, so it snaps hand-placed visuals too. It still honours
  `blueprint: ignore`, and skips grouped visuals and pages with no fixed
  size, with a warning.)
- **It doesn't delete.** A visual dropped from a spec is left on the page,
  with a warning.

### What it *does* take back on a re-run

The spec owns these, so a re-apply restores them. It reports each change,
but it doesn't ask first:

- **Position and size.** The layout owns them. Nudge a Blueprint visual in
  Desktop and the next apply moves it back (`x 400 -> 16`).
- **The header's text and style**, unless you edited the textbox into more
  than the single run Blueprint wrote — then it warns and leaves it.
- **Any option or sort the spec sets.** One the spec *doesn't* mention is
  left to you.

The one thing it guards is **field bindings**. Each Blueprint visual carries
a fingerprint of what it last bound, so if you rebind fields in Desktop and
the spec disagrees, `apply` refuses and names `--overwrite-edits`. So: put
layout and bindings in the spec, and keep formatting Blueprint doesn't
manage in Desktop.

---

## When something is refused

The errors name the file and the key. A few that come up first:

| Message | What to change |
|---|---|
| `layout '<name>' not found` | The layout file's name, or `layouts.search_path` in the guidelines. See snag 1 above. |
| `no measure [X] in the semantic model` | The field name in the spec. `bp describe` lists the real ones. |
| `two fields in <role> would both be called 'X'` | Two entries in one slot end up with the same display name — e.g. the same column listed twice in a table's `columns`. Bind one of them. |
| `no free 'main' region left in layout` | Remove a visual, choose a layout with more regions, or set `region:` on one. |
| `layout '<name>' doesn't fit the guidelines` | The layout's region coordinates: off the grid, inside the margin, or closer than the gutter. |
| `'<type>' is not a supported visual type` | The type name. The error lists all of them; [`docs/visuals.md`](../docs/visuals.md) covers adding your own. |
| `page '<name>' is built by spec '<id>'` | You renamed the spec file. Set `id:` back to the old name, as the error says. |
| `unknown key <k>. Known here: …` | A typo in the guidelines. The core refuses unknown keys rather than ignoring them, and names the closest real one. |
