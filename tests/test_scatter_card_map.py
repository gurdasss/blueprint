"""The scatter chart, the multi-row card and the map (probes 34 and 36).

Probe 34 drew these three as hand-written candidates; probe 36 built them with `bp apply` and
Desktop drew and kept them. The one shape Blueprint deliberately leaves out is `"active": true`
on a scatter's `X`: `active` marks a column's drill state and `X` takes a measure, so Desktop
adds it itself on save (probe 36's diff shows it on all three scatters).
"""

import shutil
from pathlib import Path

import pytest

from blueprint.cli import main
from blueprint.pbir import jsonfmt
from blueprint.slots import contracts

ROOT = Path(__file__).resolve().parent.parent
GUIDE = ROOT / "guidelines" / "example.yaml"


@pytest.fixture
def report(tmp_path: Path) -> Path:
    shutil.copytree(ROOT / "fixtures" / "02-card-and-chart", tmp_path / "proj")
    return tmp_path / "proj" / "Fixture.Report"


def _apply(report: Path, body: str) -> int:
    spec = report.parent.parent / "s.yaml"
    spec.write_text("page: P\nlayout: two-up\nvisuals:\n  - {type: header, title: P}\n" + body,
                    encoding="utf-8")
    return main(["apply", str(spec), "--report", str(report), "--guidelines", str(GUIDE)])


def _visual(report: Path, visual_type: str) -> dict:
    for f in report.glob("definition/pages/*/visuals/*/visual.json"):
        doc = jsonfmt.load(f)
        if doc["visual"]["visualType"] == visual_type:
            return doc["visual"]
    raise AssertionError(f"no {visual_type}")


def _roles(visual: dict) -> dict[str, list[tuple[str, bool]]]:
    return {role: [(p["field"][next(iter(p["field"]))]["Property"], p.get("active", False))
                   for p in body["projections"]]
            for role, body in visual["query"]["queryState"].items()}


SCATTER = ('  - {type: scatter, title: S, slots: {category: "Sales[Country]", x: "[Total Amount]", '
           'y: "[Total Amount]", size: "[Total Amount]", legend: "Sales[Region]"}}\n')


def test_a_scatter_writes_five_wells_with_active_on_the_category_only(report: Path):
    assert _apply(report, SCATTER) == 0
    roles = _roles(_visual(report, "scatterChart"))
    assert list(roles) == ["Category", "Series", "Size", "X", "Y"]  # alphabetical, as Desktop writes
    assert roles["Category"] == [("Country", True)]
    assert roles["X"] == [("Total Amount", False)]  # Desktop adds its own `active` on save
    assert roles["Series"] == [("Region", False)] and roles["Size"] == [("Total Amount", False)]


def test_a_scatter_takes_a_drill_down_category(report: Path):
    assert _apply(report, '  - {type: scatter, title: S, slots: {category: ["Sales[Country]", '
                          '"Sales[Region]"], x: "[Total Amount]", y: "[Total Amount]"}}\n') == 0
    assert _roles(_visual(report, "scatterChart"))["Category"] == [("Country", True), ("Region", True)]


@pytest.mark.parametrize("missing", ["x", "y", "category"])
def test_a_scatter_without_a_required_well_is_refused(report: Path, missing: str, capsys):
    slots = {"category": '"Sales[Country]"', "x": '"[Total Amount]"', "y": '"[Total Amount]"'}
    del slots[missing]
    body = ", ".join(f"{k}: {v}" for k, v in slots.items())
    assert _apply(report, f"  - {{type: scatter, title: S, slots: {{{body}}}}}\n") == 2
    assert missing in capsys.readouterr().err


def test_a_multi_row_card_takes_columns_and_measures_in_one_well(report: Path):
    """Probe 34: a column beside a measure draws one row per value, which is the type's point."""
    assert _apply(report, '  - {type: multi-row-card, title: C, slots: {fields: ["Sales[Country]", '
                          '"[Total Amount]"]}}\n') == 0
    roles = _roles(_visual(report, "multiRowCard"))
    assert roles == {"Values": [("Country", False), ("Total Amount", False)]}  # no active


def test_a_map_writes_category_size_and_legend(report: Path):
    assert _apply(report, '  - {type: map, title: M, slots: {category: "Sales[Country]", '
                          'size: "[Total Amount]", legend: "Sales[Region]"}}\n') == 0
    roles = _roles(_visual(report, "map"))
    assert roles["Category"] == [("Country", True)]
    assert roles["Size"] == [("Total Amount", False)] and roles["Series"] == [("Region", False)]


def test_a_map_without_a_size_is_refused(report: Path, capsys):
    assert _apply(report, '  - {type: map, title: M, slots: {category: "Sales[Country]"}}\n') == 2
    assert "size" in capsys.readouterr().err


def test_the_contracts_say_what_the_probes_verified():
    c = contracts()
    assert c["scatter"].active_roles == frozenset({"Category"})  # not X: Desktop adds that itself
    assert c["map"].active_roles == frozenset({"Category"})
    assert c["multi-row-card"].active_roles == frozenset()
    assert c["multi-row-card"].slots["fields"].accepts == ("column", "measure")
    assert [s.name for s in c["scatter"].slots.values() if s.required] == ["category", "x", "y"]
    assert [s.name for s in c["map"].slots.values() if s.required] == ["category", "size"]
    # none of the three ships an option: probe 34 wrote no objects on them
    assert not (c["scatter"].options or c["map"].options or c["multi-row-card"].options)
