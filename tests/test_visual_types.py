"""Pie, table and KPI (probe 08): `bp apply` writes the query shapes Desktop wrote for them."""

import shutil
from pathlib import Path

from blueprint import guidelines
from blueprint.cli import main
from blueprint.pbir import jsonfmt
from blueprint.pbir.reader import read_report
from blueprint.slots import contracts
from blueprint.validate import check_report

ROOT = Path(__file__).resolve().parent.parent
GUIDE = ROOT / "guidelines" / "example.yaml"

SPEC = """\
page: Mix
layout: standard-4-up
visuals:
  - type: kpi
    title: Trend
    slots: {value: "[Total Amount]", trend: "Sales[Country]"}
  - type: pie
    title: Share
    slots: {category: "Sales[Region]", value: "[Total Amount]"}
  - type: table
    title: Detail
    slots: {columns: ["Sales[Country]", "Sales[Region]", "[Total Amount]"]}
"""


def col(name: str, active: bool = False) -> dict:
    p = {"field": {"Column": {"Expression": {"SourceRef": {"Entity": "Sales"}}, "Property": name}},
         "queryRef": f"Sales.{name}", "nativeQueryRef": name}
    return {**p, "active": True} if active else p


MEASURE = {"field": {"Measure": {"Expression": {"SourceRef": {"Entity": "Sales"}}, "Property": "Total Amount"}},
           "queryRef": "Sales.Total Amount", "nativeQueryRef": "Total Amount"}

# queryState exactly as Desktop wrote it in probe 08 (docs/probes/08-pie-table-kpi.diff; the table
# after step 06's reorder). Desktop's own extras (sortDefinition, drillFilterOtherVisuals) are left
# out, as for every type (probe 05).
DESKTOP = {
    "pieChart": {"Category": {"projections": [col("Region", active=True)]}, "Y": {"projections": [MEASURE]}},
    "tableEx": {"Values": {"projections": [col("Country"), col("Region"), MEASURE]}},
    "kpi": {"Indicator": {"projections": [MEASURE]}, "TrendLine": {"projections": [col("Country")]}},
}


def test_contracts_ship_the_probed_types():
    c = contracts()
    assert (c["pie"].visual_type, c["table"].visual_type, c["kpi"].visual_type) == ("pieChart", "tableEx", "kpi")
    assert c["table"].slots["columns"].accepts == ("column", "measure")


def test_apply_writes_desktops_query_shapes(tmp_path: Path):
    shutil.copytree(ROOT / "fixtures" / "02-card-and-chart", tmp_path / "proj")
    report = tmp_path / "proj" / "Fixture.Report"
    spec = tmp_path / "mix.yaml"
    spec.write_text(SPEC)
    assert main(["apply", str(spec), "--report", str(report), "--guidelines", str(GUIDE)]) == 0

    made = {}
    for f in report.glob("definition/pages/*/visuals/*/visual.json"):
        doc = jsonfmt.load(f)
        if any(a.get("name") == "blueprint.visual" for a in doc.get("annotations", [])):
            made[doc["visual"]["visualType"]] = doc
    assert set(made) == set(DESKTOP)
    for vtype, doc in made.items():
        assert doc["visual"]["query"]["queryState"] == DESKTOP[vtype], vtype
    # kpi fills the kpi-row region; pie and table take the two main regions in spec order.
    pos = {t: (d["position"]["x"], d["position"]["y"]) for t, d in made.items()}
    assert pos == {"kpi": (16, 96), "pieChart": (16, 232), "tableEx": (648, 232)}

    # bp check passes what apply built (the fixture's hand-made page and base theme have findings).
    names = {d["name"] for d in made.values()}
    findings = check_report(read_report(report), guidelines.load(GUIDE)).findings
    assert [f for f in findings if f.visual in names] == []
