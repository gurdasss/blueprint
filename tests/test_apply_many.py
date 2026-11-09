"""`bp apply` with several specs or a folder: all are checked before anything is written."""

import shutil
from pathlib import Path

from blueprint.cli import main
from blueprint.pbir.reader import read_report

ROOT = Path(__file__).resolve().parent.parent
GUIDE = ROOT / "guidelines" / "example.yaml"
SPECS = [ROOT / "examples" / "sales-overview.yaml", ROOT / "examples" / "sales-mix.yaml"]


def _project(tmp_path: Path) -> Path:
    shutil.copytree(ROOT / "fixtures" / "02-card-and-chart", tmp_path / "proj")
    return tmp_path / "proj"


def _snapshot(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def _apply(proj: Path, *specs, extra=()) -> int:
    return main(["apply", *map(str, specs), "--report", str(proj), "--guidelines", str(GUIDE), *extra])


def test_several_specs_build_several_pages_and_rerun_is_a_no_op(tmp_path: Path, capsys):
    proj = _project(tmp_path)
    assert _apply(proj, *SPECS) == 0
    out = capsys.readouterr().out
    assert f"== {SPECS[0]}" in out and f"== {SPECS[1]}" in out and "== manifest" in out
    pages = [p.display_name for p in read_report(proj).pages]
    assert pages == ["Overview", "Sales Overview", "Sales Mix"]
    assert _apply(proj, *SPECS) == 0
    assert "A " not in capsys.readouterr().out and _apply(proj, *SPECS, extra=["--dry-run"]) == 0
    assert "M " not in capsys.readouterr().out


def test_a_folder_of_specs_is_applied_in_name_order(tmp_path: Path):
    proj = _project(tmp_path)
    folder = tmp_path / "specs"
    folder.mkdir()
    for s in SPECS:
        shutil.copy(s, folder / s.name)
    assert _apply(proj, folder) == 0
    assert [p.display_name for p in read_report(proj).pages] == ["Overview", "Sales Mix", "Sales Overview"]


def test_one_bad_spec_means_nothing_is_written_and_all_problems_are_listed(tmp_path: Path, capsys):
    proj = _project(tmp_path)
    before = _snapshot(proj)
    bad = tmp_path / "bad.yaml"
    bad.write_text("page: Bad\nvisuals:\n  - {type: card, slots: {value: '[Nope]'}}\n")
    worse = tmp_path / "worse.yaml"
    worse.write_text("page: Worse\nvisuals:\n  - {type: gauge}\n")
    assert _apply(proj, SPECS[0], bad, worse) == 2
    err = capsys.readouterr().err
    assert "2 problem(s) in 3 spec(s); nothing was written" in err
    assert "no measure [Nope]" in err and "'gauge' is not a supported visual type" in err
    assert _snapshot(proj) == before


def test_two_specs_for_the_same_page_are_refused_up_front(tmp_path: Path, capsys):
    proj = _project(tmp_path)
    before = _snapshot(proj)
    twin = tmp_path / "twin.yaml"
    twin.write_text("page: Sales Overview\nvisuals:\n  - {type: header, title: Hi}\n")
    assert _apply(proj, SPECS[0], twin) == 2
    assert "page 'Sales Overview' is also used by" in capsys.readouterr().err
    assert _snapshot(proj) == before


def test_the_same_file_twice_is_applied_once(tmp_path: Path):
    proj = _project(tmp_path)
    assert _apply(proj, SPECS[0], SPECS[0]) == 0


def test_empty_folder_is_an_error(tmp_path: Path, capsys):
    (tmp_path / "none").mkdir()
    assert _apply(_project(tmp_path), tmp_path / "none") == 2
    assert "folder has no *.yaml page specs" in capsys.readouterr().err
