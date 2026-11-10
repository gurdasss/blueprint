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
four live here rather than in the core file — they are knobs, not contracts):

```yaml
extensions:
  severity: {grid: warning}         # override a rule's baked-in severity
  decorative_types: [image, shape]  # may contain visuals; exempt from margin/gutter
  max_resize: 0.25                  # bp fmt skips a bigger resize; null: no limit
  typography:                       # text roles beyond the core three
    subtitle:   {font: Segoe UI, size: 12}
    callout:    {font: Segoe UI Light, size: 32}   # a card's value (probe 07)
    card_label: {font: Segoe UI, size: 12}         # the new card's label (probe 15)
```

**What further extensions add here:**
- Four-sided margins (`spacing.margin: { top: 16, bottom: 16, ... }`)
- Two-axis gutters (`spacing.gutter: { horizontal: 16, vertical: 24 }`)
- Canvas background colour
- Approved visual type / layout allowlists
- Visual container styling (border, shadow, corner radius)
- Further typography roles (kpi_value, data_label)

### 2. Visual definitions

The core loads `blueprint/visuals/*.yaml` automatically. Extensions
add visuals by declaring them in `extensions:`:

```yaml
# in guidelines.yaml
extensions:
  custom_visuals:
    search_path: ["my-visuals"]
```

**How it works:**
- Core loader reads `blueprint/visuals/` at startup (always)
- If the custom_visuals extension is active, it also reads from
  the declared search paths
- A custom YAML file with the same `type:` as a built-in replaces it
- `inherits:` works the same way — custom visuals can extend built-ins

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

### 5. Layout rows

Layout rows are dicts. Extensions add keys to them:

```yaml
# Core:
rows:
  - role: main
    columns: 2

# With extensions:
rows:
  - role: main
    columns: 2
    column_widths: [2, 1]          # ← extension: weighted columns
    min_height: 200                # ← extension: responsive constraint
```

**How it works:**
- Core engine reads `role`, `height`, `columns` — the keys it owns
- Unknown keys are passed through
- Extension engine reads its own keys and modifies the computed regions
- Core regions are always computed first; extensions adjust them

**What extensions add here:**
- Weighted column widths (non-equal splits)
- Responsive constraints (min/max height)
- Conditional rows (show only if spec has certain visual types)

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
