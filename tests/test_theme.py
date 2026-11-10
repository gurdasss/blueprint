import json
import shutil
from pathlib import Path

import pytest

from blueprint import guidelines, validate
from blueprint.cli import main
from blueprint.model import TextClass
from blueprint.pbir import jsonfmt, theme
from blueprint.pbir.reader import read_report
from blueprint.validate import check_report

ROOT = Path(__file__).resolve().parent.parent
GUIDE = ROOT / "guidelines" / "example.yaml"


def _rules(tmp_path: Path, body: str) -> guidelines.Guidelines:
    f = tmp_path / "g.yaml"
    f.write_text(body)
    return guidelines.load(f)


@pytest.fixture
def report(tmp_path: Path) -> Path:
    shutil.copytree(ROOT / "fixtures" / "02-card-and-chart", tmp_path / "proj")
    return tmp_path / "proj" / "Fixture.Report"


# --- build -----------------------------------------------------------------------------


def test_example_guidelines_theme():
    doc, notes = theme.build(guidelines.load(GUIDE))
    assert doc == {
        "name": "Example Corp Reporting Standard",
        "dataColors": ["#4E79A7", "#F28E2B", "#E15759", "#76B7B2", "#59A14F"],
        "foreground": "#333333",
        "background": "#FFFFFF",
        "textClasses": {"callout": {"color": "#333333"},
                        "title": {"fontFace": "Segoe UI Semibold", "fontSize": 18, "color": "#333333"},
                        "header": {"color": "#333333"}, "label": {"color": "#333333"}},
        # probe 06: the base theme's visualStyles title size outranks textClasses, so set it too
        "visualStyles": {"*": {"*": {"title": [{"fontSize": 18}], "subTitle": [{"fontSize": 12}]}}},
    }
    assert notes == ["typography.subtitle: the theme can't set its font (unverified); visuals are still checked"]


def test_typography_only_and_first_choice_notes(tmp_path: Path):
    doc, notes = theme.build(_rules(tmp_path, "name: T\ntypography:\n  callout: {font: [DIN, Arial], size: [28, 32], bold: true}\n"))
    assert doc == {"name": "T", "textClasses": {"callout": {"fontFace": "DIN", "fontSize": 28}}}  # no card
    assert any("first allowed font, 'DIN'" in n for n in notes)
    assert any("first allowed size, 28pt" in n for n in notes)
    assert any("bold: not expressible" in n for n in notes)


def test_nothing_to_theme_is_an_error(tmp_path: Path):
    with pytest.raises(theme.ThemeError, match="nothing to put in a theme"):
        theme.build(_rules(tmp_path, "grid: {size: 8}\n"))


# --- report.json ------------------------------------------------------------------------


def test_with_theme_on_a_new_report_mirrors_desktop(blank_fixture: Path):
    doc = jsonfmt.load(blank_fixture / "definition/report.json")
    out = theme.with_theme(doc, replace=False)
    custom = out["themeCollection"]["customTheme"]
    assert custom == {"name": "blueprint-theme.json",
                      "reportVersionAtImport": doc["themeCollection"]["baseTheme"]["reportVersionAtImport"],
                      "type": "RegisteredResources"}
    assert out["resourcePackages"][0] == {"name": "RegisteredResources", "type": "RegisteredResources",
                                          "items": [{"name": "blueprint-theme.json", "path": "blueprint-theme.json",
                                                     "type": "CustomTheme"}]}
    assert out["resourcePackages"][1] == doc["resourcePackages"][0]  # base theme package untouched
    assert theme.with_theme(out, replace=False) == out  # idempotent


def test_resource_packages_inserted_before_settings_when_absent():
    doc = {"$schema": "x", "themeCollection": {}, "objects": {}, "settings": {"a": True}}
    assert list(theme.with_theme(doc, replace=False)) == ["$schema", "themeCollection", "objects",
                                                          "resourcePackages", "settings"]


def test_existing_custom_theme_needs_replace_and_keeps_its_item():
    doc = {"themeCollection": {"customTheme": {"name": "Bloom1.json", "type": "RegisteredResources"}},
           "resourcePackages": [{"name": "RegisteredResources", "type": "RegisteredResources",
                                 "items": [{"name": "Bloom1.json", "path": "Bloom1.json", "type": "CustomTheme"},
                                           {"name": "logo.png", "path": "logo.png", "type": "Image"}]}]}
    with pytest.raises(theme.ThemeError, match="already uses custom theme 'Bloom1.json'"):
        theme.with_theme(doc, replace=False)
    out = theme.with_theme(doc, replace=True)
    assert out["themeCollection"]["customTheme"]["name"] == "blueprint-theme.json"
    # Sorted by name, case-insensitively, as Desktop listed them (probe 03); the old item is kept.
    assert [i["name"] for i in out["resourcePackages"][0]["items"]] == ["Bloom1.json", "blueprint-theme.json",
                                                                       "logo.png"]


# --- command ----------------------------------------------------------------------------


def _snapshot(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def test_theme_clears_theme_findings_and_is_idempotent(report: Path, capsys):
    check = ["check", "--report", str(report), "--guidelines", str(GUIDE), "--json"]
    main(check)
    before = json.loads(capsys.readouterr().out)["findings"]
    assert any(f["rule"] in ("palette", "typography") and f["page"] is None for f in before)

    assert main(["theme", "--report", str(report), "--guidelines", str(GUIDE)]) == 0
    capsys.readouterr()
    main(check)
    after = json.loads(capsys.readouterr().out)["findings"]
    assert [f for f in after if f["rule"] in ("palette", "typography")] == []

    once = _snapshot(report)
    capsys.readouterr()
    assert main(["theme", "--report", str(report), "--guidelines", str(GUIDE)]) == 0
    assert "No changes." in capsys.readouterr().out
    assert _snapshot(report) == once
    [base, custom] = read_report(report).themes
    assert (base.name, custom.name, custom.missing) == ("Fluent2-CY26SU10", "blueprint-theme.json", False)


def test_dry_run_and_stale_file_write_nothing(report: Path, capsys):
    before = _snapshot(report)
    assert main(["theme", "--report", str(report), "--guidelines", str(GUIDE), "--dry-run"]) == 0
    assert "A StaticResources/RegisteredResources/blueprint-theme.json" in capsys.readouterr().out
    assert _snapshot(report) == before


def test_written_theme_file_is_desktop_formatted(report: Path):
    main(["theme", "--report", str(report), "--guidelines", str(GUIDE)])
    raw = (report / theme.REL_PATH).read_bytes()
    assert b"\r\n" in raw and not raw.endswith(b"\n") and jsonfmt.dump_bytes(jsonfmt.loads_bytes(raw)) == raw


def test_base_visual_styles_title_size_outranks_text_classes(tmp_path: Path):
    """Probe 06: textClasses.title 18 in our theme, but the base theme's visualStyles title 15 won."""
    from blueprint.validate import check_report
    from tests.builders import add_theme, make_report
    rd = make_report(tmp_path / "r", {"p": []})
    add_theme(rd, "base", "B", {"textClasses": {"title": {"fontSize": 12, "fontFace": "DIN"}},
                                "visualStyles": {"*": {"*": {"title": [{"show": True, "fontSize": 15}]}}}},
              folder="BaseThemes")
    add_theme(rd, "custom", "C", {"textClasses": {"title": {"fontSize": 18, "fontFace": "Segoe UI Semibold"}}},
              package="RegisteredResources", folder="t")
    rules = _rules(tmp_path, "typography: {title: {font: Segoe UI Semibold, size: 18}}\n")
    found = [f.message for f in check_report(read_report(rd), rules).findings if f.rule == "typography"]
    assert found == ["theme 'C' title text: size 15pt (allowed: 18)"]  # the false pass, now caught

    # Writing the size at the visualStyles level too (what bp theme now does) fixes it.
    add_theme(rd, "custom", "C2", {"textClasses": {"title": {"fontSize": 18, "fontFace": "Segoe UI Semibold"}},
                                   "visualStyles": {"*": {"*": {"title": [{"fontSize": 18}]}}}},
              package="RegisteredResources", folder="t")
    assert [f for f in check_report(read_report(rd), rules).findings if f.rule == "typography"] == []


def test_fixture_base_theme_visual_text(blank_fixture: Path):
    [base] = read_report(blank_fixture).themes
    assert base.visual_text["title"].size == 15 and base.visual_text["subTitle"].size == 12
    # probe 07: what Desktop showed as the new card's Category label default (Segoe UI 12)
    assert base.visual_text["cardVisual.label"].size == 12
    assert validate.theme_font(base, "card_label") == TextClass("Segoe UI", 12.0)


def test_card_label_is_written_as_the_cardvisual_label_style(tmp_path: Path):
    doc, notes = theme.build(_rules(tmp_path, "name: T\ntypography:\n  title: {size: 18}\n"
                                              "  card_label: {font: Arial, size: 14}\n"))
    # exactly the entry Desktop showed as Arial 14 in probe 15, after the "*" styles
    assert doc["visualStyles"] == {
        "*": {"*": {"title": [{"fontSize": 18}]}},
        "cardVisual": {"*": {"label": [{"$id": "default", "fontSize": 14,
                                        "fontFamily": "'Arial', helvetica, arial, sans-serif"}]}},
    }
    assert "label" not in doc["textClasses"]  # textClasses.label is every visual's "General" text
    assert notes == []


def test_card_label_notes(tmp_path: Path):
    doc, notes = theme.build(_rules(tmp_path, "name: T\ntypography:\n"
                                              "  card_label: {font: [Segoe UI, Arial], size: [12, 14], bold: true}\n"))
    assert doc["visualStyles"]["cardVisual"]["*"]["label"] == [
        {"$id": "default", "fontSize": 12, "fontFamily": "'Segoe UI', helvetica, arial, sans-serif"}]
    assert notes == ["typography.card_label: theme uses the first allowed size, 12pt",
                     "typography.card_label: theme uses the first allowed font, 'Segoe UI'",
                     ("typography.card_label.bold: not expressible in a theme (unverified); "
                      "visuals are still checked")]
    _, notes = theme.build(_rules(tmp_path, "name: T\ntypography:\n  callout: {size: 30}\n"
                                            "  card_label: {bold: false}\n"))
    assert notes == [("typography.card_label.bold: not expressible in a theme (unverified); "
                      "visuals are still checked")]


def test_theme_then_check_passes_the_card_label(tmp_path: Path, card_chart_fixture: Path):
    report = tmp_path / "proj"
    shutil.copytree(card_chart_fixture.parent, report)
    guide = tmp_path / "g.yaml"
    guide.write_text("name: T\ntypography:\n  card_label: {font: Arial, size: 14}\n")
    rules = guidelines.load(guide)
    before = check_report(read_report(report), rules).findings
    assert [f.message for f in before if f.rule == "typography"] == [
        "theme 'Fluent2-CY26SU10' card_label text: font 'Segoe UI' (allowed: Arial); size 12pt (allowed: 14)"]
    assert main(["theme", "--report", str(report), "--guidelines", str(guide)]) == 0
    after = check_report(read_report(report), rules).findings
    assert [f for f in after if f.rule == "typography"] == []


def test_replacing_a_custom_theme_when_there_is_no_base_theme(card_chart_fixture, tmp_path):
    """Microsoft's Retail sample has only a customTheme (Concourse) and no baseTheme. The schema
    requires reportVersionAtImport on customTheme, so it comes from the theme being replaced
    (Desktop gave both layers the same value, probes 02 and 03). Desktop opened the result."""
    proj = tmp_path / "proj"
    shutil.copytree(card_chart_fixture.parent, proj)
    report_json = proj / "Fixture.Report" / "definition" / "report.json"
    doc = jsonfmt.load(report_json)
    version = {"visual": "1.8.26", "report": "2.0.26", "page": "1.3.26"}
    doc["themeCollection"] = {"customTheme": {"name": "Concourse", "reportVersionAtImport": version,
                                              "type": "RegisteredResources"}}
    report_json.write_bytes(jsonfmt.dump_bytes(doc))
    args = ["theme", "--report", str(proj), "--guidelines", str(GUIDE)]
    assert main(args) == 2  # a non-Blueprint custom theme needs --replace-theme
    assert main([*args, "--replace-theme"]) == 0
    assert jsonfmt.load(report_json)["themeCollection"] == {"customTheme": {
        "name": "blueprint-theme.json", "reportVersionAtImport": version, "type": "RegisteredResources"}}
