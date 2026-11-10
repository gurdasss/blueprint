"""Page spec parsing: valid specs parse to typed structures; every invalid input names its location."""

from pathlib import Path

import pytest
import yaml

from blueprint import spec
from blueprint.spec import FieldRef, SpecError

ROOT = Path(__file__).resolve().parent.parent


def problems(data) -> list[str]:
    with pytest.raises(SpecError) as exc:
        spec.parse(data, "t.yaml")
    return exc.value.problems


def test_example_spec_parses():
    s = spec.load(ROOT / "examples" / "sales-overview.yaml")
    assert (s.page, s.layout, [v.type for v in s.visuals]) == ("Sales Overview", "two-up",
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
     ["visuals[0].type: 'gauge' is not a supported visual type (supported: bar, card, column, header, kpi, line, table)"]),
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
     [("visuals[0].slots.category[1]: 'nope' is not a field reference "
       "(use Table[Column], [Measure], or {field: \u2026, aggregate: \u2026, format: \u2026})")]),
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


def test_every_full_spec_in_the_readme_parses(tmp_path):
    """README spec examples once drifted from the code (a `kpi-row` visual type that never
    existed). Every ```yaml block with top-level `visuals:` must parse as a spec, and every block
    with top-level `palette:` must load as guidelines."""
    import re

    import yaml

    from blueprint import guidelines
    from blueprint.spec import parse

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    blocks = re.findall(r"```yaml\n(.*?)```", readme, re.DOTALL)
    specs = [b for b in blocks if re.search(r"^visuals:", b, re.MULTILINE)]
    guides = [b for b in blocks if re.search(r"^palette:", b, re.MULTILINE)]
    assert specs and guides
    for block in specs:
        parse(yaml.safe_load(block), "README.md")
    for i, block in enumerate(guides):
        g = tmp_path / f"g{i}.yaml"
        g.write_text(block, encoding="utf-8")
        guidelines.load(g)


def test_the_shipped_page_template_parses():
    """template/page.template.yaml is what a client copies: every slot form it shows in its
    YAML body must be one the parser accepts (the guidelines and layout templates have the
    same test). Syntax that isn't built yet belongs in a comment, marked as such."""
    data = yaml.safe_load((ROOT / "template" / "page.template.yaml").read_text(encoding="utf-8"))
    spec.parse(data, "page.template.yaml")
