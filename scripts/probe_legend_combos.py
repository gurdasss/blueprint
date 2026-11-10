"""Build the Desktop probe for Legend combinations and the 'Bottom' legend position (probe 28).

Usage:
    python scripts/probe_legend_combos.py <dest folder> <data cache .abf>

Like probes 22 and 23 it writes **candidate** shapes, opened and reloaded through the bridge
with a page capture per round; nothing is dirty, so there's no save. The model is the demo's
(fixture 02 + Target Amount + Order Date + the Geography hierarchy, as scripts/demo.sh builds
it), so the demo's refreshed data cache fits it. `bp apply` builds verified shapes, then the
probe changes them:

- page **Drill + Legend**: a `column` with a drill list on `Category` (Country, Region, both
  "active"), retyped to lineChart, areaChart, columnChart, hundredPercentStackedColumnChart and
  barChart, each with Legend `Series` = Order Date (no "active");
- page **Measures + Legend**: a `column` with Category Country and `Y` = Total Amount, Target
  Amount, retyped to columnChart, hundredPercentStackedColumnChart, barChart and areaChart, each
  with Legend `Series` = Region; plus two clusteredColumnCharts with the two measures (a legend
  of measure names) to test the legend position: one with
  `objects.legend[0].properties.position = 'Bottom'`, one without.
- `bp theme` writes the guidelines theme, then the probe sets its default legend position to Top
  (`visualStyles["*"]["*"].legend = [{"position": "Top"}]`), so 'Bottom' can be told apart from
  the default (probe 23 couldn't: the base theme's default is bottom).

All content is invented.
"""

import shutil
import sys
from pathlib import Path

from _probe import git, make_probe
from probe_apply_charts import DATE_COLUMN
from probe_apply_hierarchy import HIERARCHY
from probe_chart_variants import REGION, spec_id

from blueprint.cli import main as bp
from blueprint.pbir import jsonfmt

ROOT = Path(__file__).resolve().parent.parent
MEASURE = ("\tmeasure 'Target Amount' = 600\r\n\t\tformatString: 0\r\n"  # as scripts/demo.sh
           "\t\tlineageTag: 9ab090f9-bd7f-43c4-82be-86470a46784b\r\n\r\n")
ORDER_DATE = {"field": {"Column": {"Expression": {"SourceRef": {"Entity": "Sales"}}, "Property": "Order Date"}},
              "queryRef": "Sales.Order Date", "nativeQueryRef": "Order Date"}

DRILL = '{category: ["Sales[Country]", "Sales[Region]"], value: "[Total Amount]"}'
TWO = '{category: "Sales[Country]", value: ["[Total Amount]", "[Target Amount]"]}'
SPECS = {
    "drill-legend.yaml": "page: Drill + Legend\nlayout: grid-2x3\nvisuals:\n"
    "  - {type: header, title: Drill-down with a Legend}\n"
    + "".join(f"  - {{type: column, id: {sid}, title: {title}, slots: {DRILL}}}\n" for sid, title in [
        ("dl-line", "Line drill + legend"), ("dl-area", "Area drill + legend"),
        ("dl-stacked", "Stacked column drill + legend"), ("dl-stacked-100", "100% stacked drill + legend"),
        ("dl-stacked-bar", "Stacked bar drill + legend")]),
    "measures-legend.yaml": "page: Measures + Legend\nlayout: grid-2x3\nvisuals:\n"
    "  - {type: header, title: Two measures with a Legend; legend Bottom}\n"
    + "".join(f"  - {{type: column, id: {sid}, title: {title}, slots: {TWO}}}\n" for sid, title in [
        ("ml-stacked", "Stacked column measures + legend"), ("ml-stacked-100", "100% stacked measures + legend"),
        ("ml-stacked-bar", "Stacked bar measures + legend"), ("ml-area", "Area measures + legend"),
        ("legend-bottom", "Legend Bottom"), ("legend-default", "Legend default (theme Top)")]),
}

# spec id -> (visualType, Legend projection to add or None, visual.objects or None)
CANDIDATES = {
    "dl-line": ("lineChart", ORDER_DATE, None),
    "dl-area": ("areaChart", ORDER_DATE, None),
    "dl-stacked": ("columnChart", ORDER_DATE, None),
    "dl-stacked-100": ("hundredPercentStackedColumnChart", ORDER_DATE, None),
    "dl-stacked-bar": ("barChart", ORDER_DATE, None),
    "ml-stacked": ("columnChart", REGION, None),
    "ml-stacked-100": ("hundredPercentStackedColumnChart", REGION, None),
    "ml-stacked-bar": ("barChart", REGION, None),
    "ml-area": ("areaChart", REGION, None),
    "legend-bottom": ("clusteredColumnChart", None,
                      {"legend": [{"properties": {"position": {"expr": {"Literal": {"Value": "'Bottom'"}}}}}]}),
}

STEPS = """\
# Probe 28: Legend combinations and the 'Bottom' legend position

Blueprint built two pages and changed visuals to candidates. Claude opens the report through
the bridge, reloads and captures pages, and commits each step itself. Nothing for you to do
unless Claude asks.
"""


def make_candidates(report: Path) -> list[str]:
    changed = []
    for f in sorted(report.glob("definition/pages/*/visuals/*/visual.json")):
        doc = jsonfmt.load(f)
        sid = spec_id(doc)
        if sid not in CANDIDATES:
            continue
        vtype, legend, objects = CANDIDATES[sid]
        body = doc["visual"]
        body["visualType"] = vtype
        if legend:
            state = body["query"]["queryState"]
            state["Series"] = {"projections": [dict(legend)]}
            body["query"]["queryState"] = {role: state[role] for role in sorted(state)}  # alphabetical
        if objects:
            body["objects"] = objects
        f.write_bytes(jsonfmt.dump_bytes(doc))
        changed.append(f"{sid} -> {vtype}{' + Legend ' + legend['nativeQueryRef'] if legend else ''}"
                       f"{' + objects ' + ', '.join(objects) if objects else ''}")
    return changed


def theme_legend_top(report: Path) -> str:
    path = report / "StaticResources" / "RegisteredResources" / "blueprint-theme.json"
    theme = jsonfmt.load(path)
    styles = theme.setdefault("visualStyles", {}).setdefault("*", {}).setdefault("*", {})
    styles["legend"] = [{"position": "Top"}]
    path.write_bytes(jsonfmt.dump_bytes(theme))
    return f"{path.name}: visualStyles['*']['*'].legend = [{{position: Top}}]"


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    dest, cache = Path(sys.argv[1]), Path(sys.argv[2])
    make_probe(ROOT / "fixtures" / "02-card-and-chart", dest, STEPS, snap=True)
    tmdl = dest / "Fixture.SemanticModel" / "definition" / "tables" / "Sales.tmdl"
    text = tmdl.read_bytes().decode()
    text = text.replace("\tcolumn Country", MEASURE + "\tcolumn Country", 1)
    text = text.replace("\tpartition Sales = m", DATE_COLUMN + HIERARCHY + "\tpartition Sales = m", 1)
    tmdl.write_bytes(text.encode())
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "model: the demo's (Target Amount, Order Date, Geography)")

    specs = dest / "specs"
    specs.mkdir()
    guide = str(ROOT / "guidelines" / "example.yaml")
    for name, body in SPECS.items():
        (specs / name).write_text(body, encoding="utf-8")
    if bp(["apply", str(specs), "--report", str(dest), "--guidelines", guide]) != 0:
        sys.exit(1)
    if bp(["theme", "--report", str(dest), "--guidelines", guide]) != 0:
        sys.exit(1)
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "blueprint: apply specs/ (verified types) and bp theme")

    print("\n".join(make_candidates(dest / "Fixture.Report")))
    print(theme_legend_top(dest / "Fixture.Report"))
    if bp(["manifest", "--report", str(dest), "--guidelines", guide]) != 0:
        sys.exit(1)
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "probe: change visuals to the candidates; theme legend default Top")

    shutil.copy2(cache, dest / "Fixture.SemanticModel" / ".pbi" / "cache.abf")
    print(f"data cache copied from {cache}\nProbe ready: {dest}")
