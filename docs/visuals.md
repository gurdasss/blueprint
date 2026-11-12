# Visual Type System

> How Blueprint defines, loads and creates visuals.

---

## How it works

A visual definition is a YAML file that says what a visual type **is** —
its Power BI type string, what data slots it has, and what formatting
options it supports. Blueprint ships 18 of these in `blueprint/visuals/`,
one per probe-verified type.

The first time anything asks for the contracts, Blueprint reads every visual
YAML, resolves `inherits:`, and keeps the result as a dict of `Contract`
objects (`slots.contracts()`). That is lazy, not at startup: a command that
never needs a visual type never reads them. The result is cached for the
rest of the process, once per distinct set of extra directories. When
`bp apply` runs, it combines each visual's contract with the client's page
spec to produce the PBIR JSON objects, then writes them to disk.

```
                        ┌─────────────────────────────────┐
                        │   First use (cached after)      │
   blueprint/visuals/   │                                 │
   *.yaml (+ yours)     │  Read every YAML                │
   ──────────────────▶  │  Resolve inherits: references   │
                        │  Result: dict[str, Contract]    │
                        └────────────┬────────────────────┘
                                     │
                                     ▼
                        ┌─────────────────────────────────┐
                        │         Per spec                │
                        │                                 │
   Page spec            │  1. Parse and check slots       │
   ──────────────────▶  │     against the contract        │
                        │  2. Place into layout regions   │
   TMDL model           │  3. Resolve fields against TMDL │
   ──────────────────▶  │  4. Build PBIR JSON in memory   │
                        │  5. Write, or write nothing     │
                        └────────────┬────────────────────┘
                                     │
                                     ▼
                              PBIR files in PBIP
```

---

## Visual definition format

Each YAML file defines one visual type: its `type`, `visual_type` and default
`region`, plus its `slots` and its `options`. The file name must equal
`type`, or the loader refuses it.

```yaml
# blueprint/visuals/column.yaml
type: column                          # name used in page specs
visual_type: clusteredColumnChart     # Power BI's internal type string
region: main                          # default layout role
slots:
  category:
    role: Category                    # PBIR query role name
    accepts: [column, hierarchy]      # what field types are valid
    required: true
    ordered: true                     # list = drill-down path
    active: true                      # Desktop marks this well's columns "active"
    active_levels: first              # of a hierarchy: first (default) or all (a slicer's Field)
  value:
    role: Y
    accepts: measure
    required: true
    ordered: true                     # list = multiple series
    list_excludes: [legend]           # a list here is refused if `legend` is also set
options:
  labels: { object: labels, property: show, values: { "on": "true" } }
  legend: { object: legend, property: position, values: { ... } }
```

That's the complete definition. The engine needs nothing else to create
a column chart.

---

## Inheritance

Many visuals share the same slot structure. The bar chart's slots are the
column chart's, with a different `visual_type` string. Instead of
duplicating slots, a visual can inherit from another:

```yaml
# blueprint/visuals/bar.yaml
type: bar
visual_type: clusteredBarChart
inherits: column                      # gets column's slots, options, region
```

Three lines of YAML. The loader copies column's slots and options into bar,
then applies any overrides bar declares. The result in memory is a
complete `Contract` — the engine never sees the inheritance, just the
final merged object.

The loader is strict about it, and each of these is a `ContractError`:

- a cycle, or a parent that isn't a loaded type;
- a child that doesn't declare its own `type` and `visual_type`;
- a core contract inheriting from outside the core (the core must load on
  its own);
- two files defining the same type, or two types claiming the same PBIR
  `visual_type`. Nothing is silently shadowed.

All files in every directory are read before any `inherits:` is resolved, so
a custom type can inherit a core parent.

**One shipped contract uses it: `bar.yaml`.** It was deliberately held
back at first, because every contract cites the probe that verified its
shape and `options` are not slots — probe 23 verified data labels and a
legend position on the column and stacked charts, never on the clustered
bar, so inheriting then would have shipped an option nobody had checked.
Probe 31 wrote those shapes onto a clustered bar and Desktop drew and kept
them, which made `bar` identical to `column` apart from the PBIR type, and
`inherits: column` became the honest way to say so.

That's the rule for using it: inherit when a probe has shown the parent's
shapes work on the child too, not to save typing. `line` states its own
slots for exactly that reason — its `legend` excludes a measure list beside
it. Otherwise inheritance is for the types a client adds, the case
`extensions.custom_visuals.search_path` serves.

### What inherits copies

| Field | Behavior |
|-------|----------|
| `slots` | Copied from parent. Child can add new slots or override individual ones. Mentioned but empty (`slots: {}`): the child has none. |
| `options` | Copied from parent. Child can add or override. Mentioned but empty: the child has none. |
| `region` | Copied from parent. Child can override. |
| `visual_type` | **Never inherited.** Every visual must declare its own. |
| `type` | **Never inherited.** Every visual must declare its own. |

### Which shipped types inherit

Only one does: `bar` inherits `column`. Every other contract states its own
slots, because each one cites the probe that verified that shape.

```
column  ← bar                         (inherits)

          stacked-column, stacked-bar, stacked-column-100, area
          are written out in full, each its own probe-verified type.
          Their slots are column's, except that `category` takes a
          plain column and not a model hierarchy

line      its own slots; legend excludes a measure list beside it

card, kpi, table, matrix, header, ...   standalone
```

---

## Adding a new visual

Drop a YAML file. That's it.

**If an existing visual's slots fit** (most chart types):

```yaml
# my-visuals/waterfall.yaml
type: waterfall
visual_type: waterfallChart
inherits: column
```

**If it needs unique slots:**

```yaml
# my-visuals/gauge.yaml
type: gauge
visual_type: gauge
region: main
slots:
  value:
    role: Y
    accepts: measure
    required: true
  target:
    role: TargetValue
    accepts: measure
```

Then tell Blueprint where that directory is — either in your guidelines,

```yaml
extensions:
  custom_visuals:
    search_path: ["my-visuals"]   # relative to this guidelines file
```

or with `--visuals DIR` on `apply`, `describe` and `manifest` for one run.
The type is available on the next `bp apply`. No code changes.

Most clients never define one, which is why this is opt-in rather than a
core guidelines key. A type defined twice is refused, and a type with no
contract is refused by name — adding a contract is the only way in.

Only ship a type whose PBIR shape a Desktop probe has verified, and cite
the probe in the YAML. That is the rule the shipped contracts follow, and
the reason a guessed `visual_type` string is worse than no type at all:
Desktop will either ignore the visual or draw something nobody intended.

### Load order

```
1. blueprint/visuals/*                              ← the 18 core types, always loaded
2. extensions.custom_visuals.search_path            ← yours, declared in guidelines
3. --visuals DIR                                    ← yours, for one run
```

The core always loads; there is no opt-in and no way to switch it off.

---

## The runtime flow in detail

What happens when `bp apply spec.yaml` runs:

```
1. contracts() → read the YAMLs, resolve inherits → dict[str, Contract]
   (first call only; cached for the process)

2. spec.parse — the whole spec, every visual:
   a. unknown type? refused, naming the types there are
   b. does each slot exist, accept this kind of field, and take a list?
   c. are the required slots there? every problem is collected with its
      location and reported together

3. layouts.place — each visual takes the next free region of its role

4. Resolve every field against the TMDL model (apply._resolve)

5. Build each visual's PBIR JSON in memory (pbir/render.py):
   - visual_type string from the contract
   - query roles + field bindings from contract slots + spec fields
   - formatting properties from contract options + spec options
   - position from the layout region it was placed in

6. Every spec given, all pre-flighted and built? Write them all to disk.
   Any failure in any of them? Write nothing.
```

The visual definitions provide the **structure** (what a column chart is).
The page spec provides the **content** (what this column chart shows).
The engine combines them into **PBIR JSON** (what Power BI reads).

---

## The core types

All 18 are core and load automatically — there is no opt-in and no archive
(that split was a v0.6 refactor holding pen, removed in v0.8.0). The ones a
standard report is built from come first:

| Type | What it shows | Slots |
|------|--------------|-------|
| **header** | Page title text | (none — textbox) |
| **card** | Single KPI number | value |
| **kpi** | Value + trend + target | value, trend, target |
| **column** | Categories vs values | category, value, legend |
| **bar** | Horizontal categories | inherits column |
| **line** | Trends over time | category, value, legend |
| **table** | Rows and columns | columns (mixed types) |
| **matrix** | Rows x columns x measures | rows, columns, values |
| **slicer** | A filter the reader drives | field |
| **pie**, **donut** | Share of a total | category, value, details |
| **area**, **stacked-column**, **stacked-column-100**, **stacked-bar** | Composition over a category | category, value, legend |
| **scatter** | Two measures per category | category, x, y, size, legend |
| **multi-row-card** | A row per value, fields side by side | fields (columns and measures) |
| **map** | Bubbles per location | category, size, legend |

Each contract cites the probe that verified its PBIR shape, and a type with
no probe behind it doesn't ship. `map` also needs Desktop's "Map and filled
map visuals" security setting on, which is off by default.

Types of your **own** still load from a directory you declare
(`extensions.custom_visuals.search_path`, or `--visuals DIR` for one run).
