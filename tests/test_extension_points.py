"""The promises docs/extensions.md makes, as tests.

That document's claim is structural: extensions **add, never modify** — a new `extensions:`
sub-key, a new contract file, a new option line — and the core needs no change. It is the kind of
claim that rots quietly, because nothing breaks when it stops being true; the core simply starts
refusing something the document says is open, or ignoring something it says is read.

Each test here is a sentence in that file. What is already covered elsewhere is not repeated:
`tests/test_consistency.py` pins the five `extensions:` sub-keys the core reads (in both
directions, against `guidelines.py`'s own lookups), and `tests/test_visual_types.py` covers
contract loading, `inherits:` and `custom_visuals.search_path`.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from blueprint import guidelines, layouts, spec
from blueprint.cli import main
from blueprint.guidelines import GuidelinesError

ROOT = Path(__file__).resolve().parent.parent
GUIDE = ROOT / "guidelines" / "example.yaml"
BASE = (GUIDE).read_text(encoding="utf-8")


def _guidelines(tmp_path: Path, body: str, name: str = "g.yaml") -> Path:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


# --- section 1: extensions: is the one open section -----------------------------------------

def test_an_unknown_extensions_sub_key_loads_untouched(tmp_path: Path):
    """The open-section promise: the core reads the five sub-keys it knows and carries the rest
    through for an extension's own code to read, without refusing or rewriting them."""
    path = _guidelines(tmp_path, BASE + "\nextensions:\n"
                                        "  conditional_formatting:\n"
                                        "    rules: [{field: 'Sales[Amount]', over: 100}]\n"
                                        "  four_sided_margin: {top: 16, right: 24}\n")
    rules = guidelines.load(path)
    assert rules.raw["extensions"]["four_sided_margin"] == {"top": 16, "right": 24}
    assert rules.raw["extensions"]["conditional_formatting"]["rules"][0]["over"] == 100
    # and it changed nothing the core itself reads
    assert (rules.spacing.margin, rules.spacing.gutter) == (16, 16)


def test_a_typo_in_a_core_section_is_refused_with_the_closest_key(tmp_path: Path):
    """The counterpart, and the reason the open section has to be a *place*: docs/extensions.md
    cites `spacing: {margn: 16}`, which before v0.7 loaded with the default margin and checked
    nothing."""
    path = _guidelines(tmp_path, BASE.replace("margin: 16", "margn: 16"))
    with pytest.raises(GuidelinesError, match="did you mean margin"):
        guidelines.load(path)


@pytest.mark.parametrize("key", ["margin", "gutter"])
def test_a_core_spacing_key_cannot_be_widened_to_a_mapping(tmp_path: Path, key: str):
    """Why four-sided margins have to arrive as `extensions.four_sided_margin` and not as
    `spacing.margin: {top: …}`: the loader takes an integer there, so changing its type would be
    modifying the core, which is the one thing that document says extensions never do."""
    path = _guidelines(tmp_path, BASE.replace(f"{key}: 16", f"{key}: {{top: 16}}"))
    with pytest.raises(GuidelinesError, match=f"spacing.{key} must be an integer"):
        guidelines.load(path)


# --- section 3: the page spec is not an open dict -------------------------------------------

def test_a_slot_mapping_refuses_an_unknown_key_and_names_the_allowed_ones(tmp_path: Path):
    """docs/extensions.md section 3 is the one extension point in it that needs a core change,
    and says so: a misspelt `fromat` has to be an error, not something that silently does
    nothing, so a new long-form key means editing `spec._SLOT_KEYS`.

    `gradient` (v0.10.0, probe 44) is that core change having been made: the key list grew, and
    this test grew with it, which is the cost the doc promises."""
    problems: list[str] = []
    assert spec.parse_slot({"field": "Sales[Amount]", "fromat": "#,0"}, "at", problems) is None
    assert "field, aggregate, format, gradient" in problems[0]
    assert spec._SLOT_KEYS == ("field", "aggregate", "format", "gradient")


# --- section 4: an option is a line of YAML -------------------------------------------------

def test_an_option_declared_only_in_a_clients_contract_is_written_by_apply(tmp_path: Path):
    """The headline claim of docs/extensions.md ("what adding an option actually cost"): the
    render path is generic, so an option the core has never heard of is written from the
    contract alone, with no core change. `tooltip` is that option here — nothing in
    `blueprint/` mentions it.

    This is the whole extension point end to end: a contract in a directory of the client's
    own, reached with `--visuals`, declaring an option a spec then sets.
    """
    mine = tmp_path / "my-visuals"
    mine.mkdir()
    (mine / "waterfall.yaml").write_text(
        "type: waterfall\n"
        "visual_type: waterfallChart\n"   # free: no core contract claims it
        "inherits: column\n"
        "options:\n"
        "  tooltip: { object: tooltip, property: show, values: { \"on\": \"true\" } }\n",
        encoding="utf-8")
    spec_path = tmp_path / "ext.yaml"
    spec_path.write_text(
        "page: Ext\nlayout: one-up\nvisuals:\n"
        "  - type: header\n    title: Ext\n"
        "  - type: waterfall\n"
        "    title: W\n"
        "    options: { tooltip: \"on\" }\n"
        "    slots: { category: \"Sales[Region]\", value: \"[Total Amount]\" }\n",
        encoding="utf-8")
    shutil.copytree(ROOT / "fixtures" / "02-card-and-chart", tmp_path / "proj")
    report = tmp_path / "proj" / "Fixture.Report"

    assert main(["apply", str(spec_path), "--report", str(report), "--guidelines", str(GUIDE),
                 "--visuals", str(mine)]) == 0

    written = [p for p in report.rglob("visual.json")
               if "waterfallChart" in p.read_text(encoding="utf-8")]
    assert len(written) == 1, "the client's own type wasn't written"
    visual = json.loads(written[0].read_text(encoding="utf-8"))["visual"]
    assert visual["visualType"] == "waterfallChart"
    assert visual["objects"]["tooltip"] == [
        {"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}]
    # inherited from column, so the engine wrote the parent's bindings for it too
    assert "Category" in visual["query"]["queryState"]


def test_a_value_the_contract_does_not_declare_is_still_refused(tmp_path: Path):
    """Open to new options, not to unchecked values: the contract lists the values it allows,
    and a spec outside them is refused by name rather than written through."""
    mine = tmp_path / "my-visuals"
    mine.mkdir()
    (mine / "waterfall.yaml").write_text(
        "type: waterfall\nvisual_type: waterfallChart\ninherits: column\n"
        "options:\n  tooltip: { object: tooltip, property: show, values: { \"on\": \"true\" } }\n",
        encoding="utf-8")
    visual = {"type": "waterfall", "options": {"tooltip": "maybe"},
              "slots": {"category": "Sales[Region]", "value": "[Total Amount]"}}
    with pytest.raises(spec.SpecError, match="'maybe' isn't one of on"):
        spec.parse({"page": "P", "visuals": [visual]}, "p.yaml", visual_dirs=(mine,))


# --- section 5: layout regions, and the engine that was deliberately not built ---------------

def test_extra_keys_in_a_region_are_ignored_not_refused():
    """The asymmetry docs/extensions.md section 5 states, and warns about: a layout region
    carries an extension's own keys, but nothing in the core reads them, so a typo in one is
    silent. That is the opposite of the guidelines, where an unknown key is refused."""
    layout = layouts.parse({"name": "x", "canvas": {"width": 1280, "height": 720},
                            "regions": [{"role": "main", "x": 16, "y": 16, "w": 616, "h": 432,
                                         "min_height": 200, "backgroun": "#FFFFFF"}]})
    assert len(layout.regions) == 1
    assert layout.regions[0].rect.width == 616


def test_the_pixel_core_accepts_a_grid_that_does_not_divide_the_margin():
    """docs/extensions.md says the `margin % grid == 0` precondition belongs to the *relative*
    engine that computes regions flush to the margin, not to the pixel core — "a grid of 10 with
    a margin of 16 is fine, as long as the regions start at 20". Both halves checked, because the
    claim is only interesting if flush-to-margin really does fail there."""
    at_20 = layouts.parse({"name": "x", "canvas": {"width": 1280, "height": 720},
                           "regions": [{"role": "main", "x": 20, "y": 20, "w": 1240, "h": 680}]})
    assert layouts.conflicts(at_20, grid=10, margin=16, gutter=16) == []

    flush = layouts.parse({"name": "x", "canvas": {"width": 1280, "height": 720},
                           "regions": [{"role": "main", "x": 16, "y": 16, "w": 1248, "h": 688}]})
    assert layouts.conflicts(flush, grid=10, margin=16, gutter=16), "flush to a 16px margin on a grid of 10 should be off-grid"


# (2 columns, width, gap) — the table docs/extensions.md records as what a relative engine would
# have to produce, and template/layout.template.yaml hands to a client doing the arithmetic.
COLUMNS = [(1, 1248, 0), (2, 616, 16), (3, 400, 24), (4, 288, 32), (5, 224, 32), (6, 168, 48)]


@pytest.mark.parametrize("count, width, gap", COLUMNS)
def test_the_recorded_column_table_fills_the_canvas_on_the_grid(count, width, gap):
    """Equal tracks, equal gaps, every number a multiple of the grid, each gap at least the
    gutter, filling the usable span exactly — the rule both documents record so it needn't be
    re-derived. If these numbers were wrong, the advice in the layout template would be too."""
    usable = 1280 - 2 * 16
    assert count * width + (count - 1) * gap == usable
    assert width % 8 == 0 and gap % 8 == 0
    assert gap == 0 or gap >= 16  # the gutter is a minimum


def test_equal_division_is_why_the_relative_engine_waits():
    """The concrete reason docs/extensions.md gives for not computing regions: equal division
    rarely lands on the grid, and snapping afterwards pushes a region past the margin or pulls
    two inside the gutter — exactly what `conflicts()` refuses."""
    usable = 1280 - 2 * 16
    assert round((usable - 2 * 16) / 3, 2) == 405.33   # three columns, 16px gaps
    assert (usable - 3 * 16) / 4 == 300 and 300 % 8 != 0  # four columns: a whole number, off-grid


def test_the_shipped_layouts_use_the_recorded_numbers():
    """And the rule reproduces the shipped layouts' own widths, which is the document's claim
    that it "could land without changing a byte of output"."""
    widths = {w for _, w, _ in COLUMNS}
    for name in layouts.available((ROOT / "guidelines" / "layouts",)):
        layout = layouts.load(name, (ROOT / "guidelines" / "layouts",))
        assert {r.rect.width for r in layout.regions} <= widths, name


# --- section 6: validation rules ------------------------------------------------------------

def test_the_documented_rule_list_is_the_real_one():
    """docs/extensions.md enumerates the core rules, and the list it shipped with had drifted:
    it omitted `format` and `page-size` and offered `palette` as if it were one of
    `guidelines.RULES`. Rule ids are a CI contract, so the prose that names them is pinned to
    the constant, the way the README's flags are pinned to the parser."""
    import re

    text = (ROOT / "docs" / "extensions.md").read_text(encoding="utf-8")
    listed = re.search(r"`guidelines\.RULES` is the list:\n  `([^`]+)`", text)
    assert listed, "docs/extensions.md no longer enumerates guidelines.RULES"
    names = {n.strip() for n in listed.group(1).replace("\n", " ").split(",")}
    assert names == set(guidelines.RULES), (
        f"doc says {sorted(names)}, guidelines.RULES says {sorted(guidelines.RULES)}")


def test_palette_is_a_rule_id_but_not_one_extensions_severity_accepts(tmp_path: Path):
    """The exception the document now states: `palette`'s severity comes from `palette.enforce`,
    so naming it under `extensions.severity` is refused even though findings carry that id."""
    assert "palette" not in guidelines.RULES
    path = _guidelines(tmp_path, BASE + "\nextensions:\n  severity: {palette: warning}\n")
    with pytest.raises(GuidelinesError, match="unknown rule 'palette'"):
        guidelines.load(path)

    for enforce, severity in (("strict", "error"), ("warn", "warning"), ("off", "off")):
        rules = guidelines.load(_guidelines(
            tmp_path, BASE.replace("enforce: strict", f"enforce: {enforce}"), f"{enforce}.yaml"))
        assert rules.palette.severity == severity
