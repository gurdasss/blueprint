import json
import random
import shutil
from pathlib import Path

import pytest

from blueprint import grid, guidelines
from blueprint.cli import main
from blueprint.model import Rect
from blueprint.pbir.reader import IGNORE_ANNOTATION, read_report
from blueprint.validate import check_report
from tests.builders import make_report, visual, write


def rules(tmp_path: Path, body: str = "") -> guidelines.Guidelines:
    f = tmp_path / "g.yaml"
    f.write_text(body)
    return guidelines.load(f)


_n = iter(range(10**6))


def findings(tmp_path: Path, visuals: list[dict], body: str = "", rule: str | None = None):
    root = tmp_path / f"r{next(_n)}"  # fresh report per call; folders must not leak between calls
    r = read_report(make_report(root, {"p": visuals}))
    out = check_report(r, rules(tmp_path, body)).findings
    return [f for f in out if rule is None or f.rule == rule]


def test_clean_page_has_no_findings(tmp_path: Path):
    assert findings(tmp_path, [visual("a", 16, 16, 400, 200), visual("b", 432, 16, 400, 200)]) == []


def test_bounds(tmp_path: Path):
    [f] = findings(tmp_path, [visual("a", -8, 0, 64, 64)], rule="bounds")
    assert (f.visual, f.severity, f.message) == ("a", "error", "outside the page: left by 8")
    [f] = findings(tmp_path, [visual("b", 1248, 696, 64, 64)], rule="bounds")
    assert f.message == "outside the page: right by 32, bottom by 40"


def test_grid_counts_page_edge_as_grid_line(tmp_path: Path):
    assert findings(tmp_path, [visual("a", 0, 0, 1280, 720)], "grid: {size: 7}", "grid") == []
    [f] = findings(tmp_path, [visual("a", 3, 8, 64, 64)], rule="grid")
    assert "left=3" in f.message and "right=67" in f.message and "bp fmt fixes this" in f.message


def test_grid_hint_when_fmt_would_skip(tmp_path: Path):
    [f] = findings(tmp_path, [visual("a", 1151.39, 694.51, 126.16, 24.5)], "grid: {size: 32}", "grid")
    assert "bp fmt skips it (would resize 96%)" in f.message


def test_margin_and_decorative_exemption(tmp_path: Path):
    body = "canvas: {margin: 16}"
    [f] = findings(tmp_path, [visual("a", 8, 16, 64, 64)], body, "margin")
    assert f.message == "closer than 16px to the page edge (left 8)"
    assert findings(tmp_path, [visual("bg", 0, 0, 1280, 720, vtype="image")], body, "margin") == []


def test_overlap_rules(tmp_path: Path):
    partial = [visual("a", 0, 0, 64, 64), visual("b", 32, 32, 64, 64)]
    [f] = findings(tmp_path, partial, rule="overlap")
    assert (f.visual, f.message) == ("a", "overlaps b (card)")
    touching = [visual("a", 0, 0, 64, 64), visual("b", 64, 0, 64, 64)]
    assert findings(tmp_path, touching, rule="overlap") == []
    on_background = [visual("bg", 0, 0, 640, 640, vtype="image"), visual("c", 16, 16, 64, 64)]
    assert findings(tmp_path, on_background, rule="overlap") == []
    card_inside_chart = [visual("chart", 0, 0, 640, 640, vtype="lineChart"), visual("c", 16, 16, 64, 64)]
    assert len(findings(tmp_path, card_inside_chart, rule="overlap")) == 1


def test_page_size(tmp_path: Path):
    [f] = findings(tmp_path, [], "canvas: {width: 1920, height: 1080}", "page-size")
    assert f.message == "page is 1280x720, guidelines say 1920x1080"
    assert findings(tmp_path, [], "canvas: {width: 1280}", "page-size") == []


def test_dynamic_page_noted_not_checked(tmp_path: Path):
    rd = make_report(tmp_path, {"p": [visual("a", 3, 3, 10, 10)]})
    write(rd / "definition/pages/p/page.json", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json",
        "name": "p", "displayName": "Dyn", "displayOption": "DeprecatedDynamic"})
    res = check_report(read_report(rd), rules(tmp_path, "canvas: {width: 1280, height: 720}"))
    assert [f.rule for f in res.findings] == ["page-size"]
    assert res.notes == ["Dyn: geometry not checked (no fixed page size)"]


@pytest.mark.parametrize(("policy", "expected"), [("all", 4), ("visible", 3), ("data", 2)])
def test_density_policies(tmp_path: Path, policy: str, expected: int):
    q = {"queryState": {"Values": {"projections": [{"field": {}, "queryRef": "T.c"}]}}}
    vs = [visual("a", 0, 0, 8, 8), visual("b", 16, 0, 8, 8), visual("t", 32, 0, 8, 8, vtype="textbox"),
          visual("h", 48, 0, 8, 8, isHidden=True)]
    vs[0]["visual"]["query"] = q
    vs[1]["visual"]["query"] = q
    vs[3]["visual"]["query"] = q
    body = f"page: {{max_visuals: 1, density_policy: {policy}}}"
    [f] = findings(tmp_path, vs, body, "density")
    assert f.message.startswith(f"{expected} visuals (policy '{policy}') > max_visuals 1")


def test_severity_levels(tmp_path: Path):
    vs = [visual("a", 3, 3, 64, 64)]
    assert findings(tmp_path, vs, "check: {severity: {grid: off}}", "grid") == []  # YAML 1.1: off -> False
    assert findings(tmp_path, vs, "check: {severity: {grid: 'off'}}", "grid") == []
    [f] = findings(tmp_path, vs, "check: {severity: {grid: warning}}", "grid")
    assert f.severity == "warning"


def test_ignored_exempt_and_groups_noted(tmp_path: Path):
    vs = [visual("i", 3, 3, 64, 64, annotations=[{"name": IGNORE_ANNOTATION, "value": "true"}]),
          visual("c", 3, 3, 64, 64, parentGroupName="g")]
    r = read_report(make_report(tmp_path, {"p": vs}))
    res = check_report(r, rules(tmp_path))
    assert res.findings == []
    assert res.notes == ["P: 1 grouped visual(s) not checked (group-relative positioning is unverified)"]


def test_snapped_rects_are_never_off_grid():
    rng = random.Random(99)
    for _ in range(5000):
        g = rng.choice([1, 3, 4, 7, 8, 10, 16, 32, 64])
        pw, ph = rng.choice([(1280, 720), (1278, 719), (1920, 1080)])
        x, y = rng.uniform(0, pw - 1), rng.uniform(0, ph - 1)
        r = Rect(x, y, rng.uniform(0.5, pw - x), rng.uniform(0.5, ph - y))
        assert grid.off_grid_edges(grid.snap_rect(r, g, pw, ph), g, pw, ph) == {}, (r, g)


# --- CLI ------------------------------------------------------------------------------


def _snapshot(root: Path) -> dict[str, bytes]:
    return {p.as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def test_exit_codes_and_read_only(tmp_path: Path, capsys):
    clean = make_report(tmp_path / "clean", {"p": [visual("a", 16, 16, 64, 64)]})
    assert main(["check", "--report", str(clean)]) == 0
    messy = make_report(tmp_path / "messy", {"p": [visual("a", 0, 0, 64, 64), visual("b", 32, 32, 64, 64)]})
    before = _snapshot(messy)
    assert main(["check", "--report", str(messy)]) == 0          # overlap is only a warning
    assert main(["check", "--report", str(messy), "--strict"]) == 1
    assert main(["check", "--report", str(messy), "--grid", "3"]) == 1  # now off-grid: error
    assert _snapshot(messy) == before
    assert main(["check", "--report", str(tmp_path / "nope")]) == 2
    capsys.readouterr()


def test_json_output(tmp_path: Path, capsys):
    rd = make_report(tmp_path, {"p": [visual("a", 3, 16, 64, 64)]})
    assert main(["check", "--report", str(rd), "--json"]) == 1
    out = json.loads(capsys.readouterr().out)
    assert (out["errors"], out["warnings"]) == (1, 0)
    assert out["findings"][0] | {"message": ""} == {"rule": "grid", "severity": "error", "message": "",
                                                    "page": "p", "visual": "a"}


def test_format_findings(tmp_path: Path, capsys):
    rd = make_report(tmp_path, {"p": [visual("a", 16, 16, 64, 64, bogus=1)]})
    (rd / "definition/pages/bad name").mkdir()
    assert main(["check", "--report", str(rd), "--json"]) == 1
    msgs = [f["message"] for f in json.loads(capsys.readouterr().out)["findings"] if f["rule"] == "format"]
    assert any("bad name: invalid folder name" in m for m in msgs)
    assert any("visual.json" in m and "bogus" in m for m in msgs)


def test_unchecked_guidelines_are_listed(tmp_path: Path, capsys):
    rd = make_report(tmp_path, {"p": []})
    g = tmp_path / "g.yaml"
    g.write_text("canvas: {gutter: 32}\npage: {require_title: true}\n")
    main(["check", "--report", str(rd), "--guidelines", str(g)])
    assert "not checked yet (set in guidelines, not implemented): page.require_title, canvas.gutter" in capsys.readouterr().out


def test_example_guidelines_load():
    g = guidelines.load(Path(__file__).resolve().parent.parent / "guidelines" / "example.yaml")
    assert (g.canvas.margin, g.page.max_visuals, g.page.density_policy) == (16, 6, "data")


def test_fmt_then_check_leaves_only_fmt_skipped_grid_findings(retail_report: Path, tmp_path: Path, capsys):
    copy = tmp_path / retail_report.name
    shutil.copytree(retail_report, copy)
    for g in ("8", "16", "32"):
        assert main(["fmt", "--report", str(copy), "--grid", g]) == 0
        capsys.readouterr()
        main(["check", "--report", str(copy), "--grid", g, "--json"])
        out = json.loads(capsys.readouterr().out)
        grid_findings = [f for f in out["findings"] if f["rule"] == "grid"]
        assert all("bp fmt skips it" in f["message"] for f in grid_findings), (g, grid_findings)
        assert not [f for f in out["findings"] if f["rule"] in ("format", "bounds")], g
