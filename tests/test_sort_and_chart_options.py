"""A visual's sort, and the chart options the core's chart types share (probe 31).

Probe 31 settled two things in Desktop: the clustered bar and the line take the column chart's
`labels`/`legend` options, and a sort the *user* chooses carries no `isDefaultSort` — that flag
marks only the sort Desktop adds by itself, and it doesn't come back when the sort is set to what
Desktop would have chosen anyway.
"""

import shutil
from pathlib import Path

import pytest

from blueprint.cli import main
from blueprint.pbir import jsonfmt
from blueprint.slots import contracts

ROOT = Path(__file__).resolve().parent.parent
GUIDE = ROOT / "guidelines" / "example.yaml"


@pytest.fixture
def report(tmp_path: Path) -> Path:
    shutil.copytree(ROOT / "fixtures" / "02-card-and-chart", tmp_path / "proj")
    return tmp_path / "proj" / "Fixture.Report"


def _apply(report: Path, body: str) -> int:
    spec = report.parent.parent / "sorted.yaml"
    spec.write_text("page: Sorted\nlayout: two-up\nvisuals:\n"
                    "  - {type: header, title: Sorted}\n" + body, encoding="utf-8")
    return main(["apply", str(spec), "--report", str(report), "--guidelines", str(GUIDE)])


def _visual(report: Path, visual_type: str) -> dict:
    for f in report.glob("definition/pages/*/visuals/*/visual.json"):
        doc = jsonfmt.load(f)
        if (doc["visual"]["visualType"] == visual_type
                and any(a.get("name") == "blueprint.visual" for a in doc.get("annotations", []))):
            return doc
    raise AssertionError(f"no Blueprint-made {visual_type}")


COLUMN = ("  - type: column\n    title: By country\n"
          "    slots: {category: \"Sales[Country]\", value: \"[Total Amount]\"}\n")


def test_a_spec_sort_is_written_without_isdefaultsort(report: Path):
    """probe 31: `isDefaultSort: true` marks Desktop's own choice. A sort the spec asked for is
    the user's choice, so the flag stays off — otherwise Desktop would treat it as replaceable."""
    assert _apply(report, COLUMN + "    sort: {by: \"[Total Amount]\", direction: descending}\n") == 0
    sort = _visual(report, "clusteredColumnChart")["visual"]["query"]["sortDefinition"]
    assert sort == {"sort": [{"field": {"Measure": {
        "Expression": {"SourceRef": {"Entity": "Sales"}}, "Property": "Total Amount"}},
        "direction": "Descending"}]}
    assert "isDefaultSort" not in sort


def test_a_sort_on_a_column_ascending(report: Path):
    assert _apply(report, COLUMN + "    sort: {by: \"Sales[Country]\", direction: ascending}\n") == 0
    [entry] = _visual(report, "clusteredColumnChart")["visual"]["query"]["sortDefinition"]["sort"]
    assert entry["field"]["Column"]["Property"] == "Country" and entry["direction"] == "Ascending"


def test_a_changed_sort_is_rewritten_on_reapply(report: Path):
    assert _apply(report, COLUMN + "    sort: {by: \"[Total Amount]\", direction: descending}\n") == 0
    assert _apply(report, COLUMN + "    sort: {by: \"Sales[Country]\", direction: ascending}\n") == 0
    [entry] = _visual(report, "clusteredColumnChart")["visual"]["query"]["sortDefinition"]["sort"]
    assert entry["field"]["Column"]["Property"] == "Country" and entry["direction"] == "Ascending"


def test_reapplying_the_same_sort_changes_nothing(report: Path, capsys):
    body = COLUMN + "    sort: {by: \"[Total Amount]\", direction: descending}\n"
    assert _apply(report, body) == 0
    capsys.readouterr()
    assert _apply(report, body) == 0
    assert [ln for ln in capsys.readouterr().out.splitlines() if ln[:2] in ("A ", "M ")] == []


def test_a_spec_without_a_sort_leaves_desktops_alone(report: Path):
    """A spec that says nothing about sorting is not a spec that says "no sort": Desktop's own
    default sort, or the user's, stays."""
    assert _apply(report, COLUMN) == 0
    doc = _visual(report, "clusteredColumnChart")
    assert "sortDefinition" not in doc["visual"]["query"]  # Blueprint writes none of its own
    # Desktop would add its default here; a later apply must not remove it
    doc["visual"]["query"]["sortDefinition"] = {
        "sort": [{"field": {"Column": {"Expression": {"SourceRef": {"Entity": "Sales"}},
                                       "Property": "Country"}}, "direction": "Ascending"}],
        "isDefaultSort": True}
    path = next(f for f in report.glob("definition/pages/*/visuals/*/visual.json")
                if jsonfmt.load(f)["name"] == doc["name"])
    path.write_bytes(jsonfmt.dump_bytes(doc))
    assert _apply(report, COLUMN) == 0
    assert _visual(report, "clusteredColumnChart")["visual"]["query"]["sortDefinition"]["isDefaultSort"] is True


def test_a_sort_on_a_field_the_visual_does_not_bind_is_refused(report: Path, capsys):
    assert _apply(report, COLUMN + "    sort: {by: \"Sales[Region]\", direction: ascending}\n") == 2
    assert "isn't bound by this visual" in capsys.readouterr().err


def test_a_sort_on_a_field_missing_from_the_model_is_refused(report: Path, capsys):
    body = ("  - type: table\n    title: T\n"
            "    slots: {columns: [\"Sales[Country]\", \"[Total Amount]\"]}\n"
            "    sort: {by: \"Sales[Nope]\", direction: ascending}\n")
    assert _apply(report, body) == 2
    err = capsys.readouterr().err
    assert "sort.by" in err and "Nope" in err


@pytest.mark.parametrize("vtype", ["column", "bar", "line"])
def test_the_core_chart_types_share_labels_and_legend(vtype: str):
    """probe 23 verified them on column, probe 31 on bar and line: the three behave the same."""
    options = contracts()[vtype].options
    assert sorted(options) == ["labels", "legend"]
    assert sorted(options["legend"].values) == ["bottom", "left", "off", "right", "top"]  # probe 32


@pytest.mark.parametrize("vtype", ["bar", "line"])
def test_the_options_reach_the_visual(report: Path, vtype: str):
    assert _apply(report, f"  - type: {vtype}\n    title: Chart\n"
                          "    options: {labels: on, legend: right}\n"
                          "    slots: {category: \"Sales[Country]\", value: \"[Total Amount]\"}\n") == 0
    objects = _visual(report, contracts()[vtype].visual_type)["visual"]["objects"]
    assert objects["labels"][0]["properties"]["show"]["expr"]["Literal"]["Value"] == "true"
    assert objects["legend"][0]["properties"]["position"]["expr"]["Literal"]["Value"] == "'Right'"


TABLE = ("  - type: table\n    title: Detail\n    slots:\n      columns:\n"
         "        - \"Sales[Country]\"\n"
         "        - {field: \"Sales[Amount]\", aggregate: sum}\n")
AGG_SORT = {"Aggregation": {"Expression": {"Column": {"Expression": {"SourceRef": {"Entity": "Sales"}},
                                                      "Property": "Amount"}}, "Function": 0}}


@pytest.mark.parametrize("by", ['"Sales[Amount]"', '{field: "Sales[Amount]", aggregate: sum}'])
def test_a_sort_on_an_aggregated_column_writes_the_aggregation(report: Path, by: str):
    """probe 41: Desktop stores a sort on `Sum of Profit` as an Aggregation field with the
    projection's Function code, no isDefaultSort. A plain `by` follows the visual's only aggregate."""
    assert _apply(report, TABLE + f"    sort: {{by: {by}, direction: descending}}\n") == 0
    sort = _visual(report, "tableEx")["visual"]["query"]["sortDefinition"]
    assert sort == {"sort": [{"field": AGG_SORT, "direction": "Descending"}]}


def test_a_sort_on_the_wrong_aggregate_is_refused(report: Path):
    before = {f: f.read_bytes() for f in report.rglob("*.json")}
    assert _apply(report, TABLE + "    sort: {by: {field: \"Sales[Amount]\", aggregate: max},"
                                  " direction: descending}\n") != 0
    assert before == {f: f.read_bytes() for f in report.rglob("*.json")}  # refused, nothing written


def test_reapplying_an_aggregated_sort_is_a_no_op(report: Path):
    body = TABLE + "    sort: {by: \"Sales[Amount]\", direction: descending}\n"
    assert _apply(report, body) == 0
    before = {f: f.read_bytes() for f in report.rglob("*.json")}
    assert _apply(report, body) == 0
    assert before == {f: f.read_bytes() for f in report.rglob("*.json")}
