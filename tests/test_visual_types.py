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

SPEC = ROOT / "examples" / "sales-mix.yaml"


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
    assert main(["apply", str(SPEC), "--report", str(report), "--guidelines", str(GUIDE)]) == 0

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


def _fixture_with_target(tmp_path: Path) -> Path:
    """Fixture 02 plus the measure probe 10 created in Desktop, inserted where Desktop put it."""
    shutil.copytree(ROOT / "fixtures" / "02-card-and-chart", tmp_path / "proj")
    tmdl = tmp_path / "proj" / "Fixture.SemanticModel" / "definition" / "tables" / "Sales.tmdl"
    text = tmdl.read_bytes().decode()
    measure = ("\tmeasure 'Target Amount' = 600\r\n\t\tformatString: 0\r\n"
               "\t\tlineageTag: 9ab090f9-bd7f-43c4-82be-86470a46784b\r\n\r\n")
    tmdl.write_bytes(text.replace("\tcolumn Country", measure + "\tcolumn Country", 1).encode())
    return tmp_path / "proj" / "Fixture.Report"


def _made(report: Path) -> dict[str, dict]:
    out = {}
    for f in report.glob("definition/pages/*/visuals/*/visual.json"):
        doc = jsonfmt.load(f)
        if any(a.get("name") == "blueprint.visual" for a in doc.get("annotations", [])):
            out[doc["visual"]["visualType"]] = doc
    return out


def test_kpi_target_matches_probe_10(tmp_path: Path):
    report = _fixture_with_target(tmp_path)
    spec = tmp_path / "kpi-target.yaml"
    spec.write_text('page: K\nlayout: standard-4-up\nvisuals:\n  - type: kpi\n    title: T\n'
                    '    slots: {value: "[Total Amount]", trend: "Sales[Country]", target: "[Target Amount]"}\n')
    assert main(["apply", str(spec), "--report", str(report), "--guidelines", str(GUIDE)]) == 0
    state = _made(report)["kpi"]["visual"]["query"]["queryState"]
    target = {**MEASURE, "field": {"Measure": {"Expression": {"SourceRef": {"Entity": "Sales"}},
                                               "Property": "Target Amount"}},
              "queryRef": "Sales.Target Amount", "nativeQueryRef": "Target Amount"}
    # Desktop's queryState from probe 10 step 03, in its order: roles sorted, not in well order.
    assert list(state.items()) == [("Goal", {"projections": [target]}),
                                   ("Indicator", {"projections": [MEASURE]}),
                                   ("TrendLine", {"projections": [col("Country")]})]


def test_roles_are_written_in_alphabetical_order_whatever_the_spec_order(tmp_path: Path):
    shutil.copytree(ROOT / "fixtures" / "02-card-and-chart", tmp_path / "proj")
    report = tmp_path / "proj" / "Fixture.Report"
    spec = tmp_path / "order.yaml"
    spec.write_text('page: O\nlayout: standard-4-up\nvisuals:\n  - type: column\n    title: C\n'
                    '    slots: {value: "[Total Amount]", category: "Sales[Region]"}\n')
    assert main(["apply", str(spec), "--report", str(report), "--guidelines", str(GUIDE)]) == 0
    assert list(_made(report)["clusteredColumnChart"]["visual"]["query"]["queryState"]) == ["Category", "Y"]


def test_target_takes_a_measure_not_a_column(tmp_path: Path):
    report = _fixture_with_target(tmp_path)
    spec = tmp_path / "bad.yaml"
    spec.write_text('page: B\nvisuals:\n  - type: kpi\n'
                    '    slots: {value: "[Total Amount]", trend: "Sales[Country]", target: "Sales[Amount]"}\n')
    assert main(["apply", str(spec), "--report", str(report), "--guidelines", str(GUIDE)]) != 0


def test_reapply_refuses_a_target_swapped_for_a_column_in_desktop(tmp_path: Path, capsys):
    report = _fixture_with_target(tmp_path)
    spec = tmp_path / "kpi-target.yaml"
    spec.write_text('page: K\nlayout: standard-4-up\nvisuals:\n  - type: kpi\n    title: T\n'
                    '    slots: {value: "[Total Amount]", trend: "Sales[Country]", target: "[Target Amount]"}\n')
    args = ["apply", str(spec), "--report", str(report), "--guidelines", str(GUIDE)]
    assert main(args) == 0
    # probe 10 step 04, done to Blueprint's KPI: Target becomes "Sum of Amount"
    path = next(f for f in report.glob("definition/pages/*/visuals/*/visual.json")
                if jsonfmt.load(f)["visual"]["visualType"] == "kpi")
    doc = jsonfmt.load(path)
    doc["visual"]["query"]["queryState"]["Goal"]["projections"] = [{
        "field": {"Aggregation": {"Expression": {"Column": {"Expression": {"SourceRef": {"Entity": "Sales"}},
                                                            "Property": "Amount"}}, "Function": 0}},
        "queryRef": "Sum(Sales.Amount)", "nativeQueryRef": "Sum of Amount"}]
    path.write_bytes(jsonfmt.dump_bytes(doc))
    capsys.readouterr()
    assert main(args) != 0
    assert "field bindings differ" in capsys.readouterr().err
    assert main(["manifest", "--report", str(report)]) == 0
    manifest = jsonfmt.load(report / ".blueprint.manifest.json")
    [kpi] = [v for p in manifest["pages"] for v in p["visuals"] if v["visual_type"] == "kpi"]
    assert kpi["slots"]["target"] == "Sum(Sales[Amount])"
