import json
import shutil
from pathlib import Path

import pytest

from blueprint import guidelines, manifest
from blueprint.cli import main
from blueprint.pbir import jsonfmt
from blueprint.pbir.reader import read_report
from tests.builders import write

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "examples" / "sales-overview.yaml"
GUIDE = ROOT / "guidelines" / "example.yaml"


@pytest.fixture
def report(tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1767225600")
    shutil.copytree(ROOT / "fixtures" / "02-card-and-chart", tmp_path / "proj")
    return tmp_path / "proj" / "Fixture.Report"


def _read(report: Path) -> dict:
    return json.loads((report / manifest.FILE).read_text())


def _run(*args: str) -> int:
    return main(list(args))


def test_manifest_of_a_hand_built_report(report: Path, capsys):
    assert _run("manifest", "--report", str(report)) == 0
    m = _read(report)
    assert (m["guidelines"], m["generated_at"]) == ({"name": "Blueprint defaults", "version": 1},
                                                    "2026-01-01T00:00:00Z")
    [page] = m["pages"]
    assert (page["name"], page["size"], "layout" in page) == ("Overview", {"w": 1920, "h": 1080}, False)
    by_type = {v["type"]: v for v in page["visuals"]}
    assert by_type["cardVisual"]["slots"] == {"Data": "[Total Amount]"}
    assert by_type["clusteredColumnChart"]["slots"] == {"Category": ["Sales[Country]", "Sales[Region]"],
                                                        "Y": "[Total Amount]"}
    assert all(v["managed"] is False for v in page["visuals"])
    assert by_type["cardVisual"]["position"] == {"x": 10.29, "y": 0, "w": 695.71, "h": 741}


def test_apply_writes_manifest_with_spec_names_layout_and_regions(report: Path):
    _run("apply", str(SPEC), "--report", str(report), "--guidelines", str(GUIDE))
    page = next(p for p in _read(report)["pages"] if p.get("spec_page"))
    assert (page["layout"], page["built_with"]) == ("two-up", "Example Corp Reporting Standard@1")
    assert [(v["type"], v["spec_id"], v["region"], v["title"]) for v in page["visuals"]] == [
        ("header", "header-1", "header#1", "Sales Overview"),
        ("card", "card-1", "main#1", "Total"),
        ("column", "column-1", "main#2", "Sales by Geography")]
    assert page["visuals"][2]["slots"] == {"category": ["Sales[Country]", "Sales[Region]"],
                                           "value": "[Total Amount]"}


def test_regenerating_unchanged_report_is_a_no_op_even_later(report: Path, capsys, monkeypatch):
    _run("manifest", "--report", str(report))
    before = (report / manifest.FILE).read_bytes()
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1798761600")  # a year later
    capsys.readouterr()
    _run("manifest", "--report", str(report))
    assert "No changes." in capsys.readouterr().out
    assert (report / manifest.FILE).read_bytes() == before


def test_manifest_follows_the_report_and_dry_run_writes_nothing(report: Path, capsys, monkeypatch):
    _run("manifest", "--report", str(report))
    visual = next((report / "definition/pages").rglob("visual.json"))
    doc = jsonfmt.load(visual)
    write(visual, {**doc, "position": {**doc["position"], "x": 500}})
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1798761600")
    before = (report / manifest.FILE).read_bytes()
    _run("manifest", "--report", str(report), "--dry-run")
    assert (report / manifest.FILE).read_bytes() == before
    _run("manifest", "--report", str(report))
    m = _read(report)
    assert m["generated_at"] == "2027-01-01T00:00:00Z"
    assert any(v["position"]["x"] == 500 for p in m["pages"] for v in p["visuals"])


def test_full_workflow(report: Path, capsys):
    """apply -> Desktop-style drag -> check notices -> re-apply restores -> clean."""
    apply = ["apply", str(SPEC), "--report", str(report), "--guidelines", str(GUIDE)]
    check = ["check", "--report", str(report), "--guidelines", str(GUIDE), "--json"]
    assert _run(*apply) == 0
    capsys.readouterr()

    page = next(p for p in read_report(report).pages if p.spec_page)
    card = next(v for v in page.visuals if v.spec_id == "card-1")
    doc = jsonfmt.load(report / card.source.path)  # probe 05: a drag writes sub-pixel floats
    write(report / card.source.path, {**doc, "position": {**doc["position"], "x": 29.07, "width": 602.33}})

    _run(*check)
    out = json.loads(capsys.readouterr().out)
    grid = [f for f in out["findings"] if f["rule"] == "grid" and f["page"] == page.name]
    assert [f["visual"] for f in grid] == [card.name]
    assert any("out of date" in n for n in out["notes"])

    assert _run(*apply) == 0
    capsys.readouterr()
    _run(*check)
    out = json.loads(capsys.readouterr().out)
    assert not [f for f in out["findings"] if f["page"] == page.name and f["rule"] in ("grid", "bounds", "overlap")]
    assert not any("out of date" in n or "built with" in n for n in out["notes"])

    capsys.readouterr()
    assert _run(*apply) == 0
    assert "No changes." in capsys.readouterr().out


def test_check_notes_when_guidelines_changed_since_build(report: Path, tmp_path: Path, capsys):
    _run("apply", str(SPEC), "--report", str(report), "--guidelines", str(GUIDE))
    newer = tmp_path / "g2.yaml"  # elsewhere, so point it at the repo's layouts explicitly
    newer.write_text(GUIDE.read_text().replace("version: 1", "version: 2")
                     .replace('search_path: ["layouts"]', f'search_path: ["{ROOT / "guidelines" / "layouts"}"]'))
    capsys.readouterr()
    _run("check", "--report", str(report), "--guidelines", str(newer), "--json")
    notes = json.loads(capsys.readouterr().out)["notes"]
    assert "Sales Overview: built with guidelines Example Corp Reporting Standard@1, checked against " \
           "Example Corp Reporting Standard@2" in notes
    # Re-applying with the new guidelines records them on the page (and in the manifest).
    _run("apply", str(SPEC), "--report", str(report), "--guidelines", str(newer))
    assert next(p for p in read_report(report).pages if p.spec_page).guidelines == "Example Corp Reporting Standard@2"


def test_manifest_build_is_pure(report: Path):
    r = read_report(report)
    rules = guidelines.load()
    assert manifest.build(r, rules, "t") == manifest.build(read_report(report), rules, "t")


def test_fmt_keeps_an_existing_manifest_current_but_never_creates_one(report: Path, capsys):
    assert _run("fmt", "--report", str(report)) == 0
    assert not (report / manifest.FILE).exists()
    _run("manifest", "--report", str(report))
    _run("fmt", "--report", str(report), "--set", "spacing.grid=16")
    capsys.readouterr()
    _run("check", "--report", str(report), "--json")
    assert not any("out of date" in n for n in json.loads(capsys.readouterr().out)["notes"])
