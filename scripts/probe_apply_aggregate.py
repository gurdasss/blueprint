"""Build the Desktop probe that saves `bp apply`'s aggregations and formats (probe 30).

Usage:
    python scripts/probe_apply_aggregate.py <dest folder>

Probe 29 recorded the shapes from Desktop's own output: an implicit aggregate of a column
(`{"Aggregation": {"Expression": {"Column": …}, "Function": N}}`, each `Function` code, each
`queryRef`/`nativeQueryRef`) and a per-visual data format as a projection `"format"` string.
Blueprint now writes both, which is a different claim: that Desktop **accepts what Blueprint
wrote**. That's the bar every other type cleared (probe 20's shapes -> probe 21's acceptance,
probe 22/23's -> probe 24's), so this probe applies specs using all six aggregations and several
format strings across a card, a column chart and a table, on a fresh copy of fixture 02.

The user clicks Refresh now (which dirties the report) and saves; the save diff shows what
Desktop keeps, rewrites or drops. All content is invented.
"""

import sys
from pathlib import Path

from _probe import git, make_probe

from blueprint.cli import main as bp

ROOT = Path(__file__).resolve().parent.parent

MONEY = '"\\"$\\" #,0.00;(\\"$\\" #,0.00);\\"$\\" #,0.00"'

SPECS = {
    "aggregates.yaml": """\
page: Aggregates
layout: dashboard-6
visuals:
  - {type: header, title: Aggregates}
  - {type: card, title: Sum, region: kpi-row, slots: {value: {field: "Sales[Amount]", aggregate: sum}}}
  - {type: card, title: Average, region: kpi-row, slots: {value: {field: "Sales[Amount]", aggregate: average}}}
  - {type: card, title: Distinct count, region: kpi-row, slots: {value: {field: "Sales[Amount]", aggregate: distinctcount}}}
  - {type: column, title: Min by country, slots: {category: "Sales[Country]", value: {field: "Sales[Amount]", aggregate: min}}}
  - {type: column, title: Max by country, slots: {category: "Sales[Country]", value: {field: "Sales[Amount]", aggregate: max}}}
  - {type: column, title: Count by country, slots: {category: "Sales[Country]", value: {field: "Sales[Amount]", aggregate: count}}}
""",
    "formats.yaml": f"""\
page: Formats
layout: dashboard-6
visuals:
  - {{type: header, title: Formats}}
  - {{type: card, title: Whole number, region: kpi-row, slots: {{value: {{field: "[Total Amount]", format: "#,0"}}}}}}
  - {{type: card, title: Two decimals, region: kpi-row, slots: {{value: {{field: "[Total Amount]", format: "#,0.00"}}}}}}
  - {{type: card, title: Currency, region: kpi-row, slots: {{value: {{field: "[Total Amount]", format: {MONEY}}}}}}}
  - {{type: column, title: Percent by country, slots: {{category: "Sales[Country]", value: {{field: "[Total Amount]", format: "0.00%"}}}}}}
  - {{type: table, title: Formatted and aggregated, slots: {{columns: ["Sales[Country]", {{field: "Sales[Amount]", aggregate: sum, format: {MONEY}}}, {{field: "[Total Amount]", format: "#,0.00"}}]}}}}
  - {{type: column, title: Plain, slots: {{category: "Sales[Country]", value: "[Total Amount]"}}}}
"""
}

STEPS = """\
# Probe 30: Desktop's save of bp apply's aggregations and formats

Blueprint built **Aggregates** and **Formats**. Claude opens the report through the bridge,
captures both pages and commits each step; you only:

1. Click **Refresh now** on the banner, then **Ctrl+S**.

Never click a value inside a visual, and don't open a field's menu: this probe is about what
Desktop does with what Blueprint wrote, untouched.

What it settles:
- whether Desktop keeps each `Aggregation` + `Function` as written, with Blueprint's
  `queryRef`/`nativeQueryRef`, or rewrites them;
- whether the projection `"format"` string survives a save and is what the visual draws
  (the card should show `$500.00` for the currency one, `500.00` for two decimals);
- whether a format on a measure projection behaves like one on an aggregated column.
"""

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    dest = Path(sys.argv[1])
    make_probe(ROOT / "fixtures" / "02-card-and-chart", dest, STEPS, snap=True)

    specs = dest / "specs"
    specs.mkdir()
    for name, body in SPECS.items():
        (specs / name).write_text(body, encoding="utf-8")
    if bp(["apply", str(specs), "--report", str(dest),
           "--guidelines", str(ROOT / "guidelines" / "example.yaml")]) != 0:
        sys.exit(1)
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "blueprint: apply specs/ (aggregates.yaml, formats.yaml)")
    print(f"Probe ready: {dest}")
