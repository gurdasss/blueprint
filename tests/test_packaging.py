"""A plain `pip install` (as the GitHub Action does) must ship every data file Blueprint reads.
An editable install hides a missing one: blueprint/visuals/*.yaml once wasn't packaged.
Markdown (pbir/schema.md) is documentation, not data."""

import tomllib
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "blueprint"


def _covered(rel: PurePosixPath, globs: list[str]) -> bool:
    for g in globs:
        if "**" in g:
            head, tail = g.split("**/", 1)
            if rel.as_posix().startswith(head) and rel.match(tail):
                return True
        elif rel.match(g) and len(rel.parts) == len(PurePosixPath(g).parts):
            return True
    return False


def test_every_data_file_is_package_data():
    config = tomllib.loads((ROOT / "pyproject.toml").read_text())
    globs = config["tool"]["setuptools"]["package-data"]["blueprint"]
    data = [PurePosixPath(p.relative_to(PKG).as_posix()) for p in PKG.rglob("*")
            if p.is_file() and p.suffix not in (".py", ".pyc", ".md") and "__pycache__" not in p.parts]
    assert any(p.parts[0] == "visuals" for p in data)
    assert [p for p in data if not _covered(p, globs)] == []
