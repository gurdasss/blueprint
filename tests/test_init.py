"""`bp init`: a starter set copied out of the package, that works together and never overwrites."""

from __future__ import annotations

from pathlib import Path

import pytest

from blueprint import guidelines, layouts
from blueprint.cli import main
from blueprint.commands import init

ROOT = Path(__file__).resolve().parent.parent

# Each packaged starter file and the repository file it is a copy of. setuptools can only ship
# files inside blueprint/, so the starter set is a copy; this keeps it from drifting.
SOURCES = {
    "guidelines.yaml": ROOT / "template" / "guidelines.template.yaml",
    "layouts/standard-dashboard.yaml": ROOT / "template" / "layout.template.yaml",
    "pages/overview.yaml": ROOT / "template" / "page.template.yaml",
    **{f"layouts/{p.name}": p for p in (ROOT / "guidelines" / "layouts").glob("*.yaml")},
}


def test_the_starter_set_is_exactly_the_template_and_the_shipped_layouts():
    assert sorted(f.as_posix() for f in init.starter_files()) == sorted(SOURCES)
    for rel, source in SOURCES.items():
        assert (init.STARTER_DIR / rel).read_bytes() == source.read_bytes(), (
            f"blueprint/starter/{rel} differs from {source.relative_to(ROOT)}: copy it again")


def test_init_writes_the_starter_set_and_says_what_next(tmp_path: Path, capsys):
    assert main(["init", str(tmp_path / "new")]) == 0
    out = capsys.readouterr().out
    for rel, source in SOURCES.items():
        assert (tmp_path / "new" / rel).read_bytes() == source.read_bytes()
    assert "bp describe --report" in out and "git init" in out


def test_init_never_overwrites(tmp_path: Path, capsys):
    (tmp_path / "pages").mkdir()
    (tmp_path / "pages" / "overview.yaml").write_text("mine")
    assert main(["init", str(tmp_path)]) == 2
    err = capsys.readouterr().err
    assert "would overwrite pages/overview.yaml" in err and "nothing was written" in err
    assert (tmp_path / "pages" / "overview.yaml").read_text() == "mine"
    assert not (tmp_path / "guidelines.yaml").exists()


def test_the_written_starter_set_works_together(tmp_path: Path):
    """The guidelines find every layout through their own search_path, each layout fits them,
    and the page spec names a layout that is there."""
    assert main(["init", str(tmp_path)]) == 0
    g = guidelines.load(tmp_path / "guidelines.yaml")
    names = sorted(p.stem for p in (tmp_path / "layouts").glob("*.yaml"))
    assert len(names) == 7 and g.layouts.default in names
    for name in names:
        layout = layouts.load(name, g.layouts.search_path)
        assert (layout.width, layout.height) == (g.canvas.width, g.canvas.height), name
        assert layouts.conflicts(layout, g.spacing.grid, g.spacing.margin, g.spacing.gutter) == [], name
    spec_layout = next(line.split(":", 1)[1].strip() for line in
                       (tmp_path / "pages" / "overview.yaml").read_text().splitlines()
                       if line.startswith("layout:"))
    assert spec_layout in names


@pytest.mark.parametrize("args", [["init"], ["init", "."]])
def test_init_defaults_to_the_current_folder(tmp_path: Path, monkeypatch, args):
    monkeypatch.chdir(tmp_path)
    assert main(args) == 0
    assert (tmp_path / "guidelines.yaml").is_file()


def test_the_pages_folder_applies_as_a_folder_of_specs(tmp_path: Path, capsys):
    """`bp apply pages` reads only page specs: guidelines and layouts live outside that folder,
    so the run gets as far as checking the spec's (invented) field names against the model."""
    import shutil
    assert main(["init", str(tmp_path / "s")]) == 0
    shutil.copytree(ROOT / "fixtures" / "02-card-and-chart", tmp_path / "report")
    capsys.readouterr()
    assert main(["apply", str(tmp_path / "s" / "pages"), "--report", str(tmp_path / "report"),
                 "--guidelines", str(tmp_path / "s" / "guidelines.yaml"), "--dry-run"]) == 2
    err = capsys.readouterr().err
    assert "field references don't match the semantic model" in err and "unknown key" not in err
