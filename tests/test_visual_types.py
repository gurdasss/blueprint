"""Pie, table and KPI (probe 08): `bp apply` writes the query shapes Desktop wrote for them.

pie is archived out of the core seven, so these tests opt it back in the way a client would.
"""

import json
import shutil
from pathlib import Path

import pytest
import yaml

from blueprint import guidelines
from blueprint.cli import main
from blueprint.pbir import jsonfmt
from blueprint.pbir.reader import read_report
from blueprint.slots import ContractError, contracts
from blueprint.validate import check_report

ROOT = Path(__file__).resolve().parent.parent
GUIDE = ROOT / "guidelines" / "example.yaml"

# What examples/sales-mix.yaml held when pie was core: probe 08's three types on one page.
SPEC_TEXT = """\
page: Sales Mix
layout: standard-4-up
visuals:
  - type: kpi
    title: Total by Country
    slots: {value: "[Total Amount]", trend: "Sales[Country]"}
  - type: pie
    title: Share by Region
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


def test_the_core_ships_every_probe_verified_type():
    """Types move into the core as their Desktop evidence is confirmed; what is left in the
    archive still needs an opt-in. `slicer` and `matrix` came first (probe 20 recorded the shapes,
    probe 21 showed Desktop accepts what `bp apply` writes), then `pie` and `donut` (probes 08 and
    11 for the shapes and the Legend drill-down, 22-24 for the rest and Desktop's save)."""
    assert sorted(contracts()) == [
        "area", "bar", "card", "column", "donut", "header", "kpi", "line", "matrix", "pie",
        "slicer", "stacked-bar", "stacked-column", "stacked-column-100", "table"]


def test_contracts_ship_the_probed_types():
    c = contracts()
    assert (c["pie"].visual_type, c["table"].visual_type, c["kpi"].visual_type) == ("pieChart", "tableEx", "kpi")
    assert c["table"].slots["columns"].accepts == ("column", "measure", "hierarchy")


def test_apply_writes_desktops_query_shapes(tmp_path: Path):
    shutil.copytree(ROOT / "fixtures" / "02-card-and-chart", tmp_path / "proj")
    report = tmp_path / "proj" / "Fixture.Report"
    spec_path = tmp_path / "sales-mix.yaml"
    spec_path.write_text(SPEC_TEXT)
    assert main(["apply", str(spec_path), "--report", str(report), "--guidelines", str(GUIDE)]) == 0

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
    assert pos == {"kpi": (16, 96), "pieChart": (16, 272), "tableEx": (648, 272)}

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
    """A Desktop edit to a Blueprint visual's fields is refused, not silently undone (its
    blueprint.bindings fingerprint no longer matches); --overwrite-edits puts the spec back."""
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
    err = capsys.readouterr().err
    assert "its fields were changed in Desktop since Blueprint wrote them" in err
    assert main(["manifest", "--report", str(report)]) == 0
    manifest = jsonfmt.load(report / ".blueprint.manifest.json")
    [kpi] = [v for p in manifest["pages"] for v in p["visuals"] if v["visual_type"] == "kpi"]
    assert kpi["slots"]["target"] == "Sum(Sales[Amount])"
    capsys.readouterr()
    assert main([*args, "--overwrite-edits"]) == 0
    assert "rebind" in capsys.readouterr().out
    assert jsonfmt.load(path)["visual"]["query"]["queryState"]["Goal"]["projections"][0]["field"] == {
        "Measure": {"Expression": {"SourceRef": {"Entity": "Sales"}}, "Property": "Target Amount"}}
    capsys.readouterr()
    assert main(args) == 0 and capsys.readouterr().out.startswith("No changes.")


def test_pie_drill_down_and_details_match_probe_11(tmp_path: Path):
    shutil.copytree(ROOT / "fixtures" / "02-card-and-chart", tmp_path / "proj")
    report = tmp_path / "proj" / "Fixture.Report"
    spec = tmp_path / "pie.yaml"
    spec.write_text('page: P\nlayout: standard-4-up\nvisuals:\n'
                    '  - type: pie\n    title: Drill\n'
                    '    slots: {category: ["Sales[Country]", "Sales[Region]"], value: "[Total Amount]"}\n'
                    '  - type: pie\n    title: Split\n'
                    '    slots: {category: "Sales[Country]", details: "Sales[Region]", value: "[Total Amount]"}\n')
    assert main(["apply", str(spec), "--report", str(report), "--guidelines", str(GUIDE)]) == 0
    pies = {}
    for f in report.glob("definition/pages/*/visuals/*/visual.json"):
        doc = jsonfmt.load(f)
        if doc["visual"]["visualType"] == "pieChart":
            pies[doc["visual"]["visualContainerObjects"]["title"][0]["properties"]["text"]["expr"]["Literal"]["Value"]] = doc
    # probe 11 step 02: an ordered drill-down in Category. Every level active, as in Desktop's own
    # column chart (fixture 02), which Desktop accepted from Blueprint in probe 05.
    assert pies["'Drill'"]["visual"]["query"]["queryState"] == {
        "Category": {"projections": [col("Country", active=True), col("Region", active=True)]},
        "Y": {"projections": [MEASURE]}}
    # probe 11 step 04: Details is role Series, with no "active", and roles in alphabetical order.
    state = pies["'Split'"]["visual"]["query"]["queryState"]
    assert list(state.items()) == [("Category", {"projections": [col("Country", active=True)]}),
                                   ("Series", {"projections": [col("Region")]}),
                                   ("Y", {"projections": [MEASURE]})]


def test_line_and_bar_match_probe_12(tmp_path: Path):
    shutil.copytree(ROOT / "fixtures" / "02-card-and-chart", tmp_path / "proj")
    report = tmp_path / "proj" / "Fixture.Report"
    spec = tmp_path / "charts.yaml"
    spec.write_text('page: C\nlayout: standard-4-up\nvisuals:\n'
                    '  - type: line\n    title: Line\n'
                    '    slots: {category: "Sales[Country]", value: "[Total Amount]", legend: "Sales[Region]"}\n'
                    '  - type: bar\n    title: Bar\n'
                    '    slots: {category: ["Sales[Country]", "Sales[Region]"], value: "[Total Amount]"}\n')
    assert main(["apply", str(spec), "--report", str(report), "--guidelines", str(GUIDE)]) == 0
    made = _made(report)
    # probe 12 step 05 (line with Legend) and step 04 (bar drill-down), roles in Desktop's order
    assert list(made["lineChart"]["visual"]["query"]["queryState"].items()) == [
        ("Category", {"projections": [col("Country", active=True)]}),
        ("Series", {"projections": [col("Region")]}),
        ("Y", {"projections": [MEASURE]})]
    assert made["clusteredBarChart"]["visual"]["query"]["queryState"] == {
        "Category": {"projections": [col("Country", active=True), col("Region", active=True)]},
        "Y": {"projections": [MEASURE]}}



# --- inherits: (template/visuals.md) -------------------------------------------------------

def _dir(tmp_path: Path, **files: str) -> tuple[Path, ...]:
    """A directory of contract YAMLs, as a client's extensions.custom_visuals.search_path."""
    d = tmp_path / "my-visuals"
    d.mkdir(exist_ok=True)
    for name, text in files.items():
        (d / f"{name}.yaml").write_text(text)
    return (d,)


def test_inherits_copies_slots_options_and_region(tmp_path: Path):
    """The documented behaviour: slots, options and region come from the parent; the child
    declares its own type and visual_type."""
    extra = _dir(tmp_path, waterfall="type: waterfall\nvisual_type: waterfallChart\n"
                                     "inherits: column\n")
    c = contracts(extra)["waterfall"]
    parent = contracts()["column"]
    assert (c.type, c.visual_type) == ("waterfall", "waterfallChart")
    assert (c.slots, c.options, c.region) == (parent.slots, parent.options, parent.region)


def test_a_child_overrides_slot_by_slot_and_adds_its_own(tmp_path: Path):
    extra = _dir(tmp_path, trend="""\
type: trend
visual_type: trendChart
inherits: column
region: kpi-row
slots:
  value: { role: Y, accepts: measure, required: true }   # no longer a list
  legend: { role: Series, accepts: column }              # restated (column has one since probe 32)
options: {}                                              # this type has none
""")
    c = contracts(extra)["trend"]
    assert c.region == "kpi-row"
    assert list(c.slots) == ["category", "value", "legend"]          # parent's first, then new
    assert c.slots["category"] == contracts()["column"].slots["category"]  # untouched
    assert c.slots["value"].ordered is False                          # overridden
    # a section the child writes as empty is empty: a client's file is followed to the letter,
    # and an inherited option it can't drop would be a guess about its own visual
    assert c.options == {} and contracts()["column"].options


def test_inherits_chains(tmp_path: Path):
    extra = _dir(tmp_path,
                 mid="type: mid\nvisual_type: midChart\ninherits: column\nregion: kpi-row\n",
                 leaf="type: leaf\nvisual_type: leafChart\ninherits: mid\n")
    c = contracts(extra)["leaf"]
    assert (c.region, list(c.slots)) == ("kpi-row", ["category", "value", "legend"])


def test_type_and_visual_type_are_never_inherited(tmp_path: Path):
    extra = _dir(tmp_path, clone="type: clone\ninherits: column\n")
    with pytest.raises(ContractError, match="visual_type is never inherited"):
        contracts(extra)


def test_a_cycle_is_refused(tmp_path: Path):
    extra = _dir(tmp_path,
                 a="type: a\nvisual_type: aChart\ninherits: b\n",
                 b="type: b\nvisual_type: bChart\ninherits: a\n")
    with pytest.raises(ContractError, match="inherits is a cycle"):
        contracts(extra)


def test_inheriting_itself_is_refused(tmp_path: Path):
    extra = _dir(tmp_path, me="type: me\nvisual_type: meChart\ninherits: me\n")
    with pytest.raises(ContractError, match="inherits is a cycle"):
        contracts(extra)


def test_an_unknown_parent_names_what_is_loaded(tmp_path: Path):
    extra = _dir(tmp_path, odd="type: odd\nvisual_type: oddChart\ninherits: gauge\n")
    with pytest.raises(ContractError, match="inherits unknown type 'gauge' .*loaded: area"):
        contracts(extra)


def test_two_types_may_not_claim_one_pbir_visual(tmp_path: Path):
    """The manifest and the probe replays key by visual_type, so a duplicate would shadow."""
    extra = _dir(tmp_path, twin="type: twin\nvisual_type: clusteredColumnChart\n"
                                "inherits: column\n")
    with pytest.raises(ContractError, match="'clusteredColumnChart' is claimed by both"):
        contracts(extra)


def test_a_duplicate_type_name_is_refused(tmp_path: Path):
    extra = _dir(tmp_path, column="type: column\nvisual_type: other\nregion: main\n")
    with pytest.raises(ContractError, match="visual type 'column' is defined twice"):
        contracts(extra)


def test_a_core_contract_can_be_a_parent_of_a_clients_own_type(tmp_path: Path):
    """A client's own type, in its own directory, may inherit a core one."""
    extra = _dir(tmp_path, ring="type: ring\nvisual_type: ringChart\ninherits: donut\n")
    c = contracts(extra)["ring"]
    assert list(c.slots) == list(contracts()["donut"].slots)


def test_bar_inherits_column_now_that_a_probe_covers_its_options():
    """Why this took a probe rather than an edit: bar's slots were always column's, but `options`
    are not slots. Probe 23 verified data labels and legend position on the column and stacked
    charts, never on the clustered bar, so inheriting them would have shipped a guess. Probe 31
    wrote them onto a bar, Desktop drew and kept them, and only then did the two become the same
    contract apart from the PBIR type."""
    core = contracts()
    bar, column = core["bar"], core["column"]
    assert (bar.slots, bar.options, bar.region) == (column.slots, column.options, column.region)
    assert (bar.visual_type, column.visual_type) == ("clusteredBarChart", "clusteredColumnChart")
    raw = yaml.safe_load((ROOT / "blueprint" / "visuals" / "bar.yaml").read_text())
    assert raw["inherits"] == "column" and "slots" not in raw and "options" not in raw


def test_line_states_its_own_slots_because_it_differs():
    """line adds a legend slot and excludes a measure list beside it (probes 27, 28), so it says
    so itself rather than inheriting and restating most of what it overrides."""
    line = contracts()["line"]
    assert "legend" in line.slots and line.slots["value"].list_excludes == ("legend",)


# --- the opt-in has to reach every command that touches the manifest -----------------------

PIE_SPEC = """\
page: Pie Page
layout: standard-4-up
visuals:
  - {type: header, title: Pie Page}
  - {type: pie, title: Share, slots: {category: "Sales[Region]", value: "[Total Amount]"}}
"""


def _pie_entry(report: Path) -> dict:
    data = json.loads((report / ".blueprint.manifest.json").read_text(encoding="utf-8"))
    return next(v for p in data["pages"] for v in p["visuals"]
                if v.get("type") in ("pie", "pieChart"))


def _report_with_a_pie(tmp_path: Path) -> Path:
    shutil.copytree(ROOT / "fixtures" / "02-card-and-chart", tmp_path / "proj")
    report = tmp_path / "proj" / "Fixture.Report"
    spec = tmp_path / "pie.yaml"
    spec.write_text(PIE_SPEC)
    assert main(["apply", str(spec), "--report", str(report), "--guidelines", str(GUIDE)]) == 0
    assert _pie_entry(report)["type"] == "pie"
    return report


def test_fmt_keeps_the_manifests_spec_types(tmp_path: Path):
    """The manifest is built from contracts: for a type no contract describes, `bp fmt` rewrites
    the entry as its PBIR type with raw query roles ("pieChart", Category/Y) and `bp check` then
    calls the manifest stale. Every probe-verified type is core now, so a plain run keeps them."""
    report = _report_with_a_pie(tmp_path)
    assert main(["fmt", "--report", str(report), "--guidelines", str(GUIDE)]) == 0
    entry = _pie_entry(report)
    assert (entry["type"], list(entry["slots"])) == ("pie", ["category", "value"])


def test_the_flag_adds_to_the_guidelines_opt_in_instead_of_replacing_it(tmp_path: Path):
    """`merge()` replaces a list, so a plain override layer would drop the report's own
    search_path and turn its pages into "unknown type"."""
    mine = tmp_path / "mine"
    mine.mkdir()
    (mine / "ring.yaml").write_text("type: ring\nvisual_type: ringChart\ninherits: donut\n")
    theirs = tmp_path / "theirs"
    theirs.mkdir()
    (theirs / "gauge.yaml").write_text(
        "type: gauge\nvisual_type: gaugeChart\nregion: main\n"
        "slots:\n  value: { role: Y, accepts: measure, required: true }\n")
    g = tmp_path / "g.yaml"
    g.write_text(f'extensions:\n  custom_visuals:\n    search_path: ["{theirs}"]\n')
    rules = guidelines.load(g, visuals=[mine])
    assert set(rules.visuals) == {theirs, mine}
    assert {"gauge", "ring"} <= set(contracts(rules.visuals))  # both reachable
