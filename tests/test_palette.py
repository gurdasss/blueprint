from pathlib import Path

import pytest

from blueprint import guidelines
from blueprint.pbir.reader import IGNORE_ANNOTATION, read_report
from blueprint.validate import check_report
from tests.builders import add_theme, hex_color, make_report, theme_color, visual, write

PALETTE = """
palette:
  categorical: ["#4E79A7", "#F28E2B"]
  background: "#FFFFFF"
  text: "#333333"
  enforce: strict
"""
GOOD_THEME = {"dataColors": ["#4e79a7", "#F28E2B", "#000001"], "foreground": "#333333",
              "background": "#FFFFFF"}


def _rules(tmp_path: Path, body: str = PALETTE) -> guidelines.Guidelines:
    f = tmp_path / "g.yaml"
    f.write_text(body)
    return guidelines.load(f)


def _palette_findings(tmp_path: Path, rd: Path, body: str = PALETTE):
    res = check_report(read_report(rd), _rules(tmp_path, body))
    return [f for f in res.findings if f.rule == "palette"], res.notes


# --- rule -------------------------------------------------------------------------------


def test_compliant_report_is_clean(tmp_path: Path):
    v = visual("a", 16, 16, 64, 64)
    v["visual"]["objects"] = {"dataPoint": [{"properties": {"fill": hex_color("#F28E2B")}}],
                              "labels": [{"properties": {"color": theme_color(0, -0.1)}}]}
    rd = make_report(tmp_path / "r", {"p": [v]})
    add_theme(rd, "custom", "Good", GOOD_THEME)
    assert _palette_findings(tmp_path, rd) == ([], [])


def test_off_palette_hex_reported_per_visual_and_page(tmp_path: Path):
    v = visual("a", 16, 16, 64, 64)
    v["visual"]["objects"] = {"dataPoint": [{"properties": {"fill": hex_color("#E15759")}}],
                              "general": [{"properties": {"paragraphs": [{"textRuns": [
                                  {"value": "x", "textStyle": {"color": "#f7c1a4"}}]}]}}]}
    rd = make_report(tmp_path / "r", {"p": [v]})
    add_theme(rd, "custom", "Good", GOOD_THEME)
    page = rd / "definition/pages/p/page.json"
    from blueprint.pbir import jsonfmt
    doc = jsonfmt.load(page)
    doc["objects"] = {"background": [{"properties": {"color": hex_color("#F3F2F1")}}]}
    write(page, doc)
    found, notes = _palette_findings(tmp_path, rd)
    assert [(f.visual, f.severity, f.message) for f in found] == [
        (None, "error", "colours not in the palette: background.color #F3F2F1"),
        ("a", "error", "colours not in the palette: dataPoint.fill #E15759, text #F7C1A4"),
    ]
    assert any("add approved shades to palette.extra" in n for n in notes)


def test_extra_allows_and_ignore_exempts(tmp_path: Path):
    a = visual("a", 16, 16, 64, 64)
    a["visual"]["objects"] = {"labels": [{"properties": {"color": hex_color("#F7C1A4")}}]}
    b = visual("b", 96, 16, 64, 64, annotations=[{"name": IGNORE_ANNOTATION, "value": "true"}])
    b["visual"]["objects"] = {"labels": [{"properties": {"color": hex_color("#123456")}}]}
    rd = make_report(tmp_path / "r", {"p": [a, b]})
    add_theme(rd, "custom", "Good", GOOD_THEME)
    assert _palette_findings(tmp_path, rd, PALETTE + '  extra: ["#f7c1a4"]\n')[0] == []


def test_theme_mismatch_and_missing(tmp_path: Path):
    rd = make_report(tmp_path / "r", {"p": []})
    add_theme(rd, "base", "Base1", {"dataColors": ["#4E79A7"], "background": "#000000", "foreground": "#333333"},
              folder="BaseThemes")
    found, _ = _palette_findings(tmp_path, rd)
    assert [f.message for f in found] == [
        "theme 'Base1' data colours differ from palette.categorical at theme has only 1 data colours, palette has 2",
        "theme 'Base1' background is #000000, palette says #FFFFFF",
    ]
    rd2 = make_report(tmp_path / "r2", {"p": []})
    add_theme(rd2, "custom", "Concourse", None, package="RegisteredResources", folder="themes")
    found, _ = _palette_findings(tmp_path, rd2)
    assert [f.message for f in found] == [
        "custom theme 'Concourse' is referenced but its file is missing; theme colours can't be checked"]


def test_custom_theme_overrides_base_field_by_field(tmp_path: Path):
    rd = make_report(tmp_path / "r", {"p": []})
    add_theme(rd, "base", "Base1", GOOD_THEME, folder="BaseThemes")
    add_theme(rd, "custom", "OnlyText", {"foreground": "#F5F5F5"})  # like Dark's partial textClasses
    found, _ = _palette_findings(tmp_path, rd)
    assert [f.message for f in found] == ["theme 'OnlyText' foreground is #F5F5F5, palette says #333333"]


def test_unreadable_theme_notes_unchecked_refs_and_expressions(tmp_path: Path):
    v = visual("a", 16, 16, 64, 64)
    v["visual"]["objects"] = {"dataPoint": [{"properties": {"fill": theme_color(3)}}],
                              "labels": [{"properties": {"color": {"solid": {"color": {"expr": {"FillRule": {}}}}}}}]}
    rd = make_report(tmp_path / "r", {"p": [v]})
    _, notes = _palette_findings(tmp_path, rd)
    assert "1 theme colour reference(s) not checked (no readable theme)" in notes
    assert "1 colour expression(s) not checked (e.g. conditional formatting)" in notes


@pytest.mark.parametrize(("enforce", "severity"), [("warn", "warning"), ("off", None), ("'off'", None)])
def test_enforce_levels(tmp_path: Path, enforce: str, severity):
    v = visual("a", 16, 16, 64, 64)
    v["visual"]["objects"] = {"labels": [{"properties": {"color": hex_color("#123456")}}]}
    rd = make_report(tmp_path / "r", {"p": [v]})
    add_theme(rd, "custom", "Good", GOOD_THEME)
    found, _ = _palette_findings(tmp_path, rd, PALETTE.replace("enforce: strict", f"enforce: {enforce}"))
    assert [f.severity for f in found] == ([severity] if severity else [])


def test_no_palette_means_rule_inactive(tmp_path: Path):
    v = visual("a", 16, 16, 64, 64)
    v["visual"]["objects"] = {"labels": [{"properties": {"color": hex_color("#123456")}}]}
    assert _palette_findings(tmp_path, make_report(tmp_path / "r", {"p": [v]}), "")[0] == []


@pytest.mark.parametrize(("body", "match"), [
    ("palette: {categorical: ['#12345']}", r"palette.categorical\[0\] must be a #RRGGBB"),
    ("palette: {background: red}", "palette.background must be a #RRGGBB"),
    ("palette: {enforce: always}", "palette.enforce must be strict, warn or off"),
    ("palette: {extra: '#123456'}", "palette.extra must be a list"),
])
def test_palette_config_rejected(tmp_path: Path, body: str, match: str):
    f = tmp_path / "g.yaml"
    f.write_text(body)
    with pytest.raises(guidelines.GuidelinesError, match=match):
        guidelines.load(f)




def test_builtin_theme_without_file_is_a_note_not_a_finding(tmp_path: Path):
    # Probe 03 phase 2: Desktop's theme "Update" references a SharedResources base theme
    # without embedding the file.
    rd = make_report(tmp_path / "r", {"p": []})
    add_theme(rd, "base", "Fluent2-CY26SU10", None, folder="BaseThemes")
    add_theme(rd, "custom", "Good", GOOD_THEME, package="RegisteredResources", folder="themes")
    found, notes = _palette_findings(tmp_path, rd)
    assert found == []
    assert ("built-in base theme 'Fluent2-CY26SU10' isn't embedded in the report; "
            "its colours can't be checked") in notes
