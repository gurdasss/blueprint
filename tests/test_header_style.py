"""typography.header: written onto Blueprint's header textboxes by apply, checked by check."""

import json
import shutil
from pathlib import Path

import pytest

from blueprint import guidelines
from blueprint.cli import main
from blueprint.pbir import jsonfmt, render, theme
from blueprint.pbir.reader import read_report
from tests.builders import write

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "examples" / "sales-overview.yaml"
GUIDE = ROOT / "guidelines" / "example.yaml"


@pytest.fixture
def report(tmp_path: Path) -> Path:
    shutil.copytree(ROOT / "fixtures" / "02-card-and-chart", tmp_path / "proj")
    return tmp_path / "proj" / "Fixture.Report"


def _header(report: Path):
    page = next(p for p in read_report(report).pages if p.spec_page)
    return next(v for v in page.visuals if v.spec_id == "header-1")


def _guide(tmp_path: Path, header: str) -> Path:
    g = tmp_path / "g.yaml"
    g.write_text(GUIDE.read_text().replace("{ font: Segoe UI Semibold, size: 20 }", header)
                 .replace('search_path: ["layouts"]', f'search_path: ["{ROOT / "guidelines" / "layouts"}"]'))
    return g


def test_text_style_shapes_match_probe_03():
    assert render.text_style("Arial", 20, True) == {"fontFamily": "Arial", "fontSize": "20pt", "fontWeight": "bold"}
    assert render.text_style("Segoe UI", 10.5, False) == {"fontFamily": "Segoe UI", "fontSize": "10.5pt"}
    assert render.text_style(None, None, None) == {}


def test_with_textbox_keeps_unowned_style_and_refuses_hand_edits():
    doc = {"visual": {"objects": {"general": [{"properties": {"paragraphs": [{"textRuns": [
        {"value": "Old", "textStyle": {"fontFamily": "Arial", "color": "#123456"}}],
        "horizontalTextAlignment": "center"}]}}]}}}
    out = render.with_textbox(doc, "New", {"fontFamily": "Segoe UI", "fontSize": "20pt"})
    para = out["visual"]["objects"]["general"][0]["properties"]["paragraphs"][0]
    assert para["textRuns"] == [{"value": "New", "textStyle": {"color": "#123456", "fontFamily": "Segoe UI",
                                                               "fontSize": "20pt"}}]
    assert para["horizontalTextAlignment"] == "center"
    two_runs = json.loads(json.dumps(doc))
    two_runs["visual"]["objects"]["general"][0]["properties"]["paragraphs"][0]["textRuns"].append({"value": "x"})
    assert render.with_textbox(two_runs, "New", {}) is None


def test_apply_writes_header_style_and_check_passes(report: Path, capsys):
    main(["apply", str(SPEC), "--report", str(report), "--guidelines", str(GUIDE)])
    [font] = _header(report).fonts
    assert (font.family, font.size, font.bold) == ("Segoe UI Semibold", 20.0, None)
    capsys.readouterr()
    main(["check", "--report", str(report), "--guidelines", str(GUIDE), "--json"])
    findings = json.loads(capsys.readouterr().out)["findings"]
    # Theme-level findings remain (bp theme wasn't run); no visual-level typography findings.
    assert [f for f in findings if f["rule"] == "typography" and f["page"] is not None] == []


def test_reapply_updates_header_text_and_style(report: Path, tmp_path: Path, capsys):
    main(["apply", str(SPEC), "--report", str(report), "--guidelines", str(GUIDE)])
    spec = tmp_path / "s.yaml"
    spec.write_text(SPEC.read_text().replace("title: Sales Overview", "title: Sales at a Glance"))
    g = _guide(tmp_path, "{ font: Segoe UI, size: 24, bold: true }")
    capsys.readouterr()
    assert main(["apply", str(spec), "--report", str(report), "--guidelines", str(g)]) == 0
    header = _header(report)
    [font] = header.fonts
    assert (header.text, font.family, font.size, font.bold) == ("Sales at a Glance", "Segoe UI", 24.0, True)


def test_hand_edited_header_is_left_alone_with_a_warning(report: Path, capsys):
    main(["apply", str(SPEC), "--report", str(report), "--guidelines", str(GUIDE)])
    path = report / _header(report).source.path
    doc = jsonfmt.load(path)
    runs = doc["visual"]["objects"]["general"][0]["properties"]["paragraphs"][0]["textRuns"]
    runs.append({"value": " (draft)", "textStyle": {"fontFamily": "Arial"}})
    write(path, doc)
    before = path.read_bytes()
    capsys.readouterr()
    assert main(["apply", str(SPEC), "--report", str(report), "--guidelines", str(GUIDE)]) == 0
    assert "header textbox was edited by hand" in capsys.readouterr().out
    assert path.read_bytes() == before


def test_check_applies_header_rule_to_blueprint_headers_only(report: Path, tmp_path: Path, capsys):
    main(["apply", str(SPEC), "--report", str(report), "--guidelines", str(GUIDE)])
    g = _guide(tmp_path, "{ font: Segoe UI Semibold, size: 32 }")  # stricter than what was written
    g.write_text(g.read_text() + "  textbox:  { font: Arial }\n")
    capsys.readouterr()
    main(["check", "--report", str(report), "--guidelines", str(g), "--json"])
    found = [(f["visual"], f["message"]) for f in json.loads(capsys.readouterr().out)["findings"]
             if f["rule"] == "typography"]
    header = _header(report).name
    assert (header, "header size 20pt (allowed: 32)") in found
    assert not any(v == header and "textbox" in m for v, m in found)


def test_theme_ignores_header_role():
    doc, notes = theme.build(guidelines.load(GUIDE))
    assert not any("header" in n for n in notes)
    assert "header" in doc["textClasses"] and set(doc["textClasses"]["header"]) == {"color"}
