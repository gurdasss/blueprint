"""An empty layout region is a gap on the page: bp apply warns and names layouts that fit,
and never stretches other regions into it (no reflow)."""

import shutil
from pathlib import Path

from blueprint import layouts
from blueprint.cli import main
from blueprint.pbir.reader import read_report

ROOT = Path(__file__).resolve().parent.parent
GUIDE = ROOT / "guidelines" / "example.yaml"
HEADER = "  - {type: header, title: Hi}\n"
CARD = "  - {type: card, slots: {value: '[Total Amount]'}}\n"
KPI = "  - {type: kpi, slots: {value: '[Total Amount]', trend: 'Sales[Country]'}}\n"


def _apply(tmp_path: Path, layout: str, visuals: str, capsys, guide: Path = GUIDE) -> str:
    proj = tmp_path / "proj"
    if not proj.exists():
        shutil.copytree(ROOT / "fixtures" / "02-card-and-chart", proj)
    s = tmp_path / "gap.yaml"
    s.write_text(f"page: G\nlayout: {layout}\nvisuals:\n{visuals}")
    capsys.readouterr()
    assert main(["apply", str(s), "--report", str(proj), "--guidelines", str(guide)]) == 0
    return capsys.readouterr().out


def _gaps(out: str) -> list[str]:
    return [ln.strip() for ln in out.splitlines() if "a gap on the page" in ln]


def test_an_empty_kpi_row_warns_and_names_two_up(tmp_path, capsys):
    out = _apply(tmp_path, "standard-4-up", HEADER + CARD * 2, capsys)
    assert _gaps(out) == [("- layout 'standard-4-up' leaves kpi-row#1 empty, a gap on the page; "
                          "layout(s) that fit with no gap: two-up")]
    page = next(p for p in read_report(tmp_path / "proj").pages if p.display_name == "G")
    assert sorted((v.rect.y, v.rect.height) for v in page.visuals if v.visual_type == "cardVisual") == [
        (272, 432), (272, 432)]  # the regions stay as declared: nothing is stretched


def test_following_the_hint_leaves_no_gap(tmp_path, capsys):
    _apply(tmp_path, "standard-4-up", HEADER + CARD * 2, capsys)
    out = _apply(tmp_path, "two-up", HEADER + CARD * 2, capsys)
    assert _gaps(out) == [] and "layout two-up" in out  # re-placed in the new layout
    page = next(p for p in read_report(tmp_path / "proj").pages if p.display_name == "G")
    assert sorted((v.rect.y, v.rect.height) for v in page.visuals if v.visual_type == "cardVisual") == [
        (96, 608), (96, 608)]


def test_a_partly_used_role_is_a_gap_too(tmp_path, capsys):
    [gap] = _gaps(_apply(tmp_path, "grid-2x3", HEADER + CARD, capsys))
    assert "leaves main#2, main#3, main#4, main#5, main#6 empty" in gap and gap.endswith("one-up")


def test_a_full_layout_and_no_fit(tmp_path, capsys):
    assert _gaps(_apply(tmp_path, "standard-4-up", HEADER + KPI + CARD * 2, capsys)) == []
    [gap] = _gaps(_apply(tmp_path, "standard-4-up", KPI + CARD * 2, capsys))  # no header
    assert gap.endswith("leaves header#1 empty, a gap on the page; no layout on the search path "
                        "fits this spec with no gap")


def test_hints_skip_layouts_on_another_canvas(tmp_path, capsys):
    layouts_dir = tmp_path / "layouts"
    shutil.copytree(ROOT / "guidelines" / "layouts", layouts_dir)
    text = (layouts_dir / "two-up.yaml").read_text().replace("name: two-up", "name: wide-two-up")
    (layouts_dir / "wide-two-up.yaml").write_text(text.replace("width: 1280", "width: 1920"))
    guide = tmp_path / "g.yaml"
    guide.write_text(GUIDE.read_text().replace('search_path: ["layouts"]',
                                               f"search_path: ['{layouts_dir}']"))
    [gap] = _gaps(_apply(tmp_path, "standard-4-up", HEADER + CARD * 2, capsys, guide))
    assert gap.endswith("fit with no gap: two-up")


def test_unused_lists_regions_in_declaration_order(tmp_path):
    layout = layouts.load("standard-4-up", (ROOT / "guidelines" / "layouts",))
    assert [r.key for r in layouts.unused(layout, [])] == ["header#1", "kpi-row#1", "main#1", "main#2"]
