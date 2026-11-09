"""`bp apply`: golden output on the Desktop-built fixture, plus re-apply and refusal behaviour.

The golden tree under tests/golden/ holds exactly the files apply creates or modifies. When an
intended change alters the output, regenerate it with BLUEPRINT_UPDATE_GOLDEN=1 and review the
diff like any other change.
"""

import os
import re
import shutil
from pathlib import Path

import pytest

from blueprint.cli import main
from blueprint.pbir import jsonfmt
from blueprint.pbir.reader import read_report
from tests.builders import make_report, visual, write

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "examples" / "sales-overview.yaml"
GUIDE = ROOT / "guidelines" / "example.yaml"
GOLDEN = Path(__file__).resolve().parent / "golden" / "02-card-and-chart+sales-overview"


def _copy_fixture(tmp_path: Path) -> Path:
    dest = tmp_path / "proj"
    shutil.copytree(ROOT / "fixtures" / "02-card-and-chart", dest)
    return dest / "Fixture.Report"


def _snapshot(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def _apply(report: Path, *extra: str, spec: Path = SPEC, guide: Path | None = GUIDE) -> int:
    args = ["apply", str(spec), "--report", str(report), *extra]
    return main(args + (["--guidelines", str(guide)] if guide else []))


def test_golden_output(tmp_path: Path, capsys):
    report = _copy_fixture(tmp_path)
    before = _snapshot(report)
    assert _apply(report) == 0
    after = _snapshot(report)
    changed = {k: v for k, v in after.items() if before.get(k) != v}
    if os.environ.get("BLUEPRINT_UPDATE_GOLDEN"):
        shutil.rmtree(GOLDEN, ignore_errors=True)
        for rel, data in changed.items():
            (GOLDEN / rel).parent.mkdir(parents=True, exist_ok=True)
            (GOLDEN / rel).write_bytes(data)
    expected = _snapshot(GOLDEN)
    assert sorted(changed) == sorted(expected), "set of written files changed"
    for rel in expected:
        assert changed[rel] == expected[rel], f"{rel} differs from golden output"
    assert all(k in after for k in before), "apply must never delete files"


def test_reapply_is_a_no_op_and_dry_run_writes_nothing(tmp_path: Path, capsys):
    report = _copy_fixture(tmp_path)
    before = _snapshot(report)
    assert _apply(report, "--dry-run") == 0
    assert "A definition/pages/" in capsys.readouterr().out
    assert _snapshot(report) == before
    assert _apply(report) == 0
    once = _snapshot(report)
    capsys.readouterr()
    assert _apply(report) == 0
    assert "No changes." in capsys.readouterr().out
    assert _snapshot(report) == once


def _blueprint_visual(report: Path, spec_id: str):
    r = read_report(report)
    page = next(p for p in r.pages if p.spec_page)
    return r, page, next(v for v in page.visuals if v.spec_id == spec_id)


def test_reapply_restores_layout_position_and_updates_title(tmp_path: Path, capsys):
    report = _copy_fixture(tmp_path)
    _apply(report)
    _, _, card = _blueprint_visual(report, "card-1")
    path = report / card.source.path
    doc = jsonfmt.load(path)  # simulate a Desktop drag and a hand-set title colour
    doc["position"] = {**doc["position"], "x": 40.5, "width": 600.25}
    doc["visual"]["visualContainerObjects"]["title"][0]["properties"]["fontColor"] = {
        "solid": {"color": {"expr": {"Literal": {"Value": "'#333333'"}}}}}
    write(path, doc)
    retitled = tmp_path / "s.yaml"
    retitled.write_text(SPEC.read_text().replace("title: Total", "title: Grand total"))
    capsys.readouterr()
    assert _apply(report, spec=retitled) == 0
    out = capsys.readouterr().out
    assert "x 40.50 -> 16" in out and "title 'Total' -> 'Grand total'" in out
    _, _, card = _blueprint_visual(report, "card-1")
    assert (card.rect.x, card.rect.width, card.title) == (16, 616, "Grand total")
    props = card.source.data["visual"]["visualContainerObjects"]["title"][0]["properties"]
    assert "fontColor" in props  # formatting Blueprint doesn't own is kept


def test_hand_placed_visuals_on_the_fixture_are_never_touched(tmp_path: Path):
    report = _copy_fixture(tmp_path)
    overview = report / "definition/pages/6a692d13619c1d4c0146"
    before = _snapshot(overview)
    _apply(report)
    _apply(report)
    assert _snapshot(overview) == before


@pytest.mark.parametrize(("old", "new", "match"), [
    ('value: "[Total Amount]"\n\n  - type: column', 'value: "[Other]"\n\n  - type: column',
     r"visuals\[1\].slots.value: no measure \[Other\] in the semantic model"),
    ('- "Sales[Region]"', '- "Sales[City]"', r"table 'Sales' has no column 'City'"),
    ('- "Sales[Region]"', '- "Geo[Region]"', r"no table 'Geo' in the semantic model \(tables: Sales\)"),
])
def test_bindings_are_checked_against_the_model_before_writing(tmp_path: Path, capsys, old, new, match):
    report = _copy_fixture(tmp_path)
    before = _snapshot(report)
    spec = tmp_path / "s.yaml"
    spec.write_text(SPEC.read_text().replace(old, new, 1))
    assert _apply(report, spec=spec) == 2
    assert re.search(match, capsys.readouterr().err)
    assert _snapshot(report) == before


def test_changed_bindings_or_type_are_refused(tmp_path: Path, capsys):
    report = _copy_fixture(tmp_path)
    _apply(report)
    spec = tmp_path / "s.yaml"
    spec.write_text(SPEC.read_text().replace('        - "Sales[Region]"\n', ""))
    assert _apply(report, spec=spec) == 2
    assert "field bindings differ from the report" in capsys.readouterr().err
    spec.write_text(SPEC.read_text().replace("type: card\n", "type: column\n    id: card-1\n")
                    .replace('value: "[Total Amount]"\n\n  - type: column',
                             'category: "Sales[Country]"\n      value: "[Total Amount]"\n\n  - type: column'))
    assert _apply(report, spec=spec) == 2
    assert "is a cardVisual in the report but column" in capsys.readouterr().err


def test_visual_removed_from_spec_is_kept_with_a_warning(tmp_path: Path, capsys):
    report = _copy_fixture(tmp_path)
    _apply(report)
    spec = tmp_path / "s.yaml"
    text = SPEC.read_text()
    spec.write_text(text[: text.index("  - type: column")])
    capsys.readouterr()
    assert _apply(report, spec=spec) == 0
    assert "column-1: Blueprint visual" in capsys.readouterr().out
    _blueprint_visual(report, "column-1")  # still there


def test_ignored_entries_are_not_created(tmp_path: Path):
    report = _copy_fixture(tmp_path)
    spec = tmp_path / "s.yaml"
    spec.write_text(SPEC.read_text().replace("  - type: column\n", "  - type: column\n    blueprint: ignore\n"))
    _apply(report, spec=spec)
    page = next(p for p in read_report(report).pages if p.spec_page)
    assert sorted(v.spec_id for v in page.visuals) == ["card-1", "header-1"]


def test_resized_page_is_an_error_not_a_rescale(tmp_path: Path, capsys):
    report = _copy_fixture(tmp_path)
    _apply(report)
    page = next(p for p in read_report(report).pages if p.spec_page)
    doc = jsonfmt.load(report / page.source.path)
    write(report / page.source.path, {**doc, "width": 1920, "height": 1080})
    assert _apply(report) == 2
    assert "is 1920x1080 but layout 'standard-4-up' is 1280x720" in capsys.readouterr().err


def test_overlap_with_hand_placed_visual_warns(tmp_path: Path, capsys):
    report = _copy_fixture(tmp_path)
    _apply(report)
    page = next(p for p in read_report(report).pages if p.spec_page)
    hand = visual("handplaced00000000aa", 20, 240, 100, 100)
    write(report / "definition/pages" / page.name / "visuals" / hand["name"] / "visual.json", hand)
    spec = tmp_path / "s.yaml"
    spec.write_text(SPEC.read_text().replace("type: card\n", "type: card\n    id: kpi\n"))
    capsys.readouterr()
    assert _apply(report, spec=spec) == 0
    out = capsys.readouterr().out
    assert "kpi: overlaps hand-placed visual handplaced00000000aa" in out
    assert "card-1: Blueprint visual" in out  # the old id is now an orphan, kept


def test_no_layout_and_by_connection_are_errors(tmp_path: Path, capsys):
    report = _copy_fixture(tmp_path)
    spec = tmp_path / "s.yaml"
    spec.write_text(SPEC.read_text().replace("layout: standard-4-up\n", ""))
    assert _apply(report, spec=spec, guide=None) == 2
    assert "no layout" in capsys.readouterr().err
    rd = make_report(tmp_path / "conn", {"p": []})
    write(rd / "definition.pbir", {"version": "4.0", "datasetReference": {"byConnection": {"connectionString": "x"}}})
    assert _apply(rd) == 2
    assert "report uses byConnection" in capsys.readouterr().err
