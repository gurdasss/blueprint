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


def test_spec_region_overrides_the_contract_role():
    layout = layouts.parse({**LAYOUT, "regions": [*LAYOUT["regions"],
                                                  {"role": "kpi-row", "x": 16, "y": 96, "w": 400, "h": 120}]})
    placed = layouts.place(_spec(CARD, {**CARD, "region": "kpi-row"}), layout)
    assert [p.region.key for p in placed] == ["main#1", "kpi-row#1"]


def test_spec_region_the_layout_lacks_is_an_error():
    with pytest.raises(LayoutError, match=r"visuals\[0\]\.region: layout 'two' has no 'kpi-row' region "
                                          r"\(it has header, main\)"):
        layouts.place(_spec({**CARD, "region": "kpi-row"}), layouts.parse(LAYOUT))


@pytest.mark.parametrize("bad", ["", "KPI Row", 3, ["main"]])
def test_spec_region_must_be_a_role_name(bad):
    with pytest.raises(spec.SpecError, match=r"visuals\[0\]\.region: .* must be a region role"):
        _spec({**CARD, "region": bad})


SHIPPED = sorted(p.stem for p in (ROOT / "guidelines" / "layouts").glob("*.yaml"))


@pytest.mark.parametrize("name", SHIPPED)
def test_shipped_layouts_fit_the_example_guidelines(name):
    g = guidelines.load(ROOT / "guidelines" / "example.yaml")
    layout = layouts.load(name, g.layouts.search_path)
    assert (layout.width, layout.height) == (g.canvas.width, g.canvas.height)
    assert layouts.conflicts(layout, g.grid.size, g.canvas.margin, g.canvas.gutter) == []
    assert sum(r.role == "header" for r in layout.regions) == 1


def test_shipped_layouts():
    assert SHIPPED == ["dashboard-6", "grid-2x3", "kpi-row-plus-detail", "one-up", "standard-4-up", "two-up"]


def test_conflicts_include_the_gutter():
    assert layouts.conflicts(layouts.parse(LAYOUT), 8, 16, 16) == []  # 16px apart
    assert layouts.conflicts(layouts.parse(LAYOUT), 8, 16, 24) == [
        "regions header#1 and main#1 are 16px apart, less than the 24px gutter",
        "regions header#1 and main#2 are 16px apart, less than the 24px gutter",
        "regions main#1 and main#2 are 16px apart, less than the 24px gutter",
    ]


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


def test_changing_a_visuals_region_moves_it_on_re_apply(tmp_path: Path, capsys):
    import shutil

    from blueprint.cli import main
    from blueprint.pbir.reader import read_report
    shutil.copytree(ROOT / "fixtures" / "02-card-and-chart", tmp_path / "proj")
    args = ["--report", str(tmp_path / "proj"), "--guidelines", str(ROOT / "guidelines" / "example.yaml")]
    s = tmp_path / "dash.yaml"
    body = ("page: Dash\nlayout: dashboard-6\nvisuals:\n  - {type: header, title: Hi}\n"
            "  - {type: card, id: total, %sslots: {value: '[Total Amount]'}}\n")

    def card():
        [page] = [p for p in read_report(tmp_path / "proj").pages if p.display_name == "Dash"]
        [v] = [v for v in page.visuals if v.visual_type == "cardVisual"]
        return v.region, (v.rect.x, v.rect.y)

    s.write_text(body % "")
    assert main(["apply", str(s), *args]) == 0
    assert card() == ("main#1", (16, 272))
    s.write_text(body % "region: kpi-row, ")
    assert main(["apply", str(s), *args]) == 0
    assert card() == ("kpi-row#1", (16, 96))
    from blueprint.validate import check_report
    report = read_report(tmp_path / "proj")
    [page] = [p.name for p in report.pages if p.display_name == "Dash"]
    found = check_report(report, guidelines.load(ROOT / "guidelines" / "example.yaml")).findings
    assert [f for f in found if f.page == page] == []


def test_an_empty_search_path_says_where_layouts_come_from():
    with pytest.raises(layouts.LayoutError, match="layouts.search_path is empty.*guidelines/layouts/"):
        layouts.find("two-up", ())
