# Extension Points

> How the core 20% is designed so that extensions are additive —
> new keys, new files, new rules — never changes to core code.

---

## Principle

Every extension follows one pattern: **add, never modify.** The core
structure at every layer is a dict (or list of dicts). Extensions add
keys to those dicts. Core code validates what it knows and ignores
what it doesn't. An extension registers its own validator for its own
keys.

---

## Extension points by layer

### 1. Guidelines

The core guidelines file has a reserved top-level key:

```yaml
# extensions: is reserved. Core validator ignores it.
# Extensions read their own keys from this block.
extensions:
  conditional_formatting:
    rules: [...]
  custom_visuals:
    search_path: ["my-visuals"]
```

**How it works:**
- The core reads only the sub-keys listed below; it passes the rest through
- Each extension registers a validator that reads its own sub-key
- Extensions can also read core keys (e.g. palette) but never write them
- A guidelines file without `extensions:` is complete — nothing is missing

**Implemented today** (read by `blueprint/guidelines.py`, which is why these
five live here rather than in the core file — they are knobs, not contracts):

```yaml
extensions:
  severity: {grid: warning}         # override a rule's baked-in severity
  decorative_types: [image, shape]  # may contain visuals; exempt from margin/gutter
  max_resize: 0.25                  # bp fmt skips a bigger resize; null: no limit
  typography:                       # text roles beyond the core three
    subtitle:   {font: Segoe UI, size: 12}
    callout:    {font: Segoe UI Light, size: 32}   # a card's value (probe 07)
    card_label: {font: Segoe UI, size: 12}         # the new card's label (probe 15)
  custom_visuals:                     # visual types beyond the core
    search_path: ["my-visuals", "../blueprint/visuals/archive"]
```

**What further extensions add here:**
- Four-sided margins (`spacing.margin: { top: 16, bottom: 16, ... }`)
- Two-axis gutters (`spacing.gutter: { horizontal: 16, vertical: 24 }`)
- Canvas background colour
- Approved visual type / layout allowlists
- Visual container styling (border, shadow, corner radius)
- Further typography roles (kpi_value, data_label)

### 2. Visual definitions

**Implemented.** The core loads the seven contracts in `blueprint/visuals/`
automatically — `header`, `card`, `kpi`, `column`, `line`, `bar`, `table`.
Extensions add more by declaring a directory, which is also how the eight
archived contracts (`blueprint/visuals/archive/`: `pie`, `donut`, `slicer`,
`matrix`, `area` and the stacked charts) come back:

```yaml
# in guidelines.yaml
extensions:
  custom_visuals:
    search_path: ["my-visuals"]
```

**How it works:**
- The loader always reads the core `blueprint/visuals/`, then each
  declared directory in order
- A type defined twice is **refused**, naming both files, and so is a
  second contract claiming one PBIR `visual_type`: a shadowed contract
  would change what a spec means depending on the search path order
- `inherits:` works across directories — a custom visual can extend a
  core one (but not the reverse: the core must load on its own)

**What extensions add here:**
- New visual types (waterfall, gauge, treemap, etc.)
- Modified built-ins (different default region, extra options)

### 3. Page spec — slot long form

The short/long form slot pattern is the main extension seam in
page specs. The long form is a dict, and extensions add keys:

```yaml
# Core (today):
slots:
  value:
    field: "[Total Revenue]"
    format: currency

# With extensions (future):
slots:
  value:
    field: "[Total Revenue]"
    format: currency
    sort: descending               # ← extension key
    conditional_format: red_green  # ← extension key
    display_units: thousands       # ← extension key
    decimal_places: 1              # ← extension key
```

**How it works:**
- Core validates `field` and `format` — the keys it owns
- Unknown keys in the long form are passed through, not rejected
- Each extension registers a validator for its own keys
- The short form (`value: "[Revenue]"`) still works — extensions
  only activate when the long form is used

**What extensions add here:**
- Sort order per slot
- Conditional formatting
- Display units and decimal places
- Custom aggregation beyond the pipe syntax

### 4. Page spec — visual options

Options are declared in the visual YAML. The engine writes whatever
options it finds. An extension adds options by adding lines to the
visual definition:

```yaml
# visuals/column.yaml (with extension options)
type: column
visual_type: clusteredColumnChart
region: main
slots: ...
options:
  labels: { object: labels, property: show, values: { "on": "true" } }
  legend: { object: legend, property: position, values: { ... } }
  # Extension options — same format, same engine path:
  sort: { object: sort, property: orderBy, values: { ... } }
  tooltip: { object: tooltip, property: show, values: { "on": "true" } }
```

**How it works:**
- The engine already writes any option declared in the visual YAML
- Adding an option = adding a line to the YAML
- No engine code change — the render path is generic
- The page spec references it: `options: { sort: "descending" }`

**What extensions add here:**
- Sort controls
- Tooltip configuration
- Drill-through page settings
- Reference lines
- Any Power BI visual property that maps to objects/properties

### 5. Layout regions — and relative positioning later

A layout region is a dict, so extensions add keys to it:

```yaml
# Core (today): the client states every pixel
regions:
  - { role: main, x: 16, y: 272, w: 616, h: 432 }

# With extensions:
  - { role: main, x: 16, y: 272, w: 616, h: 432,
      min_height: 200,        # ← extension: a floor Desktop needs
      background: "#FFFFFF" } # ← extension: container styling
```

**Relative positioning is the big one, and it is deliberately not core.**
A later version can accept a structural form where the client states
shape and Blueprint computes the pixels:

```yaml
# A later version, alongside regions: — never instead of it
rows:
  - { role: header,  height: 64 }
  - { role: kpi-row, height: 160, columns: 2 }
  - { role: main,    columns: 2 }      # height: what's left
```

**Why it waits:**
- It introduces a second unit. A file with `height: 64` beside
  `columns: 2` mixes pixels with shares of remaining space, and the two
  axes stop meaning the same thing (vertically you can be absolute,
  horizontally you cannot).
- Equal division rarely lands on the grid. On 1248 usable width, three
  columns want 405.33px and four want 300px — and 300 is not a multiple
  of 8. Snapping afterwards is not a tidy-up: it pushes a region past
  `canvas - margin` or pulls two closer than the gutter, and `bp apply`
  refuses exactly those layouts (`layouts.conflicts`).
- Resolving that means the engine silently decides three things the rest
  of Blueprint never decides for the client: how much to widen a gutter,
  where to put the leftover pixels, and how to round. The core's promise
  is that it does what the files say, to the letter.

**What it would take** (recorded so this isn't re-derived): equal tracks
and equal gaps, every number a multiple of the grid, each gap at least
the gutter, filling the usable span exactly. That rule reproduces the
shipped layouts' own numbers — 2 columns 616/16, 3 columns 400/24,
4 columns 288/32 — so it could land without changing a byte of output.
Its precondition — `margin % grid == 0` and `(canvas - 2 x margin) % grid
== 0` — is a condition of *that engine*, because it computes regions flush
to the margin. It must be checked where `rows:` is used, not on every
guidelines load: the pixel core happily accepts a grid of 10 with a margin
of 16, as long as the regions start at 20.

**What else extensions add here:**
- Weighted columns (`[2, 1]`) and responsive floors, once rows exist
- Conditional regions (present only if the spec has certain visuals)

### 6. Validation rules

Validation rules are pure functions. Extensions add new rules
to the collection:

```python
# Core rule (in validate.py):
def check_density(page, guidelines) -> list[Finding]: ...

# Extension rule (in an extension module):
def check_conditional_format(page, guidelines, ext_config) -> list[Finding]: ...
```

**How it works:**
- Core runs its rules: grid, margin, gutter, bounds, overlap,
  density, palette, typography, title
- Each extension registers additional rules
- Rules are independent — adding one never changes existing ones
- Extension rules can have their own severity (error/warning/off)

**What extensions add here:**
- Conditional format consistency checks
- Sort order validation
- Custom visual property checks
- Cross-page consistency rules

---

## The extension activation pattern

Extensions are always opt-in. The flow:

```
1. Client adds extensions: block to guidelines.yaml
2. Blueprint loads core as usual
3. Blueprint scans extensions: for known extension names
4. Each recognised extension:
   a. Reads its config from the extensions: block
   b. Registers its validator(s)
   c. Registers its render logic (if any)
5. Unknown extension names → warning (not error)
6. Core proceeds as normal, with extensions active
```

A guidelines file with no `extensions:` key runs the core only.
No performance cost. No unexpected behaviour.

---

## Why this works

Three properties of the core design make extensions easy:

1. **YAML dicts are open.** A dict accepts new keys without schema
   changes. Core validates what it knows, ignores what it doesn't.

2. **Visual definitions are data.** The engine reads whatever YAML
   declares — slots, options, type string. Adding a visual or an
   option is a YAML edit, not a code change.

3. **Validation rules are independent.** Each rule is a pure function.
   No rule depends on another. Adding a rule is adding a function
   to a list.

These aren't extension hooks bolted on after the fact. They're
structural properties of the core design. Extensions work because
the core is built from open dicts, declarative data, and independent
rules.

---

## Concrete example: adding "sort" later

When a client asks for visual sorting, the full change is:

```
Core code changes:         zero

New files:
  extensions/sort.py       validation + render logic (~50 lines)

Modified YAML:
  blueprint/visuals/column.yaml   add sort option declaration (1 line)
  blueprint/visuals/bar.yaml      same (1 line)
  blueprint/visuals/table.yaml    same (1 line)

Client writes:
  options: { sort: "Revenue descending" }

That's it. Core engine, core validation, core guidelines — untouched.
```
