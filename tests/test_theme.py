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
        "visualStyles": {"*": {"*": {"title": [{"fontSize": 18}]}}},
    }
    # page_title is written onto header textboxes by bp apply; body (textboxes) has no theme class
    assert notes == [("typography.body: the theme can't set its font or size (unverified); "
                      "visuals are still checked")]


def test_typography_only_and_first_choice_notes(tmp_path: Path):
    doc, notes = theme.build(_rules(
        tmp_path, "name: T\nextensions:\n  typography:\n    callout: {font: [DIN, Arial], size: [28, 32]}\n"))
    assert doc == {"name": "T", "textClasses": {"callout": {"fontFace": "DIN", "fontSize": 28}}}  # no card
    assert any("first allowed font, 'DIN'" in n for n in notes)
    assert any("first allowed size, 28pt" in n for n in notes)


def test_nothing_to_theme_is_an_error(tmp_path: Path):
    with pytest.raises(theme.ThemeError, match="nothing to put in a theme"):
        theme.build(_rules(tmp_path, "spacing: {grid: 8}\n"))


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
    rules = _rules(tmp_path, "typography: {visual_title: {font: Segoe UI Semibold, size: 18}}\n")
    found = [f.message for f in check_report(read_report(rd), rules).findings if f.rule == "typography"]
    assert found == ["theme 'C' visual_title text: size 15pt (allowed: 18)"]  # the false pass, now caught

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
    doc, notes = theme.build(_rules(tmp_path, "name: T\ntypography:\n  visual_title: {size: 18}\n"
                                              "extensions:\n  typography:\n"
                                              "    card_label: {font: Arial, size: 14}\n"))
    # exactly the entry Desktop showed as Arial 14 in probe 15, after the "*" styles
    assert doc["visualStyles"] == {
        "*": {"*": {"title": [{"fontSize": 18}]}},
        "cardVisual": {"*": {"label": [{"$id": "default", "fontSize": 14,
                                        "fontFamily": "'Arial', helvetica, arial, sans-serif"}]}},
    }
    assert "label" not in doc["textClasses"]  # textClasses.label is every visual's "General" text
    assert notes == []


def test_card_label_notes(tmp_path: Path):
    doc, notes = theme.build(_rules(
        tmp_path, "name: T\nextensions:\n  typography:\n"
                  "    card_label: {font: [Segoe UI, Arial], size: [12, 14]}\n"))
    assert doc["visualStyles"]["cardVisual"]["*"]["label"] == [
        {"$id": "default", "fontSize": 12, "fontFamily": "'Segoe UI', helvetica, arial, sans-serif"}]
    assert notes == ["extensions.typography.card_label: theme uses the first allowed size, 12pt",
                     "extensions.typography.card_label: theme uses the first allowed font, 'Segoe UI'"]
    doc, notes = theme.build(_rules(
        tmp_path, "name: T\ntypography: {visual_title: {size: 18}}\n"
                  "extensions:\n  typography:\n    card_label: {font: \"Se'goe, UI\"}\n"))
    assert "cardVisual" not in doc["visualStyles"]  # a font that can't be a CSS stack sets nothing
    assert notes == [("extensions.typography.card_label: font \"Se'goe, UI\" can't be written as a "
                      "font stack; visuals are still checked")]


def test_theme_then_check_passes_the_card_label(tmp_path: Path, card_chart_fixture: Path):
    report = tmp_path / "proj"
    shutil.copytree(card_chart_fixture.parent, report)
    guide = tmp_path / "g.yaml"
    guide.write_text("name: T\nextensions:\n  typography:\n    card_label: {font: Arial, size: 14}\n")
    rules = guidelines.load(guide)
    before = check_report(read_report(report), rules).findings
    assert [f.message for f in before if f.rule == "typography"] == [
        ("theme 'Fluent2-CY26SU10' card_label text: font 'Segoe UI' (allowed: Arial); "
         "size 12pt (allowed: 14)")]
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


# --- sentiment colours (probe 42) ---------------------------------------------------------

CATEGORICAL = "categorical: ['#4E79A7', '#F28E2B']"  # the palette check only runs with one
SENTIMENT = "palette: {" + CATEGORICAL + ", good: '#00e000', neutral: '#00B7FF', bad: '#8000FF'}\n"


def test_sentiment_colours_are_written_with_the_themes_own_key_names(tmp_path: Path):
    doc, _ = theme.build(_rules(tmp_path, "name: S\npalette: {background: '#F7F4EC', "
                                          "good: '#00e000', neutral: '#00B7FF', bad: '#8000FF'}\n"))
    # probe 42: Desktop saved good/neutral/bad right after background, upper-cased hex
    assert list(doc) == ["name", "background", "good", "neutral", "bad"]
    assert (doc["good"], doc["neutral"], doc["bad"]) == ("#00E000", "#00B7FF", "#8000FF")


def test_unset_sentiment_colours_are_left_to_the_theme(tmp_path: Path):
    doc, _ = theme.build(_rules(tmp_path, "palette: {good: '#00E000', text: '#333333'}\n"))
    assert doc["good"] == "#00E000"
    assert "neutral" not in doc and "bad" not in doc
    doc, _ = theme.build(guidelines.load(GUIDE))
    assert not {"good", "neutral", "bad"} & set(doc)


def test_sentiment_alone_is_enough_for_a_theme(tmp_path: Path):
    doc, _ = theme.build(_rules(tmp_path, "palette: {bad: '#8000FF'}\n"))
    assert doc == {"name": "Blueprint defaults", "bad": "#8000FF"}


@pytest.mark.parametrize("body", ["palette: {good: green}\n", "palette: {bad: '#FFF'}\n",
                                  "palette: {neutral: 5}\n"])
def test_a_bad_sentiment_colour_is_refused(tmp_path: Path, body: str):
    with pytest.raises(guidelines.GuidelinesError, match=r"palette\.(good|bad|neutral) must be a #RRGGBB"):
        _rules(tmp_path, body)


def test_a_misspelt_sentiment_key_is_refused_with_the_real_one(tmp_path: Path):
    with pytest.raises(guidelines.GuidelinesError, match="did you mean good"):
        _rules(tmp_path, "palette: {goood: '#00E000'}\n")


def test_sentiment_colours_can_be_set_from_the_command_line(tmp_path: Path):
    f = tmp_path / "g.yaml"
    f.write_text("palette: {good: '#00E000'}\n")
    rules = guidelines.load(f, overrides=guidelines.overrides_from(["palette.bad=#8000FF"]))
    assert rules.palette.sentiment == {"good": "#00E000", "bad": "#8000FF"}


def test_sentiment_colours_are_allowed_colours(tmp_path: Path):
    pal = _rules(tmp_path, SENTIMENT).palette
    assert {"#00E000", "#00B7FF", "#8000FF"} <= pal.allowed


def test_theme_then_check_passes_sentiment_and_a_wrong_one_is_found(report: Path, tmp_path: Path, capsys):
    g = tmp_path / "g.yaml"
    g.write_text("name: S\n" + SENTIMENT)
    assert main(["theme", "--report", str(report), "--guidelines", str(g)]) == 0
    written = json.loads((report / "StaticResources/RegisteredResources/blueprint-theme.json").read_text())
    assert (written["good"], written["bad"]) == ("#00E000", "#8000FF")
    capsys.readouterr()
    main(["check", "--report", str(report), "--guidelines", str(g), "--json"])
    findings = json.loads(capsys.readouterr().out)["findings"]
    assert [f for f in findings if f["rule"] == "palette" and "sentiment" in f["message"]] == []

    # the report's theme says #8000FF for bad; a guidelines file that wants another is a finding
    g.write_text("name: S\npalette: {" + CATEGORICAL + ", good: '#00E000', bad: '#C2452D', neutral: '#00B7FF'}\n")
    main(["check", "--report", str(report), "--guidelines", str(g), "--json"])
    msgs = [f["message"] for f in json.loads(capsys.readouterr().out)["findings"] if f["rule"] == "palette"]
    assert [m for m in msgs if "sentiment" in m] == [
        "theme 'blueprint-theme.json' sentiment colour bad is #8000FF, palette says #C2452D"]


def test_check_reports_a_sentiment_colour_the_theme_never_sets(report: Path, tmp_path: Path, capsys):
    g = tmp_path / "g.yaml"
    g.write_text("palette: {" + CATEGORICAL + ", good: '#00E000'}\n")
    main(["check", "--report", str(report), "--guidelines", str(g), "--json"])
    msgs = [f["message"] for f in json.loads(capsys.readouterr().out)["findings"] if f["rule"] == "palette"]
    assert any("sentiment colour good is" in m and "palette says #00E000" in m for m in msgs)


# --- structural colours (probes 46, 48) ---------------------------------------------------

STRUCTURAL = ("palette: {second_level: '#FF2D95', third_level: '#4639FF', "
              "fourth_level: '#9B30FF', disabled_text: '#808000'}\n")


def test_structural_colours_are_written_under_the_themes_own_key_names(tmp_path: Path):
    doc, _ = theme.build(_rules(tmp_path, "name: S\n" + STRUCTURAL))
    # the client writes the dialog's labels; the theme gets Desktop's key names (probe 46)
    assert doc == {"name": "S", "foregroundNeutralSecondary": "#FF2D95", "backgroundLight": "#4639FF",
                   "foregroundNeutralTertiary": "#9B30FF", "disabledText": "#808000"}


def test_the_guideline_and_theme_key_lists_agree():
    from blueprint.guidelines import STRUCTURAL as mapping
    from blueprint.pbir.formatting import STRUCTURAL_KEYS

    assert set(mapping.values()) == set(STRUCTURAL_KEYS)
    assert set(mapping) <= set(guidelines.CORE_KEYS["palette"])


def test_unset_structural_colours_are_left_to_the_theme(tmp_path: Path):
    doc, _ = theme.build(_rules(tmp_path, "palette: {third_level: '#4639FF', text: '#333333'}\n"))
    assert doc["backgroundLight"] == "#4639FF"
    assert not {"foregroundNeutralSecondary", "foregroundNeutralTertiary", "disabledText"} & set(doc)
    doc, _ = theme.build(guidelines.load(GUIDE))
    assert not set(guidelines.STRUCTURAL.values()) & set(doc)


@pytest.mark.parametrize("body", ["palette: {second_level: grey}\n", "palette: {disabled_text: '#FFF'}\n"])
def test_a_bad_structural_colour_is_refused(tmp_path: Path, body: str):
    with pytest.raises(guidelines.GuidelinesError,
                       match=r"palette\.(second_level|disabled_text) must be a #RRGGBB"):
        _rules(tmp_path, body)


def test_a_misspelt_structural_key_is_refused_with_the_real_one(tmp_path: Path):
    with pytest.raises(guidelines.GuidelinesError, match="did you mean third_level"):
        _rules(tmp_path, "palette: {third_levl: '#4639FF'}\n")
    # the theme's own key name is not the client's key: it must not load silently either
    with pytest.raises(guidelines.GuidelinesError, match="unknown key palette.foregroundNeutralSecondary"):
        _rules(tmp_path, "palette: {foregroundNeutralSecondary: '#FF2D95'}\n")


def test_structural_colours_can_be_set_from_the_command_line_and_are_allowed(tmp_path: Path):
    f = tmp_path / "g.yaml"
    f.write_text("palette: {second_level: '#FF2D95'}\n")
    rules = guidelines.load(f, overrides=guidelines.overrides_from(["palette.fourth_level=#9B30FF"]))
    assert rules.palette.structural == {"foregroundNeutralSecondary": "#FF2D95",
                                        "foregroundNeutralTertiary": "#9B30FF"}
    assert {"#FF2D95", "#9B30FF"} <= rules.palette.allowed


def test_theme_then_check_passes_structural_and_a_wrong_one_names_both_keys(report: Path, tmp_path: Path,
                                                                            capsys):
    g = tmp_path / "g.yaml"
    g.write_text("name: S\npalette: {categorical: ['#4E79A7'], second_level: '#FF2D95', "
                 "third_level: '#4639FF', fourth_level: '#9B30FF', disabled_text: '#808000'}\n")
    assert main(["theme", "--report", str(report), "--guidelines", str(g)]) == 0
    written = json.loads((report / "StaticResources/RegisteredResources/blueprint-theme.json").read_text())
    assert written["foregroundNeutralSecondary"] == "#FF2D95" and written["disabledText"] == "#808000"

    def structural_findings(guide: Path) -> list[str]:
        capsys.readouterr()
        main(["check", "--report", str(report), "--guidelines", str(guide), "--json"])
        found = json.loads(capsys.readouterr().out)["findings"]
        return [f["message"] for f in found if f["rule"] == "palette" and "structural" in f["message"]]

    assert structural_findings(g) == []
    g.write_text("name: S\npalette: {categorical: ['#4E79A7'], third_level: '#B6FF3B'}\n")
    assert structural_findings(g) == [
        ("theme 'blueprint-theme.json' structural colour third_level (backgroundLight) is #4639FF, "
         "palette says #B6FF3B")]
