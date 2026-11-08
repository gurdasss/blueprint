import os
from pathlib import Path

import pytest

from blueprint.model import Rect
from blueprint.pbir import writer
from blueprint.pbir.reader import read_report
from tests.builders import S, make_report, visual, write


def _report(tmp_path: Path, **v):
    rd = make_report(tmp_path, {"p": [visual("v1", 10.5, 20.25, 100, 50, **v), visual("v2", 0, 0, 8, 8)]})
    return rd, read_report(rd)


def test_no_changes_no_writes(tmp_path: Path):
    _, r = _report(tmp_path)
    assert writer.plan_writes(r).empty


def test_only_position_fields_change(tmp_path: Path):
    rd, r = _report(tmp_path, isHidden=True)
    v1 = r.page("p").visuals[0]
    v1.rect = Rect(16, 24, 96, 48)
    plan = writer.plan_writes(r)
    assert [w.path.name for w in plan.writes] == ["visual.json"]
    w = plan.writes[0]
    assert w.changes == ("v1: x 10.50 -> 16, y 20.25 -> 24, width 100 -> 96, height 50 -> 48",)
    before, after = w.before.decode().split("\r\n"), w.after.decode().split("\r\n")
    changed = [(a, b) for a, b in zip(before, after, strict=True) if a != b]
    assert changed == [('    "x": 10.5,', '    "x": 16,'), ('    "y": 20.25,', '    "y": 24,'),
                       ('    "height": 50,', '    "height": 48,'), ('    "width": 100', '    "width": 96')]

    writer.apply(plan)
    again = read_report(rd)
    assert again.page("p").visuals[0].rect == Rect(16, 24, 96, 48)
    assert again.page("p").visuals[0].hidden
    assert writer.plan_writes(again).empty


def test_refuses_when_file_changed_since_read(tmp_path: Path):
    rd, r = _report(tmp_path)
    r.page("p").visuals[0].rect = Rect(0, 0, 8, 8)
    plan = writer.plan_writes(r)
    target = rd / plan.writes[0].path
    target.write_bytes(target.read_bytes() + b" ")
    with pytest.raises(writer.WriteError, match="changed on disk"):
        writer.apply(plan)
    assert target.read_bytes().endswith(b" ")  # untouched
    assert not list(rd.rglob("*.bp-tmp"))


def test_all_or_nothing_when_one_file_is_stale(tmp_path: Path):
    rd, r = _report(tmp_path)
    for v in r.page("p").visuals:
        v.rect = Rect(40, 40, 16, 16)
    plan = writer.plan_writes(r)
    assert len(plan.writes) == 2
    stale = rd / plan.writes[1].path
    stale.write_bytes(b"{}")
    originals = {w.path: (rd / w.path).read_bytes() for w in plan.writes}
    with pytest.raises(writer.WriteError):
        writer.apply(plan)
    assert {w.path: (rd / w.path).read_bytes() for w in plan.writes} == originals


def test_preserves_file_mode(tmp_path: Path):
    rd, r = _report(tmp_path)
    target = rd / r.page("p").visuals[0].source.path
    os.chmod(target, 0o755)
    r.page("p").visuals[0].rect = Rect(0, 0, 8, 8)
    writer.apply(writer.plan_writes(r))
    assert target.stat().st_mode & 0o777 == 0o755


def test_schema_invalid_change_refused(tmp_path: Path):
    _, r = _report(tmp_path)
    r.page("p").visuals[0].source.data["bogus"] = 1  # simulate a bad in-memory edit
    r.page("p").visuals[0].rect = Rect(0, 0, 8, 8)
    with pytest.raises(writer.WriteError, match="schema-invalid"):
        writer.plan_writes(r)


def test_unknown_schema_major_needs_force(tmp_path: Path):
    rd = make_report(tmp_path, {"p": []})
    v = visual("v1")
    v["$schema"] = f"{S}/visualContainer/9.0.0/schema.json"
    write(rd / "definition/pages/p/visuals/v1/visual.json", v)
    r = read_report(rd)
    r.page("p").visuals[0].rect = Rect(8, 8, 8, 8)
    with pytest.raises(writer.WriteError, match="unknown major"):
        writer.plan_writes(r)
    assert len(writer.plan_writes(r, force_schema=True).writes) == 1
