"""Build the Desktop probe for `bp apply` output with line, bar and drill-down pie charts (probe 14).

Usage:
    python scripts/probe_apply_charts.py <dest folder>

Probes 11 and 12 verified the shapes Desktop writes for these charts; probe 05 and 09 confirmed
Desktop accepts Blueprint's other types as written. This applies two specs to a copy of fixture
02 and has Desktop open and save the result. It also settles an open item from probe 13: a date
column bound as a plain `Column` (Blueprint's `Table[Column]`), not through its date hierarchy.

The fixture has no date column, so one is added to Sales.tmdl the way probe 13 created it in
Desktop (same DAX), but without the automatic date tables: the diff shows what Desktop adds. All
content is invented.
"""

import sys
from pathlib import Path

from _probe import git, make_probe

from blueprint.cli import main as bp

ROOT = Path(__file__).resolve().parent.parent

DATE_COLUMN = (
    "\tcolumn 'Order Date' = DATE(2026, LEN(Sales[Region]), 1)\r\n"
    "\t\tformatString: General Date\r\n"
    "\t\tlineageTag: 5df9c12a-c1c3-4e2f-9b10-d5733738eeff\r\n"
    "\t\tsummarizeBy: none\r\n"
    "\r\n"
    "\t\tannotation SummarizationSetBy = Automatic\r\n"
    "\r\n"
)

SPECS = {
    "dates-and-bars.yaml": """\
page: Dates & Bars
layout: standard-4-up
visuals:
  - type: line
    title: By Order Date
    slots: {category: "Sales[Order Date]", value: "[Total Amount]"}
  - type: bar
    title: By Geography
    slots: {category: ["Sales[Country]", "Sales[Region]"], value: "[Total Amount]"}
""",
    "pies-and-lines.yaml": """\
page: Pies & Lines
layout: standard-4-up
visuals:
  - type: pie
    title: Share by Geography
    slots: {category: ["Sales[Country]", "Sales[Region]"], value: "[Total Amount]"}
  - type: line
    title: By Country and Region
    slots: {category: "Sales[Country]", value: "[Total Amount]", legend: "Sales[Region]"}
""",
}

STEPS = """\
# Probe 14: does Desktop accept Blueprint's line, bar and drill-down pie?

Blueprint added two pages (specs in `specs/`):

- **Dates & Bars**: a line chart "By Order Date" (X-axis: the date column Order Date) and a
  clustered bar chart "By Geography" (Country, then Region: a drill-down).
- **Pies & Lines**: a pie "Share by Geography" (Legend: Country, then Region: a drill-down) and a
  line chart "By Country and Region" (Legend: Region).

The model also has a new date column, **Order Date**, added outside Desktop. After each step:
**Ctrl+S**, then in WSL:

```bash
cd /mnt/c/Users/satwa/blueprint-probes/14-apply-charts
bash snap.sh "<step>"
```

| # | In Power BI Desktop | Then run |
|---|---|---|
| 1 | Open **Fixture.pbip**. Note any error or warning dialog. Look at both pages: is every chart drawn, with its title? Don't change anything. **Ctrl+S**. | `bash snap.sh "01 open and save"` |
| 2 | On **Dates & Bars**, click the **By Order Date** line chart. In its **X-axis** well, write down what the field shows: *Order Date*, or *Date Hierarchy* / Year, Quarter…? In the Data pane, can **Order Date** under Sales be expanded into a Date Hierarchy? Don't change anything. **Ctrl+S**. | `bash snap.sh "02 inspect date axis"` |
| 3 | Try the drill arrows on **By Geography** (bar) and **Share by Geography** (pie): drill into one country, then back up. Then **Ctrl+S**. | `bash snap.sh "03 drill and back"` |

Then close Desktop and tell Claude "probe 14 done", with what you saw in each step.
"""

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    dest = Path(sys.argv[1])
    make_probe(ROOT / "fixtures" / "02-card-and-chart", dest, STEPS, snap=True)

    tmdl = dest / "Fixture.SemanticModel" / "definition" / "tables" / "Sales.tmdl"
    text = tmdl.read_bytes().decode()
    anchor = "\tpartition Sales = m"
    if anchor not in text:
        sys.exit(f"{tmdl}: no {anchor!r} line to insert the date column before")
    tmdl.write_bytes(text.replace(anchor, DATE_COLUMN + anchor, 1).encode())
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "model: add calculated column Order Date (as typed in probe 13)")

    specs = dest / "specs"
    specs.mkdir()
    for name, body in SPECS.items():
        (specs / name).write_text(body, encoding="utf-8")
        code = bp(["apply", str(specs / name), "--report", str(dest),
                   "--guidelines", str(ROOT / "guidelines" / "example.yaml")])
        if code != 0:
            sys.exit(code)
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "blueprint: apply specs/dates-and-bars.yaml and specs/pies-and-lines.yaml")
    print(f"Probe ready: {dest}")
