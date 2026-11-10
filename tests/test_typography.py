from pathlib import Path

import pytest

from blueprint import guidelines
from blueprint.model import FontUse, TextClass
from blueprint.pbir import formatting
from blueprint.pbir.reader import IGNORE_ANNOTATION, read_report
from blueprint.validate import check_report
from tests.builders import add_theme, make_report, visual

STACK = "'''Segoe UI Semibold'', wf_segoe-ui_semibold, helvetica, arial, sans-serif'"


def lit(value: str) -> dict:
    return {"expr": {"Literal": {"Value": value}}}


def titled(name: str, vtype: str = "lineChart", **props) -> dict:
    v = visual(name, 16, 16, 64, 64, vtype=vtype)
    v["visual"]["visualContainerObjects"] = {"title": [{"properties": {k: lit(x) for k, x in props.items()}}]}
    return v


def textbox(name: str, **style) -> dict:
    v = visual(name, 16, 16, 64, 64, vtype="textbox")
    v["visual"]["objects"] = {"general": [{"properties": {"paragraphs": [{"textRuns": [
        {"value": "x", "textStyle": style}]}]}}]}
    return v


# --- extraction: every shape from probe 03 -----------------------------------------------


def test_fonts_in_reads_probe_03_shapes():
    vis = titled("a", fontFamily=STACK, fontSize="14D", bold="true")["visual"]
    vis["visualContainerObjects"]["subTitle"] = [{"properties": {"show": lit("true"), "fontSize": lit("12D")}}]
    assert formatting.fonts_in(vis) == [
        FontUse("title", "Segoe UI Semibold", 14.0, True,
                "'Segoe UI Semibold', wf_segoe-ui_semibold, helvetica, arial, sans-serif"),
        FontUse("subtitle", None, 12.0, None, None),
    ]
    assert formatting.fonts_in(titled("a", fontFamily="'Arial'")["visual"]) == [
        FontUse("title", "Arial", None, None, "Arial")]


def test_card_labels_are_callout_but_chart_labels_are_not():
    card = visual("c", vtype="card")["visual"]
    card["objects"] = {"labels": [{"properties": {"fontFamily": lit("'Arial'")}}]}
    assert [f.role for f in formatting.fonts_in(card)] == ["callout"]
    chart = visual("c", vtype="lineChart")["visual"]
    chart["objects"] = {"labels": [{"properties": {"fontFamily": lit("'Arial'")}}]}
    assert formatting.fonts_in(chart) == []


def new_card(name: str, **value) -> dict:
    """A cardVisual with probe 07's callout value shape (step 2) and its title (step 4)."""
    v = titled(name, vtype="cardVisual", text="'Total'", fontSize="16D")
    v["visual"]["objects"] = {
        "value": [{"properties": {k: lit(x) for k, x in value.items()}, "selector": {"id": "default"}}],
        "label": [{"properties": {"fontSize": lit("14D")}, "selector": {"id": "default"}}],
    }
    return v


def test_new_card_value_is_callout():
    vis = new_card("c", fontFamily="'Arial'", fontSize="28D", bold="true")["visual"]
    assert formatting.fonts_in(vis) == [
        FontUse("title", None, 16.0, None, None),
        FontUse("callout", "Arial", 28.0, True, "Arial"),
        FontUse("card_label", None, 14.0, None, None),  # probe 07 step 3
    ]
    chart = visual("c", vtype="lineChart")["visual"]
    chart["objects"] = {"value": [{"properties": {"fontFamily": lit("'Arial'")}}]}
    assert formatting.fonts_in(chart) == []


def test_textbox_runs():
    tb = textbox("t", fontWeight="bold", fontFamily="Arial", fontStyle="italic", fontSize="20pt")["visual"]
    assert formatting.fonts_in(tb) == [FontUse("textbox", "Arial", 20.0, True, "Arial")]
    plain = textbox("t", fontFamily="Segoe UI Light", fontSize="28pt", fontWeight="normal")["visual"]
    assert formatting.fonts_in(plain)[0].bold is False


def test_theme_text_classes_plain_and_stack(tmp_path: Path):
    rd = make_report(tmp_path, {"p": []})
    add_theme(rd, "base", "B", {"textClasses": {"title": {"fontFace": "DIN", "fontSize": 12}}}, folder="BaseThemes")
    add_theme(rd, "custom", "C", {"textClasses": {"title": {
        "fontFace": "'Segoe UI Semibold', wf_segoe-ui_semibold, helvetica, arial, sans-serif", "fontSize": 16}}},
        package="RegisteredResources", folder="t")
    base, custom = read_report(rd).themes
    assert base.text_classes["title"] == TextClass("DIN", 12.0)
    assert custom.text_classes["title"] == TextClass("Segoe UI Semibold", 16.0)


# --- guidelines ----------------------------------------------------------------------------


def _g(tmp_path: Path, body: str) -> guidelines.Guidelines:
    f = tmp_path / "g.yaml"
    f.write_text(body)
    return guidelines.load(f)


def test_typography_config_forms(tmp_path: Path):
    g = _g(tmp_path, "typography:\n  visual_title: {font: Segoe UI Semibold, size: 14}\n"
                     "  body: {font: [Segoe UI, Arial], size: [10, 12.5]}\n")
    assert g.typography["title"] == guidelines.FontRule(("Segoe UI Semibold",), (14.0,))
    assert g.typography["textbox"] == guidelines.FontRule(("Segoe UI", "Arial"), (10.0, 12.5))


@pytest.mark.parametrize(("body", "match"), [
    ("typography: {visual_title: {font: Segoe UI, weight: semibold}}", "no separate weight"),
    ("typography: {visual_title: {font: Segoe UI, bold: true}}", "doesn't check bold"),
    ("typography: {heading: {font: Arial}}", "unknown role"),
    ("typography: {visual_title: {size: big}}", "size must be a positive number"),
    ("typography: {visual_title: {font: 3}}", "font must be a font name"),
    ("typography: {visual_title: {colour: red}}", "unknown keys colour"),
])
def test_typography_config_rejected(tmp_path: Path, body: str, match: str):
    with pytest.raises(guidelines.GuidelinesError, match=match):
        _g(tmp_path, body)


# --- rule ----------------------------------------------------------------------------------

RULES = """typography:
  visual_title: {font: Segoe UI Semibold, size: [12, 14]}
  body: {font: [Segoe UI, Segoe UI Light]}
"""


def _typo(tmp_path: Path, visuals: list[dict], body: str = RULES, theme: dict | None = None):
    rd = make_report(tmp_path / "r", {"p": visuals})
    if theme is not None:
        add_theme(rd, "custom", "T", theme, package="RegisteredResources", folder="t")
    res = check_report(read_report(rd), _g(tmp_path, body))
    return [(f.visual, f.message) for f in res.findings if f.rule == "typography"], res.notes


def test_compliant_and_unset_values_pass(tmp_path: Path):
    vs = [titled("a", fontFamily=STACK, fontSize="14D"), titled("b", fontSize="12D"),  # family unset
          textbox("t", fontFamily="Segoe UI Light", fontSize="28pt")]
    assert _typo(tmp_path, vs) == ([], ["theme text classes not checked (no readable theme)"])


def test_violations_are_reported_per_visual(tmp_path: Path):
    vs = [titled("a", fontFamily="'Arial'", fontSize="18D"),
          textbox("t", fontFamily="Arial", fontWeight="bold", fontSize="20pt")]
    found, _ = _typo(tmp_path, vs)
    assert found == [
        ("a", ("visual_title font 'Arial' (allowed: Segoe UI Semibold); "
               "visual_title size 18pt (allowed: 12, 14)")),
        ("t", "body font 'Arial' (allowed: Segoe UI, Segoe UI Light)"),
    ]


def test_new_card_callout_and_title_checked(tmp_path: Path):
    body = RULES + "extensions:\n  typography:\n    callout: {font: Segoe UI Semibold, size: 21}\n"
    found, _ = _typo(tmp_path, [new_card("c", fontFamily="'Arial'", fontSize="28D", bold="true")], body)
    assert found == [("c", ("visual_title size 16pt (allowed: 12, 14); callout font 'Arial' "
                            "(allowed: Segoe UI Semibold); callout size 28pt (allowed: 21)"))]


def test_new_card_label_checked(tmp_path: Path):
    body = "extensions:\n  typography:\n    card_label: {font: Segoe UI, size: 12}\n"
    found, _ = _typo(tmp_path, [new_card("c", fontSize="28D")], body)
    assert found == [("c", "card_label size 14pt (allowed: 12)")]
    legacy = visual("old", vtype="card")  # the legacy card's `label` isn't the category label
    legacy["visual"]["objects"] = {"label": [{"properties": {"fontSize": lit("14D")}}]}
    assert _typo(tmp_path / "2", [legacy], body)[0] == []


def test_card_label_theme_default_is_visual_style_over_text_class(tmp_path: Path):
    # probe 07: base theme cardVisual label fontSize 12 outranks textClasses.label 10.5 (face Segoe UI)
    theme = {"textClasses": {"label": {"fontFace": "Segoe UI", "fontSize": 10.5}},
             "visualStyles": {"cardVisual": {"*": {"label": [{"$id": "default", "fontSize": 12,
                                                              "textClass": "label"}]}}}}
    body = "extensions:\n  typography:\n    card_label: {font: Arial, size: 14}\n"
    found, _ = _typo(tmp_path, [], body, theme=theme)
    assert found == [(None, "theme 'T' card_label text: font 'Segoe UI' (allowed: Arial); size 12pt (allowed: 14)")]


def test_theme_text_class_checked(tmp_path: Path):
    found, _ = _typo(tmp_path, [], theme={"textClasses": {"title": {"fontFace": "DIN", "fontSize": 16}}})
    assert found == [(None, ("theme 'T' visual_title text: font 'DIN' (allowed: Segoe UI Semibold); "
                             "size 16pt (allowed: 12, 14)"))]


def test_heading_token_is_noted_not_flagged(tmp_path: Path):
    found, notes = _typo(tmp_path, [textbox("t", fontFamily="Heading", fontSize="8pt")])
    assert found == []
    assert any("Heading not checked" in n for n in notes)


def test_ignored_visual_and_unconfigured_role(tmp_path: Path):
    ign = titled("a", fontFamily="'Arial'")
    ign["annotations"] = [{"name": IGNORE_ANNOTATION, "value": "true"}]
    sub = visual("s", 16, 16, 64, 64)
    sub["visual"]["visualContainerObjects"] = {"subTitle": [{"properties": {"fontSize": lit("40D")}}]}
    assert _typo(tmp_path, [ign, sub])[0] == []  # subtitle isn't configured in RULES


def test_severity_from_check_severity(tmp_path: Path):
    body = RULES + "extensions: {severity: {typography: warning}}\n"
    rd = make_report(tmp_path / "r", {"p": [titled("a", fontFamily="'Arial'")]})
    [f] = [f for f in check_report(read_report(rd), _g(tmp_path, body)).findings if f.rule == "typography"]
    assert f.severity == "warning"
