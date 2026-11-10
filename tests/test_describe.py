"""`bp describe`: one read-only call that tells a spec writer (usually an LLM) what it can use."""

import json
import shutil
from pathlib import Path

from blueprint import guidelines, spec
from blueprint.cli import main
from blueprint.commands.describe import SPEC_SYNTAX, describe
from blueprint.slots import contracts
from tests.builders import make_report

ROOT = Path(__file__).resolve().parent.parent
GUIDE = ROOT / "guidelines" / "example.yaml"


def _describe(capsys, *args) -> dict:
    assert main(["describe", "--guidelines", str(GUIDE), "--json", *args]) == 0
    return json.loads(capsys.readouterr().out)


def test_types_layouts_and_limits_without_a_report(capsys):
    d = _describe(capsys)
    assert set(d["types"]) == set(contracts())
    assert d["types"]["kpi"] == {"visual_type": "kpi", "region": "kpi-row", "options": {}, "slots": {
        "value": {"accepts": ["measure"], "required": True, "list": False},
        "trend": {"accepts": ["column"], "required": True, "list": False},
        "target": {"accepts": ["measure"], "required": False, "list": False}}}
    assert d["types"]["slicer"]["options"] == {"style": ["dropdown"]}
    assert list(d["layouts"]) == ["dashboard-6", "grid-2x3", "kpi-row-plus-detail", "one-up", "standard-4-up", "two-up"]
    std = d["layouts"]["standard-4-up"]
    assert (std["default"], std["usable"], std["roles"]) == (True, True, {"header": 1, "kpi-row": 1, "main": 2})
    assert std["regions"][2] == {"key": "main#1", "role": "main", "x": 16, "y": 272, "w": 616, "h": 432}
    assert d["guidelines"]["canvas"] == {"width": 1280, "height": 720, "margin": 16, "gutter": 16}
    assert d["guidelines"]["max_visuals"] == 6
    assert "model" not in d and "pages" not in d


def test_model_fields_are_written_in_spec_syntax(capsys, tmp_path: Path):
    shutil.copytree(ROOT / "fixtures" / "02-card-and-chart", tmp_path / "proj")
    d = _describe(capsys, "--report", str(tmp_path / "proj"))
    assert d["model"] == {"available": True, "tables": {"Sales": {
        "columns": ["Sales[Amount]", "Sales[Country]", "Sales[Region]"],
        "measures": ["[Total Amount]"], "hierarchies": {}, "hidden": []}}, "hidden_tables": []}
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
    g.write_text("canvas: {gutter: 16}\nlayouts: {search_path: [lay]}\n")
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
    assert "  kpi                region kpi-row  value*: measure, trend*: column, target: measure\n" in out
    assert "  slicer             region main     field*[]: column; options style: dropdown\n" in out
    assert "  standard-4-up (default): 1280x720; 1 header, 1 kpi-row, 2 main" in out
    assert "    measures: [Total Amount]" in out
    assert "  Overview  (1920x1080; not built by a spec)" in out
