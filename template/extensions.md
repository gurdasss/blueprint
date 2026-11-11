# Extension Points

> How the core 20% is designed so that extensions are additive —
> new keys, new files, new rules — never changes to core code.

---

## Principle

Every extension follows one pattern: **add, never modify.** The core
structure at every layer is a dict (or list of dicts), and extensions add
keys to those dicts — **in the places the core leaves open**.

Which places those are is exact, and it is narrower than "anywhere a dict
is". Since v0.7 the core **refuses** a key it doesn't implement in every
section it owns, naming the closest real key, so that a typo can't load with
a default silently (`spacing: {margn: 16}` used to). The one open section is
`extensions:`. There is **no registry**: nothing registers a validator, and
the core never calls extension code. An extension is code that reads its own
sub-key out of the loaded rules.

---

## Extension points by layer

### 1. Guidelines

The core guidelines file has a reserved top-level key:

```yaml
# extensions: is the one open section. The core reads the five
# sub-keys below and passes everything else through untouched.
extensions:
  conditional_formatting:
    rules: [...]
  custom_visuals:
    search_path: ["my-visuals"]
```

**How it works:**
- The core reads only the sub-keys listed below; it passes the rest through
- An extension reads its own sub-key off the loaded rules — no registration,
  no hook, and nothing in the core knows the extension exists
- A name the core doesn't know is **not** warned about, because the core can't
  tell an extension's key from a typo in one. Inside `extensions:` that is the
  trade for being open
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
    search_path: ["my-visuals"]       # contracts of your own
```

**What further extensions add here**, as their own `extensions:` sub-keys:
- Canvas background colour
- Approved visual type / layout allowlists
- Four-sided margins and two-axis gutters — but **not** by widening
  `spacing.margin` to `{top: …}` or `spacing.gutter` to `{horizontal: …}`.
  Those are core keys the loader refuses as anything but an integer, and
  changing their type is modifying the core, not adding to it. They go in
  as `extensions.four_sided_margin` and the like, which is how
  `template/guidelines.template.yaml` sketches them.
- Visual container styling (border, shadow, corner radius)
- Further typography roles (kpi_value, data_label)

### 2. Visual definitions

**Implemented.** The core loads every contract in `blueprint/visuals/`
automatically — all 18 probe-verified types, from `header` and `card` to
`scatter`, `multi-row-card` and `map`. Extensions add types of your **own** by
declaring a directory (there is no archive to opt into any more):

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

A slot entry may be a field name or a dict, and the dict is where anything
further about that field is said:

```yaml
# Core (today):
slots:
  value:
    field: "Sales[Amount]"
    aggregate: sum        # summarise a column in the visual (probe 29)
    format: "#,0.00"      # a Power BI format string, written verbatim

# What an extension would want to add:
slots:
  value:
    field: "Sales[Amount]"
    conditional_format: red_green  # ← extension key
    display_units: thousands       # ← extension key
    decimal_places: 1              # ← extension key
```

There is no `currency` alias and there won't be one: Desktop writes the
*locale's* symbol, so an alias would have Blueprint invent a symbol the
model never agreed to (`template/plan.md`). Sorting is not here either —
it is `sort: {by, direction}` on the visual, where Desktop keeps it.

**How it works:**
- The core owns `field`, `aggregate` and `format`, and **refuses any other
  key**, naming the three it takes. A page spec is not an open dict: a
  misspelt `fromat` has to be an error, or it silently does nothing
- So an extension key here is the one extension point in this document that
  needs a core change — a small one (the key goes in `spec._SLOT_KEYS` and is
  carried on `FieldRef`), but it is not free the way an `extensions:` sub-key is
- The short form (`value: "[Revenue]"`) still works — the long form is only
  needed when something beside the field is being said

**What extensions add here:**
- Conditional formatting
- Display units and decimal places

### 4. Page spec — visual options

Options are declared in the visual YAML. The engine writes whatever
options it finds. An extension adds options by adding lines to the
visual definition:

```yaml
# visuals/column.yaml (with an extension option)
type: column
visual_type: clusteredColumnChart
region: main
slots: ...
options:
  labels: { object: labels, property: show, values: { "on": "true" } }
  legend: { object: legend, property: position, values: { ... } }
  # An extension option — same format, same engine path:
  tooltip: { object: tooltip, property: show, values: { "on": "true" } }
```

An option is one `objects` entry, so only something Desktop keeps *there*
fits this shape. Sorting does not: Desktop writes it as
`query.sortDefinition` (probe 31), which is why `sort` is a visual key in a
spec and not an option.

**How it works:**
- The engine already writes any option declared in the visual YAML
- Adding an option = adding a line to the YAML
- No engine code change — the render path is generic
- The page spec references it: `options: { tooltip: "on" }`

**What extensions add here:**
- Tooltip configuration
- Drill-through page settings
- Reference lines
- Any Power BI visual property that maps to objects/properties

### 5. Layout regions — and relative positioning later

A layout region needs `role`, `x`, `y`, `w` and `h`. Anything else in the
dict is **ignored, not refused** (`layouts.py`), so an extension can carry
its own keys there — but nothing in the core will read them, and a typo in
one of them is silent. Of the two examples below, Blueprint today reads
neither:

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
- Rules are independent — adding one never changes existing ones
- An extension's rule runs in the extension's own command or pass; `bp check`
  has no plug-in point, and `extensions.severity` only accepts the core rule
  ids (`guidelines.RULES`), so an extension rule carries its own severity
  until someone adds one

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
2. Blueprint loads the core as usual, reading the five sub-keys it knows
   and passing the rest of extensions: through untouched
3. The extension's own code reads its sub-key off the loaded rules
4. Unknown names are neither read nor warned about — the core cannot tell
   an extension's key from a typo in one
```

The core does not scan for extensions, recognise them or call them: step 3
is the extension doing the work, not Blueprint. A guidelines file with no
`extensions:` key runs the core only. No performance cost.

---

## Why this works

Three properties of the core design make extensions easy:

1. **One section is open by design.** `extensions:` accepts new keys
   without a schema change, while every core section refuses what it
   doesn't implement — so openness is a place, not a habit.

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

## Concrete example: what adding an option actually cost

Sorting was this document's example of a future extension. It shipped in
v0.6 **as core** instead — `sort: {by, direction}` on a visual, verified in
probe 31 — because a spec that can't say what a chart is sorted by was
missing something the core 20% needs, not something a client extends.

The part the example got right is the shape of an option. Adding `labels`
and `legend` to `pie` and `donut` in v0.9.0 was:

```
Core code changes:         zero

Modified YAML:
  blueprint/visuals/pie.yaml      the two option declarations
  blueprint/visuals/donut.yaml    the same

Client writes:
  options: { labels: "off", legend: "top" }
```

For a contract **the core ships**, that is not the whole cost: the shape has
to be verified in Desktop first — a candidate probe for what Desktop writes
and an acceptance probe for what Blueprint writes (here 37 and 40), which is
this repo's first rule, not a formality. For a client's **own** contract,
under `extensions.custom_visuals.search_path`, the YAML edit really is all
of it: they are describing a visual they already know.

The engine writes whatever a contract declares, so an option really is a
YAML edit. What is *not* free is anything the core has to recognise: a new
slot long-form key, a new rule in `bp check`, or a guidelines key outside
`extensions:`. Those are core changes, and this document says so above
rather than promising a hook that doesn't exist.
