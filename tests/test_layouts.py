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
