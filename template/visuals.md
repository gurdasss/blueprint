# Visual Type System

> How Blueprint defines, loads and creates visuals.

---

## How it works

A visual definition is a YAML file that says what a visual type **is** —
its Power BI type string, what data slots it has, and what formatting
options it supports. Blueprint already ships 15 of these in
`blueprint/visuals/`.

At startup, Blueprint loads every visual YAML into memory as a dict of
in-memory objects. When `bp apply` runs, it combines each visual's
definition with the client's page spec to produce the PBIR JSON objects,
then writes them to disk. Nothing persists in memory after the run.

```
                        ┌─────────────────────────────────┐
                        │         Startup (once)          │
   blueprint/visuals/   │                                 │
   *.yaml               │  Load all YAMLs                 │
   ──────────────────▶  │  Resolve inherits: references   │
                        │  Result: dict[str, VisualDef]   │
   guidelines           │                                 │
   visuals.search_path  │  Also load from search_path     │
   ──────────────────▶  │  directories (client additions) │
                        └────────────┬────────────────────┘
                                     │
                                     ▼
                        ┌─────────────────────────────────┐
                        │         Runtime (per spec)      │
                        │                                 │
   Page spec            │  1. Validate spec fields        │
   ──────────────────▶  │     against visual's slots      │
                        │  2. Resolve fields against TMDL │
   TMDL model           │  3. Build PBIR JSON objects     │
   ──────────────────▶  │     in memory                   │
                        │  4. Write to disk                │
                        └────────────┬────────────────────┘
                                     │
                                     ▼
                              PBIR files in PBIP
```

---

## Visual definition format

Each YAML file defines one visual type. Four fields:

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
  value:
    role: Y
    accepts: measure
    required: true
    ordered: true                     # list = multiple series
options:
  labels: { object: labels, property: show, values: { "on": "true" } }
  legend: { object: legend, property: position, values: { ... } }
```

That's the complete definition. The engine needs nothing else to create
a column chart.

---

## Inheritance

Many visuals share the same slot structure. Bar is identical to column
except for the `visual_type` string. Instead of duplicating slots,
a visual can inherit from another:

```yaml
# blueprint/visuals/bar.yaml
type: bar
visual_type: clusteredBarChart
inherits: column                      # gets column's slots, options, region
```

Three lines. The loader copies column's slots and options into bar,
then applies any overrides bar declares. The result in memory is a
complete VisualDef — the engine never sees the inheritance, just the
final merged object.

### What inherits copies

| Field | Behavior |
|-------|----------|
| `slots` | Copied from parent. Child can add new slots or override individual ones. |
| `options` | Copied from parent. Child can add or override. |
| `region` | Copied from parent. Child can override. |
| `visual_type` | **Never inherited.** Every visual must declare its own. |
| `type` | **Never inherited.** Every visual must declare its own. |

### Existing visuals that would share slots

```
column  ← bar, stacked-column, stacked-bar, stacked-column-100, area
           (all: category + value, same roles)

line    ← (extends column, adds legend slot)

card    ← standalone (single value)

kpi     ← standalone (value + trend + target)

table   ← matrix (columns of mixed types)

header  ← standalone (no slots, textbox)
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

**Then point your guidelines at the folder:**

```yaml
# in guidelines.yaml
visuals:
  search_path: ["my-visuals"]
```

Next `bp apply` run, the new type is available in page specs.
No code changes. No Blueprint updates.

### Load order

```
1. blueprint/visuals/*          ← built-in defaults (ships with Blueprint)
2. search_path directories      ← client additions/overrides (later wins)
```

A client file with the same `type:` as a built-in replaces it.
That's how a client customizes defaults (e.g. changing a visual's
default region).

---

## The runtime flow in detail

What happens when `bp apply spec.yaml` runs:

```
1. Load visual YAMLs → resolve inherits → dict[str, VisualDef]

2. Parse page spec → list of visual specs with types, titles, slots

3. For each visual in the spec:
   a. Look up type in registry → get its VisualDef
   b. Validate: does each spec slot match what the def accepts?
   c. Resolve: does each field exist in the TMDL model?
   d. Build: construct the PBIR JSON object in memory
      - visual_type string from the def
      - query roles + field bindings from def slots + spec fields
      - formatting properties from def options + spec options
      - position from layout + guidelines engine

4. All visuals validated and built? Write them all to disk.
   Any failure? Write nothing.

5. Memory is released. Nothing persists.
```

The visual definitions provide the **structure** (what a column chart is).
The page spec provides the **content** (what this column chart shows).
The engine combines them into **PBIR JSON** (what Power BI reads).

---

## Core 20% visual types

These 7 types cover every standard report pattern:

| Type | What it shows | Slots |
|------|--------------|-------|
| **header** | Page title text | (none — textbox) |
| **card** | Single KPI number | value |
| **kpi** | Value + trend + target | value, trend, target |
| **column** | Categories vs values | category, value |
| **line** | Trends over time | category, value, legend |
| **bar** | Horizontal categories | inherits column |
| **table** | Rows and columns | columns (mixed types) |

### Deferred (ship via extension or client-added visuals)

| Type | Status |
|------|--------|
| pie, donut | Slot structure exists, verified by probes |
| area, stacked-column, stacked-bar, stacked-column-100 | Inherit from column |
| matrix | Inherits from table |
| slicer | Unique slot structure |

These already have definitions in `blueprint/visuals/`. A client can
use them today by adding them to their `visuals.search_path`. They're
deferred from core only because a client doesn't need them to build
a functional report.
