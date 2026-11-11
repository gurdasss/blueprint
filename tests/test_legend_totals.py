"""A Legend column on clustered charts, `legend: off`, and the table's `totals` (probe 32).

Probe 32 settled in Desktop: a Legend column (role `Series`, no `active`) draws on a clustered
column and bar, also beside a drill-down, while several measures with it, or a second Legend
column, are refused ("too many columns in the Legend bucket"); `objects.legend[0].properties.show
= false` hides a legend; `objects.total[0].properties.totals = false` removes a table's Total row.
"""

import shutil
from pathlib import Path

import pytest

from blueprint.cli import main
from blueprint.pbir import jsonfmt, render
from blueprint.slots import contracts

ROOT = Path(__file__).resolve().parent.parent
GUIDE = ROOT / "guidelines" / "example.yaml"
SPEC = "page: Legends\nlayout: two-up\nvisuals:\n  - {type: header, title: Legends}\n"


@pytest.fixture
def report(tmp_path: Path) -> Path:
    shutil.copytree(ROOT / "fixtures" / "02-card-and-chart", tmp_path / "proj")
    return tmp_path / "proj" / "Fixture.Report"


def _apply(report: Path, body: str) -> int:
    spec = report.parent.parent / "legends.yaml"
    spec.write_text(SPEC + body, encoding="utf-8")
    return main(["apply", str(spec), "--report", str(report), "--guidelines", str(GUIDE)])


def _visual(report: Path, visual_type: str) -> dict:
    for f in report.glob("definition/pages/*/visuals/*/visual.json"):
        doc = jsonfmt.load(f)
        if (doc["visual"]["visualType"] == visual_type
                and any(a.get("name") == "blueprint.visual" for a in doc.get("annotations", []))):
            return doc
    raise AssertionError(f"no Blueprint-made {visual_type}")


def _props(doc: dict, obj: str) -> dict:
    return {k: v["expr"]["Literal"]["Value"] for k, v in doc["visual"]["objects"][obj][0]["properties"].items()}


def chart(vtype: str, slots: str, extra: str = "") -> str:
    return f"  - type: {vtype}\n    title: Chart\n{extra}    slots: {slots}\n"


LEGEND = '{category: "Sales[Country]", value: "[Total Amount]", legend: "Sales[Region]"}'


@pytest.mark.parametrize(("vtype", "pbir"), [("column", "clusteredColumnChart"), ("bar", "clusteredBarChart")])
def test_a_legend_column_is_written_as_desktop_kept_it(report: Path, vtype: str, pbir: str):
    """Series, no `active`, roles alphabetical; bar and column alike (probe 32)."""
    assert _apply(report, chart(vtype, LEGEND)) == 0
    state = _visual(report, pbir)["visual"]["query"]["queryState"]
    assert list(state) == ["Category", "Series", "Y"]
    [legend] = state["Series"]["projections"]
    assert legend["field"]["Column"]["Property"] == "Region"
    assert legend["queryRef"] == "Sales.Region" and "active" not in legend


def test_a_drill_down_may_sit_beside_a_legend(report: Path):
    slots = '{category: ["Sales[Country]", "Sales[Region]"], value: "[Total Amount]", legend: "Sales[Amount]"}'
    assert _apply(report, chart("column", slots)) == 0
    state = _visual(report, "clusteredColumnChart")["visual"]["query"]["queryState"]
    assert [p.get("active") for p in state["Category"]["projections"]] == [True, True]  # a drill-down, both active as probe 28 drew it
    assert "Series" in state


@pytest.mark.parametrize("vtype", ["column", "bar"])
def test_several_measures_with_a_legend_are_refused(report: Path, vtype: str, capsys):
    """Desktop draws only its error for this (probe 32, as for the stacked charts in probe 28)."""
    slots = '{category: "Sales[Country]", value: ["[Total Amount]", "[Total Amount]"], legend: "Sales[Region]"}'
    assert _apply(report, chart(vtype, slots)) == 2
    assert "legend" in capsys.readouterr().err


def test_two_legend_columns_are_refused(report: Path, capsys):
    slots = '{category: "Sales[Country]", value: "[Total Amount]", legend: ["Sales[Region]", "Sales[Amount]"]}'
    assert _apply(report, chart("column", slots)) == 2
    assert "legend" in capsys.readouterr().err


ONE = '{category: "Sales[Country]", value: "[Total Amount]"}'


@pytest.mark.parametrize(("vtype", "pbir"), [("column", "clusteredColumnChart"), ("bar", "clusteredBarChart"),
                                             ("line", "lineChart")])
def test_legend_off_writes_show_false_only(report: Path, vtype: str, pbir: str):
    assert _apply(report, chart(vtype, ONE, "    options: {legend: off}\n")) == 0
    assert _props(_visual(report, pbir), "legend") == {"show": "false"}


def test_a_position_still_writes_only_the_position(report: Path):
    """The shape probes 23, 28 and 31 verified: nothing added beside `position`."""
    assert _apply(report, chart("column", ONE, "    options: {legend: right}\n")) == 0
    assert _props(_visual(report, "clusteredColumnChart"), "legend") == {"position": "'Right'"}


def test_one_legend_option_is_one_state_on_reapply(report: Path):
    """Off, then a position: the position can't be left hidden by the `show: false` off wrote."""
    for value, expected in [("off", {"show": "false"}), ("top", {"position": "'Top'"}),
                            ("off", {"show": "false"})]:
        assert _apply(report, chart("column", ONE, f"    options: {{legend: {value}}}\n")) == 0
        assert _props(_visual(report, "clusteredColumnChart"), "legend") == expected


def test_a_legend_the_spec_leaves_out_is_left_alone(report: Path):
    assert _apply(report, chart("column", ONE, "    options: {legend: off}\n")) == 0
    assert _apply(report, chart("column", ONE)) == 0
    assert _props(_visual(report, "clusteredColumnChart"), "legend") == {"show": "false"}


TABLE = '{columns: ["Sales[Country]", "[Total Amount]"]}'


@pytest.mark.parametrize(("value", "literal"), [("off", "false"), ("on", "true")])
def test_totals_is_written_as_desktop_kept_it(report: Path, value: str, literal: str):
    assert _apply(report, chart("table", TABLE, f'    options: {{totals: "{value}"}}\n')) == 0
    assert _props(_visual(report, "tableEx"), "total") == {"totals": literal}


def test_a_table_with_no_totals_option_writes_no_total_object(report: Path):
    assert _apply(report, chart("table", TABLE)) == 0
    assert "total" not in (_visual(report, "tableEx")["visual"].get("objects") or {})


def test_the_new_options_are_listed_for_spec_writers():
    c = contracts()
    assert list(c["table"].options) == ["totals"]
    assert "legend" in c["column"].slots and "legend" in c["bar"].slots
    assert c["column"].slots["value"].list_excludes == ("legend",)


def test_with_option_clears_only_what_it_is_told_to():
    doc = {"visual": {"objects": {"legend": [{"properties": {
        "position": {"expr": {"Literal": {"Value": "'Top'"}}}, "show": {"expr": {"Literal": {"Value": "true"}}}}}]}}}
    out = render.with_option(doc, "legend", "show", "false")
    assert _props(out, "legend") == {"position": "'Top'", "show": "false"}
    out = render.with_option(doc, "legend", "show", "false", clear=("position",))
    assert _props(out, "legend") == {"show": "false"}
