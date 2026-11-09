from pathlib import Path

from blueprint.model import ColorUse
from blueprint.pbir import formatting, jsonfmt
from blueprint.pbir.reader import read_report
from tests.builders import add_theme, hex_color, make_report, theme_color, write


def test_colors_in_finds_every_observed_shape():
    doc = {
        "visualType": "pieChart",
        "objects": {
            "dataPoint": [{"properties": {"fill": theme_color(2, 0.4)}, "selector": {"data": []}}],
            "labels": [{"properties": {"color": hex_color("#e15759")}}],
            "general": [{"properties": {"paragraphs": [{"textRuns": [
                {"value": "x", "textStyle": {"fontSize": "28pt", "color": "#f7c1a4"}}]}]}}],
        },
        "visualContainerObjects": {
            "title": [{"properties": {"fontColor": {"solid": {"color": {"expr": {"Measure": {}}}}}}}],
            "background": [{"properties": {"color": hex_color("#000000")}}],
        },
    }
    assert formatting.colors_in(doc) == [
        ColorUse("dataPoint.fill", "theme", "ColorId 2, Percent 0.4"),
        ColorUse("labels.color", "hex", "#E15759"),
        ColorUse("text", "hex", "#F7C1A4"),
        ColorUse("title.fontColor", "expression", "Measure"),
        ColorUse("background.color", "hex", "#000000"),
    ]


def test_theme_layers_resolved_through_resource_packages(tmp_path: Path):
    rd = make_report(tmp_path, {"p": []})
    add_theme(rd, "base", "Base1", {"dataColors": ["#111111"], "background": "#FFFFFF"}, folder="BaseThemes")
    add_theme(rd, "custom", "Mine", {"dataColors": ["#222222"]})
    add_theme(rd, "custom", "Gone", None)  # replaces Mine in themeCollection; file missing
    r = read_report(rd)
    assert [(t.layer, t.name, t.missing) for t in r.themes] == [("base", "Base1", False), ("custom", "Gone", True)]
    assert r.themes[0].data_colors == ("#111111",)


def test_theme_path_escaping_report_is_not_followed(tmp_path: Path):
    rd = make_report(tmp_path / "r", {"p": []})
    outside = rd.parent / "evil.json"  # where StaticResources/SharedResources/../../../ lands
    write(outside, {"dataColors": ["#4E79A7", "#F28E2B"], "background": "#FFFFFF", "foreground": "#333333"})
    add_theme(rd, "custom", "Evil", None)
    (rd / "StaticResources/SharedResources").mkdir(parents=True)  # exists in real reports; `..` needs it
    doc = jsonfmt.load(rd / "definition/report.json")
    doc["resourcePackages"][0]["items"][0]["path"] = "../../../evil.json"
    write(rd / "definition/report.json", doc)
    [t] = read_report(rd).themes
    assert t.missing


def test_sample_theme_is_missing(retail_report: Path):
    [t] = read_report(retail_report).themes
    assert (t.layer, t.name, t.missing) == ("custom", "Concourse", True)
