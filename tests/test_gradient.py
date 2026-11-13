"""A table column's colour-scale background, from the guidelines' divergent colours (probe 44).

Probe 44 settled in Desktop: a theme's `minimum`/`center`/`maximum` are the defaults of every *new*
gradient, and a saved gradient stores its colours as hex literals in `objects.values[]`
(`backColor` ... `FillRule` `linearGradient2|3`), so it doesn't follow a later theme change. That is
why Blueprint writes the colours into the visual itself, from `palette.minimum|center|maximum`.
"""

import copy
import shutil
from pathlib import Path

import pytest

from blueprint import guidelines
from blueprint.cli import main
from blueprint.pbir import jsonfmt, render, theme

ROOT = Path(__file__).resolve().parent.parent
GUIDE = ROOT / "guidelines" / "example.yaml"
SET_A = ["--set", "palette.minimum=#6A00FF", "--set", "palette.center=#00E5D8",
         "--set", "palette.maximum=#FF5E00"]
SET_B = ["--set", "palette.minimum=#FF00C8", "--set", "palette.center=#B7FF00",
         "--set", "palette.maximum=#0030FF"]
TABLE = """\
page: Gradients
layout: one-up
visuals:
  - {type: header, title: Gradients}
  - type: table
    id: grid
    title: Grid
    slots:
      columns:
        - "Sales[Country]"
        - {field: "Sales[Amount]", aggregate: sum, gradient: 2}
        - {field: "Sales[Amount]", aggregate: max, gradient: 3}
"""


@pytest.fixture
def report(tmp_path: Path) -> Path:
    shutil.copytree(ROOT / "fixtures" / "02-card-and-chart", tmp_path / "proj")
    return tmp_path / "proj" / "Fixture.Report"


def _apply(report: Path, body: str = TABLE, flags: list[str] | None = None) -> int:
    spec = report.parent.parent / "gradients.yaml"
    spec.write_text(body, encoding="utf-8")
    return main(["apply", str(spec), "--report", str(report), "--guidelines", str(GUIDE),
                 *(SET_A if flags is None else flags)])


def _table(report: Path) -> tuple[Path, dict]:
    for f in report.glob("definition/pages/*/visuals/*/visual.json"):
        doc = jsonfmt.load(f)
        if doc["visual"]["visualType"] == "tableEx" and any(
                a.get("name") == "blueprint.visual" for a in doc.get("annotations", [])):
            return f, doc
    raise AssertionError("no Blueprint-made table")


def _stops(entry: dict) -> tuple[str, dict]:
    rule = entry["properties"]["backColor"]["solid"]["color"]["expr"]["FillRule"]["FillRule"]
    [(kind, stops)] = rule.items()
    return kind, {k: v["color"]["Literal"]["Value"] if "color" in v else v for k, v in stops.items()}


# --- guidelines -----------------------------------------------------------------------------


def _rules(tmp_path: Path, body: str) -> guidelines.Guidelines:
    f = tmp_path / "g.yaml"
    f.write_text(body)
    return guidelines.load(f)


def test_divergent_colours_load_and_are_the_themes_own_keys(tmp_path: Path):
    rules = _rules(tmp_path, "name: D\npalette: {minimum: '#6a00ff', center: '#00E5D8', maximum: '#FF5E00'}\n")
    assert rules.palette.divergent == {"minimum": "#6A00FF", "center": "#00E5D8", "maximum": "#FF5E00"}
    assert rules.palette.gradient(2) == ("#6A00FF", "#FF5E00")
    assert rules.palette.gradient(3) == ("#6A00FF", "#00E5D8", "#FF5E00")
    assert {"#6A00FF", "#00E5D8", "#FF5E00"} <= rules.palette.allowed
    doc, _ = theme.build(rules)
    assert (doc["minimum"], doc["center"], doc["maximum"]) == ("#6A00FF", "#00E5D8", "#FF5E00")
    assert not {"good", "neutral", "bad"} & set(doc)


def test_a_gradient_needs_every_stop_the_guidelines_must_supply(tmp_path: Path):
    rules = _rules(tmp_path, "palette: {minimum: '#6A00FF', maximum: '#FF5E00'}\n")
    assert rules.palette.gradient(2) == ("#6A00FF", "#FF5E00")
    assert rules.palette.gradient(3) is None


def test_a_bad_divergent_colour_is_refused(tmp_path: Path):
    with pytest.raises(guidelines.GuidelinesError, match=r"palette\.center must be a #RRGGBB"):
        _rules(tmp_path, "palette: {center: teal}\n")
    with pytest.raises(guidelines.GuidelinesError, match="did you mean minimum"):
        _rules(tmp_path, "palette: {minimun: '#6A00FF'}\n")


# --- spec ---------------------------------------------------------------------------------


@pytest.mark.parametrize(("slot", "match"), [
    ('{field: "Sales[Amount]", aggregate: sum, gradient: 4}', "gradient: 4 must be 2 (lowest to highest) or 3"),
    ('{field: "Sales[Amount]", aggregate: sum, gradient: true}', "gradient: True must be 2"),
    ('{field: "Sales[Amount]", gradient: 2}', "gradient: needs aggregate"),
    ('{field: "[Total Amount]", gradient: 2}', "gradient: needs aggregate"),
])
def test_a_gradient_is_two_or_three_colours_on_an_aggregated_column(report: Path, slot: str, match: str,
                                                                    capsys):
    body = TABLE.split("      columns:")[0] + f"      columns: [{slot}]\n"
    assert _apply(report, body) != 0
    assert match in capsys.readouterr().err


def test_a_slot_that_has_no_gradient_in_its_contract_refuses_one(report: Path, capsys):
    body = ("page: Gradients\nlayout: one-up\nvisuals:\n  - {type: header, title: G}\n"
            "  - type: column\n    title: C\n    slots:\n      category: 'Sales[Country]'\n"
            "      value: {field: 'Sales[Amount]', aggregate: sum, gradient: 2}\n")
    assert _apply(report, body) != 0
    assert "column's value takes no gradient" in capsys.readouterr().err


# --- apply --------------------------------------------------------------------------------


def test_a_gradient_is_written_as_desktop_saved_it(report: Path):
    assert _apply(report) == 0
    _, doc = _table(report)
    two, three = doc["visual"]["objects"]["values"]
    # probe 44: backColor -> FillRule {Input: the projection's field, FillRule: {linearGradientN}}
    assert two["properties"]["backColor"]["solid"]["color"]["expr"]["FillRule"]["Input"] == {
        "Aggregation": {"Expression": {"Column": {"Expression": {"SourceRef": {"Entity": "Sales"}},
                                                  "Property": "Amount"}}, "Function": 0}}
    assert _stops(two) == ("linearGradient2", {"min": "'#6A00FF'", "max": "'#FF5E00'",
                                               "nullColoringStrategy": {"strategy": {"Literal": {"Value": "'asZero'"}}}})
    assert _stops(three)[0] == "linearGradient3"
    assert list(_stops(three)[1])[:3] == ["min", "mid", "max"]  # the middle key is `mid`
    assert _stops(three)[1]["mid"] == "'#00E5D8'"
    assert two["selector"] == {"data": [{"dataViewWildcard": {"matchingOption": 1}}],
                               "metadata": "Sum(Sales.Amount)"}
    assert three["selector"]["metadata"] == "Max(Sales.Amount)"
    queries = [p["queryRef"] for p in doc["visual"]["query"]["queryState"]["Values"]["projections"]]
    assert queries == ["Sales.Country", "Sum(Sales.Amount)", "Max(Sales.Amount)"]


def test_reapplying_changes_nothing_and_new_colours_rewrite_in_place(report: Path, capsys):
    assert _apply(report) == 0
    _, before = _table(report)
    capsys.readouterr()
    assert _apply(report) == 0
    assert "No changes" in capsys.readouterr().out
    assert _table(report)[1] == before

    assert _apply(report, flags=SET_B) == 0
    assert "gradient Sum(Sales.Amount), Max(Sales.Amount)" in capsys.readouterr().out
    _, after = _table(report)
    two, three = after["visual"]["objects"]["values"]
    assert _stops(two)[1]["min"] == "'#FF00C8'" and _stops(three)[1]["mid"] == "'#B7FF00'"
    assert len(after["visual"]["objects"]["values"]) == 2  # replaced, not appended


def test_a_gradient_without_the_guidelines_colours_is_refused_and_nothing_is_written(report: Path, capsys):
    before = sorted(p.name for p in report.rglob("*") if p.is_file())
    assert _apply(report, flags=["--set", "palette.minimum=#6A00FF", "--set", "palette.maximum=#FF5E00"]) != 0
    err = capsys.readouterr().err
    assert "gradient: 3 needs palette.minimum, palette.center and palette.maximum" in err
    assert sorted(p.name for p in report.rglob("*") if p.is_file()) == before


def test_what_the_user_set_in_values_survives_and_a_dropped_gradient_stays(report: Path, capsys):
    assert _apply(report) == 0
    f, doc = _table(report)
    user = {"properties": {"fontSize": render._literal("14D")}}
    doc["visual"]["objects"]["values"].insert(0, user)
    f.write_bytes(jsonfmt.dump_bytes(doc))
    # the spec no longer asks for the gradients: they are left, and the user's entry too
    body = TABLE.replace(", gradient: 2", "").replace(", gradient: 3", "")
    assert _apply(report, body, flags=[]) == 0
    values = _table(report)[1]["visual"]["objects"]["values"]
    assert values[0] == user and len(values) == 3


def test_rebinding_a_field_drops_the_gradient_that_named_it(report: Path):
    assert _apply(report) == 0
    body = TABLE.replace("aggregate: max, gradient: 3", "aggregate: min")
    assert _apply(report, body) == 0
    values = _table(report)[1]["visual"]["objects"]["values"]
    assert [v["selector"]["metadata"] for v in values] == ["Sum(Sales.Amount)"]


def test_with_gradients_leaves_a_document_with_no_gradient_untouched():
    doc = {"visual": {"visualType": "tableEx"}}
    assert render.with_gradients(copy.deepcopy(doc), {}) == (doc, [])


def test_check_compares_the_themes_divergent_colours_with_the_guidelines(report: Path, tmp_path: Path, capsys):
    import json

    g = tmp_path / "g.yaml"
    g.write_text("name: D\npalette: {categorical: ['#4E79A7', '#F28E2B'], minimum: '#6A00FF', "
                 "center: '#00E5D8', maximum: '#FF5E00'}\n")
    assert main(["theme", "--report", str(report), "--guidelines", str(g)]) == 0
    written = json.loads((report / "StaticResources/RegisteredResources/blueprint-theme.json").read_text())
    assert (written["minimum"], written["center"], written["maximum"]) == ("#6A00FF", "#00E5D8", "#FF5E00")

    def palette_findings(guide: Path) -> list[str]:
        capsys.readouterr()
        main(["check", "--report", str(report), "--guidelines", str(guide), "--json"])
        found = json.loads(capsys.readouterr().out)["findings"]
        return [f["message"] for f in found if f["rule"] == "palette" and "divergent" in f["message"]]

    assert palette_findings(g) == []
    g.write_text("name: D\npalette: {categorical: ['#4E79A7', '#F28E2B'], minimum: '#FF00C8'}\n")
    assert palette_findings(g) == [
        "theme 'blueprint-theme.json' divergent colour minimum is #6A00FF, palette says #FF00C8"]
