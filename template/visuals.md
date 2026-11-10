# Visual Type System

> How Blueprint defines, stores and creates visuals — and which ones
> belong in core 20%.

---

## Core 20% visual types

These 7 types are sufficient to build any functional report:

| Type | What it shows | Why it's core |
|------|--------------|---------------|
| **header** | Page title text | Every page needs one |
| **card** | Single KPI number | The most basic data visual |
| **kpi** | Value + trend + optional target | Dashboard staple |
| **column** | Categories vs values (vertical bars) | The default chart |
| **line** | Trends over time | Time series are everywhere |
| **bar** | Categories vs values (horizontal bars) | Long category names |
| **table** | Rows and columns of data | Detail and drill-down |

With these 7, a client can build: a KPI dashboard, an analytical page,
a detail page, a summary page, a trend page. Every standard report
pattern is covered.

### What's deferred (useful, not essential)

| Type | Why deferred |
|------|-------------|
| pie, donut | Controversial in data viz; column/bar covers the same data |
| area | Line chart covers the same use case |
| stacked-column, stacked-bar, stacked-column-100 | Variants of column/bar |
| matrix | Table covers most cases; matrix adds pivot |
| slicer | Interactive filtering — useful but not structural |

These ship when the extension system exists, or earlier if a client needs them.

---

## The duplication problem

Today, 15 visual types are defined as 15 separate YAML files. But most
share the same slot shape:

```
column, bar, line, area, stacked-column, stacked-bar, stacked-column-100
→ ALL have: category (Category) + value (Y) + optional legend (Series)

pie, donut
→ BOTH have: category (Category) + value (Y) + optional details (Series)
```

That's 9 visuals with essentially the same contract, differing only in:
1. The `visual_type` string (what Power BI calls it internally)
2. Which options they support (labels, legend position)
3. Minor slot differences (hierarchy support, list behavior)

Adding a new chart variant (say, `waterfall`) means copying an existing
file and changing one string. That works but doesn't scale.

---

## Composable system: slot shapes + visual identity

Instead of one file per visual, split the definition into two layers:

### Layer 1: Slot shapes (reusable)

A slot shape defines the field structure — what slots exist, what they
accept, and how they behave. Shapes are the building blocks.

```yaml
# shapes/category_value.yaml
shape: category_value
description: A category axis and a value axis (most charts)
slots:
  category:
    role: Category
    accepts: [column, hierarchy]
    required: true
    ordered: true            # list = drill-down
  value:
    role: Y
    accepts: measure
    required: true
    ordered: true            # list = multiple series
```

```yaml
# shapes/category_value_legend.yaml
shape: category_value_legend
extends: category_value
slots:
  legend:
    role: Series
    accepts: column
    constraint: list_excludes [value]   # can't have multi-value + legend
```

```yaml
# shapes/single_value.yaml
shape: single_value
slots:
  value:
    role: Data
    accepts: measure
    required: true
```

```yaml
# shapes/mixed_columns.yaml
shape: mixed_columns
slots:
  columns:
    role: Values
    accepts: [column, measure, hierarchy]
    required: true
    ordered: true
```

### Layer 2: Visual identity (per type)

A visual type binds a slot shape to a Power BI visual type, a default
region, and optional formatting options. This is the lightweight part.

```yaml
# visuals/column.yaml
type: column
visual_type: clusteredColumnChart
shape: category_value              # ← references a reusable shape
region: main
options:
  labels: { object: labels, property: show, values: { "on": "true" } }
  legend: { object: legend, property: position, values: { top: "'Top'", bottom: "'Bottom'", left: "'Left'", right: "'Right'" } }
```

```yaml
# visuals/bar.yaml
type: bar
visual_type: clusteredBarChart
shape: category_value              # ← same shape as column
region: main
options:
  labels: { object: labels, property: show, values: { "on": "true" } }
  legend: { object: legend, property: position, values: { top: "'Top'", bottom: "'Bottom'", left: "'Left'", right: "'Right'" } }
```

```yaml
# visuals/line.yaml
type: line
visual_type: lineChart
shape: category_value_legend       # ← shape with legend support
region: main
```

```yaml
# visuals/card.yaml
type: card
visual_type: cardVisual
shape: single_value
region: main
```

```yaml
# visuals/table.yaml
type: table
visual_type: tableEx
shape: mixed_columns
region: main
```

### Adding a new visual type

With the composable system, adding `waterfall` is:

```yaml
# visuals/waterfall.yaml
type: waterfall
visual_type: waterfallChart
shape: category_value              # ← reuse existing shape
region: main
```

One file, three lines of identity, zero duplicated slot logic.

If the new type needs a unique slot structure (like KPI's value + trend +
target), you write a new shape first, then reference it.

---

## How the system creates a visual (the render path)

The render engine needs three pieces of information to write a PBIR visual:

```
1. Visual identity    → visual_type string (from the visual definition)
2. Slot bindings      → which fields go in which query roles (from the shape + spec)
3. Options            → formatting properties to set (from the visual definition + spec)
```

The engine assembles the PBIR JSON from these:

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Slot shape  │     │   Visual ID  │     │  Page spec   │
│              │     │              │     │              │
│  category: Y │     │ visual_type: │     │ slots:       │
│  value: Y    │     │  clustered   │     │  category: X │
│  legend: ?   │     │  ColumnChart │     │  value: Y    │
└──────┬───────┘     └──────┬───────┘     └──────┬───────┘
       │                    │                    │
       └────────────────────┼────────────────────┘
                            ▼
                    ┌──────────────┐
                    │    Engine    │
                    │              │
                    │  Writes:     │
                    │  visual.json │
                    │  query roles │
                    │  objects     │
                    └──────────────┘
```

The engine doesn't care whether it's a column chart or a waterfall chart.
It sees: "a visual_type string, a set of query role bindings, and some
object properties to set." The slot shape tells it the roles; the visual
identity tells it the type string; the spec tells it the fields.

---

## Core shapes summary

For the core 7 visual types, we need 5 shapes:

| Shape | Slots | Used by |
|-------|-------|---------|
| `single_value` | value (measure) | card |
| `category_value` | category + value | column, bar |
| `category_value_legend` | category + value + legend | line (extension: area, stacked-*) |
| `mixed_columns` | columns (mixed types) | table |
| `indicator` | value + trend + target | kpi |

Plus `header` which has no slots (it's a textbox with text).

---

## Workflow for adding a new visual

1. **Does an existing shape fit?** Most chart types reuse `category_value`
   or `category_value_legend`. If yes, skip to step 3.

2. **Define a new shape.** Write a shape YAML with the slot structure.
   This is where you declare roles, accepted types, and constraints.

3. **Define the visual identity.** Write a visual YAML: type name,
   Power BI visual_type, shape reference, default region, options.

4. **Verify with a Desktop probe.** Build the visual in Desktop, save,
   diff, confirm the PBIR matches what the shape declares. Cite the
   probe in the YAML.

5. **The visual is available.** `bp describe` lists it, `bp apply`
   creates it. No engine changes needed.

Steps 1–3 are YAML. Step 4 is a one-time verification. Step 5 is
automatic. The engine never changes when a visual type is added.
