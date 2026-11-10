"""Build the Desktop probe for a drill-down of plain columns and a two-column Legend on the line
and area charts (probe 27).

Usage:
    python scripts/probe_line_drill_legend.py <dest folder>

Like probes 22 and 23, it writes **candidate** shapes and asks whether Desktop draws them as
written; like probe 24, the user then refreshes the data and saves, so the evidence ends with a
real save diff. `bp apply` builds each visual as a verified type with a verified binding shape,
then the probe changes it:

- line-drill, area-drill: built as a `column` with a drill list on `Category` (Country, Region,
  both "active", fixture 02 / probe 23), then retyped to `lineChart` / `areaChart`;
- line-legend-2, area-legend-2: built as a `line` / `area` with X-axis Order Date and Legend
  Country (probes 12, 14, 22), then Region is appended to `Series` as a second Legend column
  (no "active", like the first).

Order Date is the calculated column from probe 14, so the data needs Refresh now in Desktop
(no data cache is copied). All content is invented.
"""

import sys
from pathlib import Path

from _probe import git, make_probe
from probe_apply_charts import DATE_COLUMN
from probe_chart_variants import REGION, spec_id

from blueprint.cli import main as bp
from blueprint.pbir import jsonfmt

ROOT = Path(__file__).resolve().parent.parent

SPEC = """\
page: Line Probe
layout: grid-2x3
visuals:
  - {type: header, title: Line drill-down and two-column Legend}
  - {type: column, id: line-drill, title: Line drill-down, slots: {category: ["Sales[Country]", "Sales[Region]"], value: "[Total Amount]"}}
  - {type: column, id: area-drill, title: Area drill-down, slots: {category: ["Sales[Country]", "Sales[Region]"], value: "[Total Amount]"}}
  - {type: line, id: line-legend-2, title: Line two-column legend, slots: {category: "Sales[Order Date]", value: "[Total Amount]", legend: "Sales[Country]"}}
  - {type: area, id: area-legend-2, title: Area two-column legend, slots: {category: "Sales[Order Date]", value: "[Total Amount]", legend: "Sales[Country]"}}
"""

# spec id -> (visualType, append Region to Series?)
CANDIDATES = {
    "line-drill": ("lineChart", False),
    "area-drill": ("areaChart", False),
    "line-legend-2": ("lineChart", True),
    "area-legend-2": ("areaChart", True),
}

STEPS = """\
# Probe 27: a drill-down of plain columns and a two-column Legend on line and area charts

Blueprint built the page **Line Probe** and changed each visual to a candidate. Claude opens it
through the bridge and commits each step itself. Never click a value inside a visual.

1. In Desktop, click **Refresh now** on the banner (Order Date is a calculated column).
2. Press **Ctrl+S**, and tell Claude it's saved.
"""


def make_candidates(report: Path) -> list[str]:
    changed = []
    for f in sorted(report.glob("definition/pages/*/visuals/*/visual.json")):
        doc = jsonfmt.load(f)
        sid = spec_id(doc)
        if sid not in CANDIDATES:
            continue
        vtype, second_legend = CANDIDATES[sid]
        body = doc["visual"]
        body["visualType"] = vtype
        if second_legend:
            body["query"]["queryState"]["Series"]["projections"].append(dict(REGION))
        f.write_bytes(jsonfmt.dump_bytes(doc))
        changed.append(f"{sid} -> {vtype}{' + Legend Region (second column)' if second_legend else ''}")
    return changed


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    dest = Path(sys.argv[1])
    make_probe(ROOT / "fixtures" / "02-card-and-chart", dest, STEPS, snap=True)
    tmdl = dest / "Fixture.SemanticModel" / "definition" / "tables" / "Sales.tmdl"
    text = tmdl.read_bytes().decode()
    tmdl.write_bytes(text.replace("\tpartition Sales = m", DATE_COLUMN + "\tpartition Sales = m", 1).encode())
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "model: add calculated column Order Date (as in probe 14)")

    specs = dest / "specs"
    specs.mkdir()
    (specs / "line-probe.yaml").write_text(SPEC, encoding="utf-8")
    guide = str(ROOT / "guidelines" / "example.yaml")
    if bp(["apply", str(specs / "line-probe.yaml"), "--report", str(dest), "--guidelines", guide]) != 0:
        sys.exit(1)
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "blueprint: apply specs/line-probe.yaml (verified types)")

    print("\n".join(make_candidates(dest / "Fixture.Report")))
    if bp(["manifest", "--report", str(dest), "--guidelines", guide]) != 0:
        sys.exit(1)
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "probe: change visuals to the candidates")
    print(f"Probe ready: {dest}")
