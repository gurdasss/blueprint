"""`bp describe`: one read-only call that tells a spec writer (usually an LLM) what it can use."""

import json
import shutil
from pathlib import Path

from blueprint import guidelines, spec
from blueprint.cli import main
from blueprint.commands.describe import SPEC_SYNTAX, describe
from blueprint.slots import CORE_TYPES
from tests.builders import make_report

ROOT = Path(__file__).resolve().parent.parent
GUIDE = ROOT / "guidelines" / "example.yaml"


def _describe(capsys, *args) -> dict:
    assert main(["describe", "--guidelines", str(GUIDE), "--json", *args]) == 0
    return json.loads(capsys.readouterr().out)


def test_types_layouts_and_limits_without_a_report(capsys):
    d = _describe(capsys)
    # describe shows what a spec may use: the core, plus any contracts of the client's own
    assert sorted(d["types"]) == sorted(CORE_TYPES)  # the core, whatever it holds today
    assert d["types"]["kpi"] == {"visual_type": "kpi", "region": "kpi-row", "options": {}, "slots": {
        "value": {"accepts": ["measure"], "required": True, "list": False, "list_excludes": []},
        "trend": {"accepts": ["column"], "required": True, "list": False, "list_excludes": []},
        "target": {"accepts": ["measure"], "required": False, "list": False, "list_excludes": []}}}
    # A combination apply refuses is visible up front (several measures with a Legend, probe 28)
    assert d["types"]["line"]["slots"]["value"]["list_excludes"] == ["legend"]
    assert list(d["layouts"]) == ["dashboard-6", "grid-2x3", "kpi-row-plus-detail", "one-up", "standard-4-up", "two-up"]
    std = d["layouts"]["standard-4-up"]
    assert (std["default"], std["usable"], std["roles"]) == (True, True, {"header": 1, "kpi-row": 1, "main": 2})
    assert std["regions"][2] == {"key": "main#1", "role": "main", "x": 16, "y": 272, "w": 616, "h": 432}
    assert d["guidelines"]["canvas"] == {"width": 1280, "height": 720}
    assert d["guidelines"]["spacing"] == {"grid": 8, "margin": 16, "gutter": 16}
    assert d["guidelines"]["max_visuals"] == 6
    assert "model" not in d and "pages" not in d


def test_model_fields_are_written_in_spec_syntax(capsys, tmp_path: Path):
    shutil.copytree(ROOT / "fixtures" / "02-card-and-chart", tmp_path / "proj")
    d = _describe(capsys, "--report", str(tmp_path / "proj"))
    sales = d["model"]["tables"]["Sales"]
    assert {k: v for k, v in sales.items() if k != "fields"} == {
        "columns": ["Sales[Amount]", "Sales[Country]", "Sales[Region]"],
        "measures": ["[Total Amount]"], "hierarchies": {}, "hidden": []}
    assert (d["model"]["available"], d["model"]["hidden_tables"]) == (True, [])
    assert (d["model"]["relationships"], d["model"]["relationships_left_out"]) == ([], 0)
    for ref in [*d["model"]["tables"]["Sales"]["columns"], *d["model"]["tables"]["Sales"]["measures"]]:
        assert spec.parse_field(ref) is not None
    assert [(p["name"], p["spec"]) for p in d["pages"]] == [("Overview", None)]


def test_the_documented_example_spec_applies(tmp_path: Path, capsys):
    """And cleanly: an agent copies it, so it mustn't start with a warning (it once left
    standard-4-up's second main region empty)."""
    shutil.copytree(ROOT / "fixtures" / "02-card-and-chart", tmp_path / "proj")
    s = tmp_path / "example.yaml"
    s.write_text(SPEC_SYNTAX["example"])
    capsys.readouterr()
    assert main(["apply", str(s), "--report", str(tmp_path / "proj"), "--guidelines", str(GUIDE)]) == 0
    assert "Warnings:" not in capsys.readouterr().out


def test_spec_keys_documented_match_the_parser():
    assert set(SPEC_SYNTAX["page_keys"]) == spec._SPEC_KEYS
    assert set(SPEC_SYNTAX["visual_keys"]) == spec._VISUAL_KEYS


def test_unusable_layouts_are_flagged(tmp_path: Path):
    lay = tmp_path / "lay"
    lay.mkdir()
    (lay / "tight.yaml").write_text("name: tight\ncanvas: {width: 1280, height: 720}\nregions:\n"
                                    "  - {role: main, x: 16, y: 16, w: 600, h: 600}\n"
                                    "  - {role: main, x: 624, y: 16, w: 600, h: 600}\n")
    (lay / "broken.yaml").write_text("name: broken\n")
    g = tmp_path / "g.yaml"
    g.write_text("spacing: {gutter: 16}\nlayouts: {search_path: [lay]}\n")
    d = describe(guidelines.load(g), None)["layouts"]
    assert d["tight"]["usable"] is False
    assert d["tight"]["problems"] == ["regions main#1 and main#2 are 8px apart, less than the 16px gutter"]
    assert d["broken"]["usable"] is False and "problem" in d["broken"]["problems"][0]


def test_report_without_a_local_model_still_describes(capsys, tmp_path: Path):
    rd = make_report(tmp_path / "r", {"p": []})
    d = _describe(capsys, "--report", str(rd))
    assert d["model"]["available"] is False and d["model"]["tables"] == {}
    assert main(["describe", "--report", str(rd)]) == 0
    assert "Model fields\n  not available:" in capsys.readouterr().out


def test_text_output(capsys, tmp_path: Path):
    shutil.copytree(ROOT / "fixtures" / "02-card-and-chart", tmp_path / "proj")
    assert main(["describe", "--report", str(tmp_path / "proj"), "--guidelines", str(GUIDE)]) == 0
    out = capsys.readouterr().out
    assert ("  kpi                region kpi-row  value*: measure, trend*: column, "
            "target: measure\n") in out
    # every probe-verified type is core, so a plain run lists them all
    assert ("  area               region main     category*[]: column, value*[]: measure"
            in out)
    # a client's own type needs an opt-in, and then it is listed too
    mine = tmp_path / "my-visuals"
    mine.mkdir()
    (mine / "gauge.yaml").write_text(
        "type: gauge\nvisual_type: gaugeChart\nregion: main\n"
        "slots:\n  value: { role: Y, accepts: measure, required: true }\n")
    assert "  gauge" not in out
    assert main(["describe", "--report", str(tmp_path / "proj"), "--guidelines", str(GUIDE),
                 "--visuals", str(mine)]) == 0
    assert "  gauge              region main     value*: measure" in capsys.readouterr().out
    assert "  standard-4-up (default): 1280x720; 1 header, 1 kpi-row, 2 main" in out
    assert "    measures: [Total Amount]" in out
    assert "  Overview  (1920x1080; not built by a spec)" in out


def _model_report(tmp_path: Path) -> Path:
    """A report whose model has a sorted month column, a measure, a hidden auto-date table and
    relationships to both a visible table and the auto-date one."""
    from tests.test_semantic import PROPS_TMDL
    rd = make_report(tmp_path / "r", {"p": []})
    defn = tmp_path / "r" / "M" / "definition"
    (defn / "tables").mkdir(parents=True)
    (defn / "tables" / "Calendar.tmdl").write_text(PROPS_TMDL)
    (defn / "tables" / "Sales.tmdl").write_text("table Sales\n\tcolumn 'Order Date'\n\t\tdataType: dateTime\n"
                                                "\tcolumn Date\n")
    (defn / "tables" / "LocalDateTable_1.tmdl").write_text("table LocalDateTable_1\n\tisHidden\n\n\tcolumn Date\n")
    (defn / "relationships.tmdl").write_text(
        "relationship r1\n\tfromColumn: Sales.'Order Date'\n\ttoColumn: Calendar.Month\n\n"
        "relationship r2\n\tjoinOnDateBehavior: datePartOnly\n"
        "\tfromColumn: Sales.Date\n\ttoColumn: LocalDateTable_1.Date\n")
    (rd / "definition.pbir").write_text(json.dumps(
        {"version": "4.0", "datasetReference": {"byPath": {"path": "../M"}}}))
    return rd


def test_field_details_say_null_when_the_model_writes_nothing(capsys, tmp_path: Path):
    """Every field has every key: null means "checked, there is none", so an agent doesn't
    guess. A sorted column names its sort column in spec syntax (months show as names)."""
    m = _describe(capsys, "--report", str(_model_report(tmp_path)), "--section", "model")["model"]
    fields = m["tables"]["Calendar"]["fields"]
    keys = {"kind", "hidden", "data_type", "sort_by", "summarize_by", "format_string"}
    assert all(set(f) == keys for t in m["tables"].values() for f in t["fields"].values())
    assert fields["Calendar[Month]"] == {"kind": "column", "hidden": False, "data_type": "string",
                                         "sort_by": "Calendar[Month Number]", "summarize_by": "none",
                                         "format_string": None}
    assert fields["Calendar[Plain]"] == {"kind": "column", "hidden": False, "data_type": None,
                                         "sort_by": None, "summarize_by": None, "format_string": None}
    assert fields["[Sales LY]"]["kind"] == "measure"
    assert fields["[Sales LY]"]["format_string"] == "\\$#,0;(\\$#,0);\\$#,0"
    assert m["relationships"] == [{"from": "Sales[Order Date]", "to": "Calendar[Month]", "properties": {}}]
    assert m["relationships_left_out"] == 1  # the one to the hidden auto-date table


def test_section_keeps_only_the_named_parts(capsys, tmp_path: Path):
    rd = str(_model_report(tmp_path))
    assert list(_describe(capsys, "--section", "types")) == ["types"]
    assert list(_describe(capsys, "--report", rd, "--section", "model", "--section", "pages")) == [
        "model", "pages"]
    assert list(_describe(capsys, "--report", rd)) == [
        "spec", "guidelines", "types", "layouts", "model", "pages"]  # no --section: everything
    assert main(["describe", "--guidelines", str(GUIDE), "--section", "layouts"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("Layouts") and "Visual types" not in out and "Guidelines:" not in out
    assert main(["describe", "--report", rd, "--guidelines", str(GUIDE), "--section", "model"]) == 0
    assert "Calendar[Month] sorts by Calendar[Month Number]" in capsys.readouterr().out


def test_a_report_section_without_a_report_is_a_clear_error(capsys):
    assert main(["describe", "--guidelines", str(GUIDE), "--section", "model"]) == 2
    assert "--section model needs --report" in capsys.readouterr().err
