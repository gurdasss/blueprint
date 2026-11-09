from pathlib import Path

import pytest

from blueprint import guidelines, layouts, spec
from blueprint.layouts import LayoutError
from blueprint.model import Rect

ROOT = Path(__file__).resolve().parent.parent
LAYOUT = {"name": "two", "canvas": {"width": 1280, "height": 720}, "regions": [
    {"role": "header", "x": 16, "y": 16, "w": 1248, "h": 64},
    {"role": "main", "x": 16, "y": 96, "w": 616, "h": 608},
    {"role": "main", "x": 648, "y": 96, "w": 616, "h": 608},
]}


def _spec(*visuals) -> spec.PageSpec:
    return spec.parse({"page": "P", "visuals": list(visuals)}, "p.yaml")


CARD = {"type": "card", "slots": {"value": "[A]"}}


def test_example_layout_and_spec_place_in_declaration_order(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)  # search_path must not depend on the current directory
    g = guidelines.load(ROOT / "guidelines" / "example.yaml")
    s = spec.load(ROOT / "examples" / "sales-overview.yaml")
    placed = layouts.place(s, layouts.load(s.layout, g.layouts.search_path))
    assert [(p.visual.type, p.region.role, p.region.rect.x) for p in placed] == [
        ("header", "header", 16), ("card", "main", 16), ("column", "main", 648)]


def test_running_out_of_regions_is_an_error_not_a_reflow():
    with pytest.raises(LayoutError, match=r"visuals\[2\] \(card\): no free 'main' region left in layout 'two' \(it has 2\)"):
        layouts.place(_spec(CARD, CARD, CARD), layouts.parse(LAYOUT))


def test_ignored_visuals_take_no_region():
    s = _spec(CARD, {"type": "column", "blueprint": "ignore"}, CARD)
    assert [p.visual.index for p in layouts.place(s, layouts.parse(LAYOUT))] == [0, 2]


def test_missing_role_region_is_an_error():
    no_header = {**LAYOUT, "regions": LAYOUT["regions"][1:]}
    with pytest.raises(LayoutError, match="no free 'header' region"):
        layouts.place(_spec({"type": "header", "title": "Hi"}), layouts.parse(no_header))


@pytest.mark.parametrize(("data", "match"), [
    ({**LAYOUT, "canvas": {"width": 0, "height": 720}}, "canvas: needs integer width and height"),
    ({**LAYOUT, "canvas": "big"}, "canvas: needs integer width and height"),
    ({**LAYOUT, "regions": []}, "regions: required"),
    ({**LAYOUT, "regions": [{"role": "main", "x": 0, "y": 0, "w": 0, "h": 10}]}, "w and h > 0"),
    ({**LAYOUT, "regions": [{"role": "main", "x": 1000, "y": 0, "w": 400, "h": 10}]}, "outside the 1280x720 canvas"),
    ({**LAYOUT, "regions": [{"x": 0}]}, "needs a role"),
])
def test_invalid_layouts(data, match):
    with pytest.raises(LayoutError, match=match):
        layouts.parse(data)


def test_name_must_match_file(tmp_path: Path):
    (tmp_path / "mine.yaml").write_text("name: other\ncanvas: {width: 10, height: 10}\n"
                                        "regions: [{role: main, x: 0, y: 0, w: 10, h: 10}]\n")
    with pytest.raises(LayoutError, match="name: must be 'mine'"):
        layouts.load("mine", (tmp_path,))


def test_not_found_lists_search_path(tmp_path: Path):
    with pytest.raises(LayoutError, match="layout 'nope' not found in"):
        layouts.load("nope", (tmp_path,))


def test_search_path_resolves_relative_to_declaring_file(tmp_path: Path, monkeypatch):
    org = tmp_path / "org"
    (org / "lay").mkdir(parents=True)
    (org / "g.yaml").write_text("layouts: {search_path: [lay], default: two}\n")
    monkeypatch.chdir(tmp_path)
    g = guidelines.load(org / "g.yaml")
    assert g.layouts.search_path == ((org / "lay").resolve(),)
    assert g.layouts.default == "two"


def test_region_rects():
    layout = layouts.parse(LAYOUT)
    assert layout.regions[1].rect == Rect(16, 96, 616, 608)


def test_conflicts_with_guidelines():
    on_grid = layouts.parse(LAYOUT)
    assert layouts.conflicts(on_grid, 8, 16) == []
    off = layouts.parse({**LAYOUT, "regions": [{"role": "header", "x": 10, "y": 16, "w": 1250, "h": 64},
                                               {"role": "main", "x": 8, "y": 96, "w": 616, "h": 608}]})
    assert layouts.conflicts(off, 8, 16) == [
        "region header#1 is off the 8px grid (left=10, right=1260)",
        "region header#1 is inside the 16px margin (left)",
        "region main#1 is inside the 16px margin (left)",
    ]
    assert layouts.conflicts(off, 2, 0) == []  # the same layout is fine for a 2px grid, no margin


def test_apply_refuses_a_layout_that_would_fight_fmt(tmp_path: Path, capsys):
    import shutil

    from blueprint.cli import main
    shutil.copytree(ROOT / "fixtures" / "02-card-and-chart", tmp_path / "proj")
    (tmp_path / "offgrid.yaml").write_text(
        "name: offgrid\ncanvas: {width: 1280, height: 720}\n"
        "regions:\n  - {role: header, x: 10, y: 10, w: 1250, h: 61}\n")
    g = tmp_path / "g.yaml"
    g.write_text(f"grid: {{size: 8}}\ncanvas: {{margin: 16}}\nlayouts: {{search_path: ['{tmp_path}']}}\n")
    s = tmp_path / "s.yaml"
    s.write_text("page: P\nlayout: offgrid\nvisuals:\n  - {type: header, title: Hi}\n")
    assert main(["apply", str(s), "--report", str(tmp_path / "proj"), "--guidelines", str(g)]) == 2
    err = capsys.readouterr().err
    assert "would keep moving its visuals back and forth" in err and "region header#1 is off the 8px grid" in err


def test_apply_fmt_apply_converges(tmp_path: Path, capsys):
    import shutil

    from blueprint.cli import main
    shutil.copytree(ROOT / "fixtures" / "02-card-and-chart", tmp_path / "proj")
    args = ["--report", str(tmp_path / "proj"), "--guidelines", str(ROOT / "guidelines" / "example.yaml")]
    spec_path = str(ROOT / "examples" / "sales-overview.yaml")
    assert main(["apply", spec_path, *args]) == 0
    assert main(["fmt", *args]) == 0
    capsys.readouterr()
    assert main(["apply", spec_path, *args]) == 0
    assert "No changes." in capsys.readouterr().out
    assert main(["fmt", *args]) == 0
    assert "No changes." in capsys.readouterr().out
