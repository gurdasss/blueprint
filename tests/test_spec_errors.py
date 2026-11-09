"""Page spec parsing: valid specs parse to typed structures; every invalid input names its location."""

from pathlib import Path

import pytest

from blueprint import spec
from blueprint.spec import FieldRef, SpecError

ROOT = Path(__file__).resolve().parent.parent


def problems(data) -> list[str]:
    with pytest.raises(SpecError) as exc:
        spec.parse(data, "t.yaml")
    return exc.value.problems


def test_example_spec_parses():
    s = spec.load(ROOT / "examples" / "sales-overview.yaml")
    assert (s.page, s.layout, [v.type for v in s.visuals]) == ("Sales Overview", "standard-4-up",
                                                                ["header", "card", "column"])
    column = s.visuals[2]
    assert column.id == "column-1"
    assert column.slots == {"category": (FieldRef("column", "Country", "Sales"), FieldRef("column", "Region", "Sales")),
                            "value": (FieldRef("measure", "Total Amount"),)}


@pytest.mark.parametrize(("text", "ref"), [
    ("[Total Amount]", FieldRef("measure", "Total Amount")),
    ("Sales[Country]", FieldRef("column", "Country", "Sales")),
    ("'Sales Data'[Order Date]", FieldRef("column", "Order Date", "Sales Data")),
    ("'Bob''s'[x]", FieldRef("column", "x", "Bob's")),
    ("  [ Spaced ] ", FieldRef("measure", "Spaced")),
    ("Total Amount", None),
    ("Sales[Country", None),
    (3, None),
])
def test_parse_field(text, ref):
    assert spec.parse_field(text) == ref


def test_ids_default_by_type_and_count_and_must_be_unique():
    s = spec.parse({"page": "P", "visuals": [
        {"type": "card", "slots": {"value": "[A]"}}, {"type": "card", "id": "kpi", "slots": {"value": "[B]"}},
        {"type": "card", "slots": {"value": "[C]"}}]})
    assert [v.id for v in s.visuals] == ["card-1", "kpi", "card-3"]
    assert problems({"page": "P", "visuals": [{"type": "card", "id": "x", "slots": {"value": "[A]"}},
                                              {"type": "card", "id": "x", "slots": {"value": "[A]"}}]}) == [
        "visuals[1].id: 'x' already used by visuals[0]"]


def test_ignored_visual_needs_no_slots():
    s = spec.parse({"page": "P", "visuals": [{"type": "column", "blueprint": "ignore"}]})
    assert s.visuals[0].ignore and s.visuals[0].slots == {}


@pytest.mark.parametrize(("data", "expected"), [
    ("not a mapping", ["top level must be a mapping with page, layout and visuals"]),
    ({"visuals": [{"type": "header", "title": "x"}]}, ["page: required, a non-empty page name"]),
    ({"page": "P"}, ["visuals: required, a non-empty list"]),
    ({"page": "P", "visuals": [], "colour": 1}, ["colour: unknown key (expected: id, layout, page, visuals)",
                                                 "visuals: required, a non-empty list"]),
    ({"page": "P", "visuals": [{"type": "gauge"}]},
     ["visuals[0].type: 'gauge' is not a supported visual type (supported: area, bar, card, column, donut, header, kpi, line, matrix, pie, slicer, stacked-bar, stacked-column, stacked-column-100, table)"]),
    ({"page": "P", "visuals": [{"type": "header"}]},
     ["visuals[0].title: a header needs a title (it is the header's text)"]),
    ({"page": "P", "visuals": [{"type": "card"}]}, ["visuals[0].slots.value: required by card"]),
    ({"page": "P", "visuals": [{"type": "card", "slots": {"value": "Sales[Amount]"}}]},
     [("visuals[0].slots.value: Sales[Amount] is a column, but value accepts measure; "
       "if 'Amount' is a measure, write it as [Amount]")]),
    ({"page": "P", "visuals": [{"type": "column", "slots": {"category": "[Total]", "value": "[Total]"}}]},
     ["visuals[0].slots.category: [Total] is a measure, but category accepts column or hierarchy"]),
    ({"page": "P", "visuals": [{"type": "card", "slots": {"value": ["[A]", "[B]"]}}]},
     ["visuals[0].slots.value: takes a single field, not a list"]),
    ({"page": "P", "visuals": [{"type": "card", "slots": {"value": "[A]", "legend": "T[x]"}}]},
     ["visuals[0].slots.legend: card has no slot 'legend' (slots: value)"]),
    ({"page": "P", "visuals": [{"type": "column", "slots": {"category": ["T[a]", "nope"], "value": "[v]"}}]},
     ["visuals[0].slots.category[1]: 'nope' is not a field reference (use Table[Column] or [Measure])"]),
    ({"page": "P", "visuals": [{"type": "card", "id": "Bad Id", "slots": {"value": "[A]"}}]},
     ["visuals[0].id: 'Bad Id' must be lowercase letters, digits and hyphens (max 40)"]),
    ({"page": "P", "visuals": [{"type": "card", "blueprint": "skip", "slots": {"value": "[A]"}}]},
     ["visuals[0].blueprint: the only accepted value is `ignore`"]),
])
def test_invalid_specs(data, expected):
    assert problems(data) == expected


def test_all_problems_reported_together():
    found = problems({"page": "", "visuals": [{"type": "gauge"}, {"type": "card"}, "x"]})
    assert len(found) == 4 and found[0].startswith("page:")


def test_unreadable_spec_file(tmp_path: Path):
    f = tmp_path / "s.yaml"
    f.write_text("page: [oops")
    with pytest.raises(SpecError):
        spec.load(f)
