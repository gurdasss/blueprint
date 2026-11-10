"""Visual-level aggregation and a per-visual data format (probe 29).

The spec syntax is the long form of a slot: a field plus the decisions about it. The shapes come
from `docs/probes/29-aggregate-format.diff`, where each aggregation was chosen on a *fresh* field
in Desktop (an aggregation changed in place keeps its old queryRef, probe 13).
"""

import json
import shutil
from pathlib import Path

import pytest

from blueprint.cli import main
from blueprint.pbir import jsonfmt, render
from blueprint.pbir.reader import read_report

ROOT = Path(__file__).resolve().parent.parent
GUIDE = ROOT / "guidelines" / "example.yaml"
CURRENCY = '"₹" #,0.###############;"₹" -#,0.###############;"₹" #,0.###############'


@pytest.fixture
def report(tmp_path: Path) -> Path:
    shutil.copytree(ROOT / "fixtures" / "02-card-and-chart", tmp_path / "proj")
    return tmp_path / "proj" / "Fixture.Report"


def _apply(report: Path, spec_text: str, name: str = "agg.yaml") -> int:
    spec = report.parent.parent / name
    spec.write_text(spec_text, encoding="utf-8")
    return main(["apply", str(spec), "--report", str(report), "--guidelines", str(GUIDE)])


def _made(report: Path) -> dict[str, dict]:
    out = {}
    for f in report.glob("definition/pages/*/visuals/*/visual.json"):
        doc = jsonfmt.load(f)
        if any(a.get("name") == "blueprint.visual" for a in doc.get("annotations", [])):
            out[doc["visual"]["visualType"]] = doc
    return out


@pytest.mark.parametrize(("name", "code", "query_ref", "native"), [
    ("sum", 0, "Sum(Sales.Amount)", "Sum of Amount"),
    ("average", 1, "Avg(Sales.Amount)", "Average of Amount"),
    ("distinctcount", 2, "Count(Sales.Amount)", "Count of Amount"),
    ("min", 3, "Min(Sales.Amount)", "Min of Amount"),
    ("max", 4, "Max(Sales.Amount)", "Max of Amount"),
    ("count", 5, "CountNonNull(Sales.Amount)", "Count of Amount"),
])
def test_each_aggregation_is_written_as_desktop_wrote_it(report: Path, name, code, query_ref, native):
    assert _apply(report, "page: Agg\nlayout: two-up\nvisuals:\n"
                          "  - {type: header, title: Agg}\n"
                          "  - type: card\n    title: A\n    slots:\n"
                          f"      value: {{field: \"Sales[Amount]\", aggregate: {name}}}\n") == 0
    [proj] = _made(report)["cardVisual"]["visual"]["query"]["queryState"]["Data"]["projections"]
    assert proj["field"] == {"Aggregation": {
        "Expression": {"Column": {"Expression": {"SourceRef": {"Entity": "Sales"}},
                                  "Property": "Amount"}}, "Function": code}}
    assert (proj["queryRef"], proj["nativeQueryRef"]) == (query_ref, native)


def test_the_format_is_a_string_on_the_projection(report: Path):
    """probe 29: Desktop put the per-field format beside the refs, inside the projection, and the
    string carries the locale's currency symbol — which is why the core takes a string."""
    assert _apply(report, "page: Agg\nlayout: two-up\nvisuals:\n"
                          "  - {type: header, title: Agg}\n"
                          "  - type: card\n    title: A\n    slots:\n"
                          f'      value: {{field: "[Total Amount]", format: \'{CURRENCY}\'}}\n') == 0
    [proj] = _made(report)["cardVisual"]["visual"]["query"]["queryState"]["Data"]["projections"]
    assert proj["format"] == CURRENCY
    assert list(proj) == ["field", "queryRef", "nativeQueryRef", "format"]


def test_a_changed_format_is_rewritten_on_reapply(report: Path):
    spec = ("page: Agg\nlayout: two-up\nvisuals:\n  - {type: header, title: Agg}\n"
            "  - type: card\n    title: A\n    slots:\n      value: {field: \"[Total Amount]\", format: \"%s\"}\n")
    assert _apply(report, spec % "#,0") == 0
    assert _apply(report, spec % "#,0.00") == 0  # only the format differs
    [proj] = _made(report)["cardVisual"]["visual"]["query"]["queryState"]["Data"]["projections"]
    assert proj["format"] == "#,0.00"


def test_reapplying_the_same_format_changes_nothing(report: Path, capsys):
    spec = ("page: Agg\nlayout: two-up\nvisuals:\n  - {type: header, title: Agg}\n"
            "  - type: card\n    title: A\n    slots:\n"
            "      value: {field: \"Sales[Amount]\", aggregate: sum, format: \"#,0.00\"}\n")
    assert _apply(report, spec) == 0
    capsys.readouterr()
    assert _apply(report, spec) == 0
    written = [ln[2:] for ln in capsys.readouterr().out.splitlines() if ln[:2] in ("A ", "M ")]
    assert written == []  # a format that hasn't changed is not a reason to rewrite anything


def test_an_aggregation_round_trips_through_the_reader(report: Path):
    """The reader names the code the same way the writer does, so apply's fingerprint of what it
    wrote matches what it reads back — otherwise every re-run would look edited in Desktop."""
    assert _apply(report, "page: Agg\nlayout: two-up\nvisuals:\n"
                          "  - {type: header, title: Agg}\n"
                          "  - type: card\n    title: A\n    slots:\n"
                          "      value: {field: \"Sales[Amount]\", aggregate: distinctcount}\n") == 0
    page = next(p for p in read_report(report.parent).pages if p.spec_page)
    visual = next(v for v in page.visuals if v.visual_type == "cardVisual")
    [f] = visual.fields["Data"]
    assert (f.kind, f.table, f.name, f.function) == ("aggregation", "Sales", "Amount", "DistinctCount")
    assert str(f) == "DistinctCount(Sales[Amount])"


def test_two_fields_that_desktop_would_name_alike_are_refused(report: Path, capsys):
    """Desktop calls count and distinct count of one column "Count of Amount" both, and adds a
    digit by hand (probe 29). Blueprint doesn't guess that rule."""
    assert _apply(report, "page: Agg\nlayout: two-up\nvisuals:\n"
                          "  - {type: header, title: Agg}\n"
                          "  - type: table\n    title: T\n    slots:\n      columns:\n"
                          "        - {field: \"Sales[Amount]\", aggregate: count}\n"
                          "        - {field: \"Sales[Amount]\", aggregate: distinctcount}\n") == 2
    assert "would both be called 'Count of Amount'" in capsys.readouterr().err


def test_the_manifest_shows_the_aggregation(report: Path):
    assert _apply(report, "page: Agg\nlayout: two-up\nvisuals:\n"
                          "  - {type: header, title: Agg}\n"
                          "  - type: card\n    title: A\n    slots:\n"
                          "      value: {field: \"Sales[Amount]\", aggregate: average}\n") == 0
    data = json.loads((report / ".blueprint.manifest.json").read_text(encoding="utf-8"))
    card = next(v for p in data["pages"] for v in p["visuals"] if v.get("type") == "card")
    assert card["slots"] == {"value": "Average(Sales[Amount])"}


def test_the_aggregation_table_matches_the_reader():
    """One source for the labels: the writer's map and the reader's codes can't drift apart."""
    from blueprint.pbir.reader import AGGREGATE_FUNCTIONS
    assert {code: label for label, (code, _, _) in render.AGGREGATIONS.items()} == AGGREGATE_FUNCTIONS
