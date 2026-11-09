"""page.require_title / page.title_region: checked on pages built from a spec only."""

import shutil
from pathlib import Path

import pytest

from blueprint import guidelines
from blueprint.cli import main
from blueprint.guidelines import GuidelinesError
from blueprint.pbir.reader import read_report
from blueprint.validate import check_report

ROOT = Path(__file__).resolve().parent.parent
LAYOUTS = ROOT / "guidelines" / "layouts"


def _setup(tmp_path: Path, page_rules: str) -> tuple[Path, Path]:
    shutil.copytree(ROOT / "fixtures" / "02-card-and-chart", tmp_path / "proj")
    g = tmp_path / "g.yaml"
    g.write_text(f"page: {page_rules}\nlayouts: {{search_path: ['{LAYOUTS}']}}\n")
    return tmp_path / "proj", g


def _apply(tmp_path: Path, proj: Path, g: Path, visuals: str, capsys) -> str:
    s = tmp_path / "t.yaml"
    s.write_text(f"page: T\nlayout: standard-4-up\nvisuals:\n{visuals}")
    assert main(["apply", str(s), "--report", str(proj), "--guidelines", str(g)]) == 0
    return capsys.readouterr().out


def _titles(proj: Path, g: Path):
    result = check_report(read_report(proj), guidelines.load(g))
    return [f for f in result.findings if f.rule == "title"], result.notes


CARD = "  - {type: card, slots: {value: '[Total Amount]'}}\n"
HEADER = "  - {type: header, title: Hi}\n"


def test_spec_page_without_a_header_fails_and_apply_warns(tmp_path: Path, capsys):
    proj, g = _setup(tmp_path, "{require_title: true}")
    out = _apply(tmp_path, proj, g, CARD, capsys)
    assert "no header: the guidelines require a page title" in out
    [f], notes = _titles(proj, g)
    assert (f.severity, f.visual) == ("error", None) and f.message.startswith("no header")
    assert "title rules not checked on 1 page(s) not built from a spec" in " ".join(notes)


def test_spec_page_with_a_header_passes(tmp_path: Path, capsys):
    proj, g = _setup(tmp_path, "{require_title: true, title_region: header}")
    out = _apply(tmp_path, proj, g, HEADER + CARD, capsys)
    assert "page title" not in out and "title_region" not in out
    assert _titles(proj, g)[0] == []


def test_header_outside_the_title_region_fails(tmp_path: Path, capsys):
    proj, g = _setup(tmp_path, "{title_region: header}")
    out = _apply(tmp_path, proj, g, "  - {type: header, title: Hi, region: main}\n", capsys)
    assert "header-1: header placed in region main#1, but page.title_region is 'header'" in out
    [f], _ = _titles(proj, g)
    assert f.visual is not None and "header is in region main#1" in f.message


def test_ignored_header_does_not_count(tmp_path: Path, capsys):
    proj, g = _setup(tmp_path, "{require_title: true}")
    _apply(tmp_path, proj, g, HEADER + CARD, capsys)
    report = read_report(proj)
    [v] = [v for p in report.pages for v in p.visuals if v.visual_type == "textbox" and v.spec_id]
    v.ignored = True
    found = [f for f in check_report(report, guidelines.load(g)).findings if f.rule == "title"]
    assert [f.message[:9] for f in found] == ["no header"]


def test_off_by_default(tmp_path: Path, capsys):
    proj, g = _setup(tmp_path, "{max_visuals: null}")
    _apply(tmp_path, proj, g, CARD, capsys)
    findings, notes = _titles(proj, g)
    assert findings == [] and not any("title rules" in n for n in notes)


@pytest.mark.parametrize("bad", ["3", "''", "[header]"])
def test_title_region_must_be_a_role(tmp_path: Path, bad):
    g = tmp_path / "g.yaml"
    g.write_text(f"page: {{title_region: {bad}}}\n")
    with pytest.raises(GuidelinesError, match="page.title_region must be a region role"):
        guidelines.load(g)
