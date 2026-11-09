"""`bp fmt` twice must equal `bp fmt` once. README design principle 3: a test, not an aspiration."""

import shutil
from pathlib import Path

from blueprint.cli import main
from blueprint.pbir import schemas
from blueprint.pbir.reader import read_report
from tests.builders import make_report, visual


def _snapshot(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def _fmt_twice(report: Path, capsys) -> tuple[dict, dict, dict]:
    original = _snapshot(report)
    assert main(["fmt", "--report", str(report)]) == 0
    once = _snapshot(report)
    capsys.readouterr()
    assert main(["fmt", "--report", str(report)]) == 0
    assert "No changes." in capsys.readouterr().out
    return original, once, _snapshot(report)


def test_fmt_idempotent_synthetic(tmp_path: Path, capsys):
    rd = make_report(tmp_path, {"p": [visual("a", 3.3, 7.7, 101.1, 49.9), visual("b", 200, 5, 64, 64)]})
    original, once, twice = _fmt_twice(rd, capsys)
    assert once != original
    assert once == twice


def test_dry_run_writes_nothing(tmp_path: Path, capsys):
    rd = make_report(tmp_path, {"p": [visual("a", 3.3, 7.7, 101.1, 49.9)]})
    before = _snapshot(rd)
    assert main(["fmt", "--report", str(rd), "--dry-run"]) == 0
    assert "a: x 3.30 -> 0" in capsys.readouterr().out
    assert _snapshot(rd) == before


def test_fmt_idempotent_and_valid_on_sample(real_report: Path, tmp_path: Path, capsys):
    copy = tmp_path / real_report.name
    shutil.copytree(real_report, copy)
    original, once, twice = _fmt_twice(copy, capsys)
    assert once == twice
    changed = [k for k in original if original[k] != once[k]]
    assert changed and all(k.endswith("/visual.json") for k in changed)
    for doc in read_report(copy).source.documents.values():
        if doc.schema is not None:
            assert schemas.validate(doc.data, doc.schema) == [], doc.path
