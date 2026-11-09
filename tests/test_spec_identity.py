"""A spec's id links it to the page it builds (gap #3 from the audit).

Before: renaming a spec's `page:` created a second page and orphaned the first silently, and two
specs naming the same page silently shared it.
"""

import json
import shutil
from pathlib import Path

import pytest

from blueprint import spec
from blueprint.cli import main
from blueprint.pbir import jsonfmt
from blueprint.pbir.reader import SPEC_ANNOTATION, read_report
from tests.builders import write

ROOT = Path(__file__).resolve().parent.parent
GUIDE = ROOT / "guidelines" / "example.yaml"
SPEC_TEXT = (ROOT / "examples" / "sales-overview.yaml").read_text()


@pytest.fixture
def report(tmp_path: Path) -> Path:
    shutil.copytree(ROOT / "fixtures" / "02-card-and-chart", tmp_path / "proj")
    return tmp_path / "proj" / "Fixture.Report"


def _spec(tmp_path: Path, name: str, text: str = SPEC_TEXT) -> Path:
    p = tmp_path / name
    p.write_text(text)
    return p


def _apply(report: Path, spec_path: Path, *extra: str) -> int:
    return main(["apply", str(spec_path), "--report", str(report), "--guidelines", str(GUIDE), *extra])


def _blueprint_pages(report: Path):
    return [p for p in read_report(report).pages if p.spec_page]


def _snapshot(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


# --- the id itself -----------------------------------------------------------------------


def test_default_id_is_the_file_name_and_can_be_set(tmp_path: Path):
    assert spec.load(_spec(tmp_path, "Sales Overview v2.yaml")).id == "sales-overview-v2"
    assert spec.load(_spec(tmp_path, "x.yaml", "id: kpis\n" + SPEC_TEXT)).id == "kpis"
    with pytest.raises(spec.SpecError, match="id: 'Bad Id' must be lowercase"):
        spec.load(_spec(tmp_path, "y.yaml", "id: Bad Id\n" + SPEC_TEXT))


def test_new_page_records_its_spec(report: Path, tmp_path: Path):
    _apply(report, _spec(tmp_path, "sales-overview.yaml"))
    [page] = _blueprint_pages(report)
    assert page.spec == "sales-overview"
    m = json.loads((report / ".blueprint.manifest.json").read_text())
    assert next(p for p in m["pages"] if p.get("spec_page"))["spec"] == "sales-overview"


# --- audit scenario 1: renaming the page --------------------------------------------------


def test_renaming_page_in_the_spec_renames_the_page(report: Path, tmp_path: Path, capsys):
    s = _spec(tmp_path, "sales-overview.yaml")
    _apply(report, s)
    [before] = _blueprint_pages(report)
    s.write_text(SPEC_TEXT.replace("page: Sales Overview", "page: Sales Summary"))
    capsys.readouterr()
    assert _apply(report, s) == 0
    assert "rename page 'Sales Overview' -> 'Sales Summary'" in capsys.readouterr().out
    [after] = _blueprint_pages(report)  # still one Blueprint page: no duplicate, no orphan
    assert (after.name, after.display_name, after.spec_page) == (before.name, "Sales Summary", "Sales Summary")
    assert sorted(v.name for v in after.visuals) == sorted(v.name for v in before.visuals)
    capsys.readouterr()
    assert _apply(report, s) == 0
    assert "No changes." in capsys.readouterr().out


def test_renamed_spec_file_keeps_its_page_with_explicit_id(report: Path, tmp_path: Path):
    _apply(report, _spec(tmp_path, "sales-overview.yaml"))
    moved = _spec(tmp_path, "overview-2026.yaml", "id: sales-overview\n" + SPEC_TEXT)
    assert _apply(report, moved) == 0
    assert len(_blueprint_pages(report)) == 1


# --- audit scenario 8: two specs, one page name ---------------------------------------------


def test_another_spec_cannot_silently_take_a_page(report: Path, tmp_path: Path, capsys):
    _apply(report, _spec(tmp_path, "sales-overview.yaml"))
    other = _spec(tmp_path, "team-b.yaml", "page: Sales Overview\nlayout: standard-4-up\n"
                                           "visuals:\n  - type: header\n    title: Team B\n")
    before = _snapshot(report)
    capsys.readouterr()
    assert _apply(report, other) == 2
    err = capsys.readouterr().err
    assert "page 'Sales Overview' is built by spec 'sales-overview', not 'team-b'" in err
    assert "--take-over" in err and "set `id: sales-overview`" in err
    assert _snapshot(report) == before

    assert _apply(report, other, "--take-over") == 0
    [page] = _blueprint_pages(report)
    assert page.spec == "team-b"
    assert "card-1: Blueprint visual" in capsys.readouterr().out  # the old spec's card: kept, warned


def test_rename_onto_another_specs_page_is_refused(report: Path, tmp_path: Path, capsys):
    _apply(report, _spec(tmp_path, "sales-overview.yaml"))
    b = _spec(tmp_path, "team-b.yaml", "page: Team B\nlayout: standard-4-up\n"
                                       "visuals:\n  - type: header\n    title: Team B\n")
    _apply(report, b)
    b.write_text(b.read_text().replace("page: Team B", "page: Sales Overview"))
    capsys.readouterr()
    assert _apply(report, b) == 2
    assert "renames its page to 'Sales Overview', but another Blueprint page already has that name" \
        in capsys.readouterr().err


# --- pages made before spec ids -------------------------------------------------------------


def test_page_without_spec_id_is_adopted_without_moving_anything(report: Path, tmp_path: Path, capsys):
    s = _spec(tmp_path, "sales-overview.yaml")
    _apply(report, s)
    [page] = _blueprint_pages(report)
    doc = jsonfmt.load(report / page.source.path)
    write(report / page.source.path,
          {**doc, "annotations": [a for a in doc["annotations"] if a["name"] != SPEC_ANNOTATION]})
    visuals_before = {v.name: v.source.raw for v in page.visuals}
    capsys.readouterr()
    assert _apply(report, s) == 0
    assert "built by spec 'sales-overview'" in capsys.readouterr().out
    [page] = _blueprint_pages(report)
    assert page.spec == "sales-overview"
    assert {v.name: v.source.raw for v in page.visuals} == visuals_before


def test_two_pages_with_the_same_spec_id_is_an_error(report: Path, tmp_path: Path, capsys):
    s = _spec(tmp_path, "sales-overview.yaml")
    _apply(report, s)
    assert len(_blueprint_pages(report)) == 1
    other = report / "definition/pages/6a692d13619c1d4c0146/page.json"  # the hand-made Overview
    doc = jsonfmt.load(other)
    write(other, {**doc, "annotations": [{"name": SPEC_ANNOTATION, "value": "sales-overview"},
                                         {"name": "blueprint.page", "value": "Other"}]})
    capsys.readouterr()
    assert _apply(report, s) == 2
    assert "several pages are marked as built by spec 'sales-overview'" in capsys.readouterr().err
