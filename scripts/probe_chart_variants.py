"""Build the Desktop probe for candidate chart variants and the Dropdown slicer (probe 22).

Usage:
    python scripts/probe_chart_variants.py <dest folder> [<probe with a data cache>]

Unlike a shape probe (the user builds visuals in Desktop and Desktop writes the JSON), this one
writes **candidate** shapes and asks whether Desktop takes them: `bp apply` builds a page of
verified types, then each visual is changed to the variant under test, keeping the query shape
that verified sibling uses:

- stacked column `columnChart`, 100% stacked column `hundredPercentStackedColumnChart` and
  stacked bar `barChart`: the clustered chart's roles plus a Legend (`Series` = Region);
- donut `donutChart`: the pie's roles;
- area `areaChart`: the line chart's roles, with a Legend;
- the slicer with `objects.data[0].properties.mode = 'Dropdown'` (as Desktop wrote it, probe 20).

Desktop's open, render and save are the evidence: a variant counts as verified only if it draws
and Desktop's save leaves its query alone (or the diff shows what Desktop wants instead).
`Target Amount` is added as in probe 20. If a second argument names an earlier probe of the same
model, its `.pbi/cache.abf` is copied in so the report opens with data (no Refresh needed).
All content is invented.
"""

import shutil
import sys
from pathlib import Path

from _probe import git, make_probe
from probe_apply_slicer_matrix import MEASURE

from blueprint.cli import main as bp
from blueprint.pbir import jsonfmt

ROOT = Path(__file__).resolve().parent.parent

SPEC = """\
page: Variants
layout: grid-2x3
visuals:
  - {type: header, title: Variants}
  - {type: column, id: stacked-column, title: Stacked column, slots: {category: "Sales[Country]", value: "[Total Amount]"}}
  - {type: column, id: stacked-column-100, title: 100% stacked column, slots: {category: "Sales[Country]", value: "[Total Amount]"}}
  - {type: bar, id: stacked-bar, title: Stacked bar, slots: {category: "Sales[Country]", value: "[Total Amount]"}}
  - {type: pie, id: donut, title: Donut, slots: {category: "Sales[Region]", value: "[Total Amount]"}}
  - {type: line, id: area, title: Area, slots: {category: "Sales[Country]", value: "[Total Amount]", legend: "Sales[Region]"}}
  - {type: slicer, id: dropdown, title: Dropdown slicer, slots: {field: "Sales[Country]"}}
"""

# spec visual id -> (candidate visualType, add a Legend (Series = Region)?, extra visual.objects)
CANDIDATES = {
    "stacked-column": ("columnChart", True, None),
    "stacked-column-100": ("hundredPercentStackedColumnChart", True, None),
    "stacked-bar": ("barChart", True, None),
    "donut": ("donutChart", False, None),
    "area": ("areaChart", False, None),
    "dropdown": ("slicer", False, {"data": [{"properties": {"mode": {"expr": {"Literal": {"Value": "'Dropdown'"}}}}}]}),
}

# A Legend column as the line chart's Series is written (probe 12): no "active".
REGION = {"field": {"Column": {"Expression": {"SourceRef": {"Entity": "Sales"}}, "Property": "Region"}},
          "queryRef": "Sales.Region", "nativeQueryRef": "Region"}

STEPS = """\
# Probe 22: does Desktop take these chart variants and the Dropdown slicer?

Blueprint built the page **Variants** and then changed each visual to a candidate: stacked
column, 100% stacked column and stacked bar (with Region as Legend), donut, area, and a Dropdown
slicer. Claude drives Desktop through the bridge; you only need to:

1. In Desktop (this report open, page **Variants**), note any error dialog, then **Ctrl+S**.

Claude commits each step itself. Never click a value inside the slicer.
"""


def spec_id(doc: dict) -> str | None:
    return next((a["value"] for a in doc.get("annotations", []) if a.get("name") == "blueprint.visual"), None)


def make_candidates(report: Path, candidates: dict | None = None) -> list[str]:
    """Change each visual whose spec id is in ``candidates`` (default: this probe's CANDIDATES):
    spec id -> (visualType, add a Legend (Series = Region)?, visual.objects to set or None)."""
    candidates = CANDIDATES if candidates is None else candidates
    changed = []
    for f in sorted(report.glob("definition/pages/*/visuals/*/visual.json")):
        doc = jsonfmt.load(f)
        sid = spec_id(doc)
        if sid not in candidates:
            continue
        vtype, legend, objects = candidates[sid]
        body = doc["visual"]
        body["visualType"] = vtype
        if legend:
            state = body["query"]["queryState"]
            state["Series"] = {"projections": [dict(REGION)]}
            body["query"]["queryState"] = {role: state[role] for role in sorted(state)}  # alphabetical
        if objects:
            body["objects"] = objects
        f.write_bytes(jsonfmt.dump_bytes(doc))
        changed.append(f"{sid} -> {vtype}{' + Legend Region' if legend else ''}{' + objects ' + ', '.join(objects) if objects else ''}")
    return changed


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
    (specs / "variants.yaml").write_text(SPEC, encoding="utf-8")
    guide = str(ROOT / "guidelines" / "example.yaml")
    if bp(["apply", str(specs / "variants.yaml"), "--report", str(dest), "--guidelines", guide]) != 0:
        sys.exit(1)
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "blueprint: apply specs/variants.yaml (verified types)")

    print("\n".join(make_candidates(dest / "Fixture.Report")))
    if bp(["manifest", "--report", str(dest), "--guidelines", guide]) != 0:
        sys.exit(1)
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "probe: change visuals to the candidate variants")

    if len(sys.argv) == 3:  # data, so the report opens without Refresh (.pbi is gitignored)
        cache = Path(sys.argv[2]) / "Fixture.SemanticModel" / ".pbi" / "cache.abf"
        shutil.copy2(cache, dest / "Fixture.SemanticModel" / ".pbi" / "cache.abf")
        print(f"data cache copied from {cache}")
    print(f"Probe ready: {dest}")
