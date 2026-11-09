"""Build the Desktop probe for drill-downs, measure lists and Details on the new chart types, and
data labels and legend position (probe 23).

Usage:
    python scripts/probe_chart_options.py <dest folder> [<probe with a data cache>]

Like probe 22, it writes **candidate** shapes and asks whether Desktop draws them as written.
`bp apply` builds each visual as a verified type with a verified binding shape, then the probe
changes it:

- stacked column `columnChart` with a drill-down (Country, Region): the column chart's drill list
  (fixture 02, probe 04);
- stacked bar `barChart` with two measures: the bar chart's measure list (probes 20, 21);
- donut `donutChart` with a drill-down, and with Details = Region: the pie's (probe 11);
- area `areaChart` with two measures: the line chart's measure list (probes 20, 21);
- a clustered column chart with two measures, data labels on
  (`objects.labels[0].properties.show = true`) and the legend at the bottom
  (`objects.legend[0].properties.position = 'Bottom'`). Those two literals are guesses at
  Desktop's shape; the page capture shows whether Desktop honours them.

`Target Amount` is added as in probe 20. A second argument copies an earlier probe's data cache.
All content is invented.
"""

import shutil
import sys
from pathlib import Path

from _probe import git, make_probe
from probe_apply_slicer_matrix import MEASURE
from probe_chart_variants import make_candidates

from blueprint.cli import main as bp

ROOT = Path(__file__).resolve().parent.parent

SPEC = """\
page: Variants 2
layout: grid-2x3
visuals:
  - {type: header, title: Variants 2}
  - {type: column, id: stacked-drill, title: Stacked column drill-down, slots: {category: ["Sales[Country]", "Sales[Region]"], value: "[Total Amount]"}}
  - {type: bar, id: stacked-bar-measures, title: Stacked bar two measures, slots: {category: "Sales[Country]", value: ["[Total Amount]", "[Target Amount]"]}}
  - {type: pie, id: donut-drill, title: Donut drill-down, slots: {category: ["Sales[Country]", "Sales[Region]"], value: "[Total Amount]"}}
  - {type: pie, id: donut-details, title: Donut with details, slots: {category: "Sales[Country]", value: "[Total Amount]", details: "Sales[Region]"}}
  - {type: line, id: area-measures, title: Area two measures, slots: {category: "Sales[Country]", value: ["[Total Amount]", "[Target Amount]"]}}
  - {type: column, id: labels-legend, title: Labels on legend bottom, slots: {category: "Sales[Country]", value: ["[Total Amount]", "[Target Amount]"]}}
"""


def _lit(value: str) -> dict:
    return {"expr": {"Literal": {"Value": value}}}


CANDIDATES = {
    "stacked-drill": ("columnChart", False, None),
    "stacked-bar-measures": ("barChart", False, None),
    "donut-drill": ("donutChart", False, None),
    "donut-details": ("donutChart", False, None),
    "area-measures": ("areaChart", False, None),
    "labels-legend": ("clusteredColumnChart", False, {
        "labels": [{"properties": {"show": _lit("true")}}],
        "legend": [{"properties": {"position": _lit("'Bottom'")}}],
    }),
}

STEPS = """\
# Probe 23: drill-downs, measure lists and Details on the new chart types; labels and legend

Blueprint built the page **Variants 2** and changed each visual to a candidate. Claude drives
Desktop through the bridge and commits each step itself. Never click a value inside a visual.
"""

if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        sys.exit(__doc__)
    dest = Path(sys.argv[1])
    make_probe(ROOT / "fixtures" / "02-card-and-chart", dest, STEPS, snap=True)
    tmdl = dest / "Fixture.SemanticModel" / "definition" / "tables" / "Sales.tmdl"
    text = tmdl.read_bytes().decode()
    tmdl.write_bytes(text.replace("\tcolumn Country", MEASURE + "\tcolumn Country", 1).encode())
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "model: add measure Target Amount (as Desktop wrote it in probe 20)")

    specs = dest / "specs"
    specs.mkdir()
    (specs / "variants-2.yaml").write_text(SPEC, encoding="utf-8")
    guide = str(ROOT / "guidelines" / "example.yaml")
    if bp(["apply", str(specs / "variants-2.yaml"), "--report", str(dest), "--guidelines", guide]) != 0:
        sys.exit(1)
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "blueprint: apply specs/variants-2.yaml (verified types)")

    print("\n".join(make_candidates(dest / "Fixture.Report", CANDIDATES)))
    if bp(["manifest", "--report", str(dest), "--guidelines", guide]) != 0:
        sys.exit(1)
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "probe: change visuals to the candidates")

    if len(sys.argv) == 3:
        cache = Path(sys.argv[2]) / "Fixture.SemanticModel" / ".pbi" / "cache.abf"
        shutil.copy2(cache, dest / "Fixture.SemanticModel" / ".pbi" / "cache.abf")
        print(f"data cache copied from {cache}")
    print(f"Probe ready: {dest}")
