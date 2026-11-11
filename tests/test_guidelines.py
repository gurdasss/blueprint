from pathlib import Path

import pytest
import yaml

from blueprint import guidelines


def test_defaults():
    g = guidelines.load()
    assert (g.spacing, g.max_resize, g.sources) == (
        guidelines.Spacing(grid=8, margin=0, gutter=0), 0.25, ("defaults",))
    assert g.check.severity == guidelines.DEFAULT_SEVERITY
    assert g.check.decorative_types == guidelines.DEFAULT_DECORATIVE_TYPES


def test_max_resize_null_disables(tmp_path: Path):
    f = tmp_path / "g.yaml"
    f.write_text("extensions: {max_resize: null}\n")
    assert guidelines.load(f).max_resize is None


def test_layering_order(tmp_path: Path, monkeypatch):
    org = tmp_path / "org.yaml"
    org.write_text("name: Org\nspacing: {grid: 4}\n")
    report = tmp_path / "R.Report"
    report.mkdir()
    (report / ".blueprint.yaml").write_text("spacing: {grid: 12}\n")

    assert guidelines.load(org).spacing.grid == 4
    g = guidelines.load(org, report)
    assert (g.name, g.spacing.grid, g.spacing.margin) == ("Org", 12, 0)  # margin still from defaults
    assert guidelines.load(org, report, {"spacing": {"grid": 16}}).spacing.grid == 16

    monkeypatch.setenv(guidelines.ENV_VAR, str(org))
    assert guidelines.load().spacing.grid == 4


@pytest.mark.parametrize("body", [
    "spacing: {grid: 0}", "spacing: {grid: '8'}", "spacing: {margin: '16'}",
    "extensions: {max_resize: -1}", "extensions: {max_resize: '25%'}", "- a",
    "extensions: [severity]",
])
def test_invalid_values_rejected(tmp_path: Path, body: str):
    f = tmp_path / "g.yaml"
    f.write_text(body)
    with pytest.raises(guidelines.GuidelinesError):
        guidelines.load(f)


@pytest.mark.parametrize(("body", "match"), [
    ("extensions: {severity: {colour: error}}", "unknown rule 'colour'"),
    ("extensions: {severity: {grid: fatal}}", "extensions.severity.grid must be one of"),
    ("page: {density_policy: lenient}", "page.density_policy must be one of all, data, visible"),
    ("spacing: {margin: -1}", "spacing.margin"),
    ("extensions: {decorative_types: image}", "decorative_types"),
])
def test_check_config_rejected(tmp_path: Path, body: str, match: str):
    f = tmp_path / "g.yaml"
    f.write_text(body)
    with pytest.raises(guidelines.GuidelinesError, match=match):
        guidelines.load(f)


@pytest.mark.parametrize(("body", "match"), [
    ("page: {density_policy: {visible: true}}\n", "page.density_policy must be one of"),
    ("extensions: {severity: {grid: [error]}}\n", r"extensions.severity.grid must be one of"),
    ("palette: {enforce: {strict: true}}\n", "palette.enforce must be strict, warn or off"),
    ("typography: {visual_title: {font: Arial, 1: x, null: y}}\n",
     "typography.visual_title: unknown keys 1, None"),
])
def test_wrong_types_are_errors_not_crashes(tmp_path: Path, body: str, match: str):
    """Found by fuzzing guidelines files: a mapping where a name was expected, or keys that
    aren't text, raised TypeError tracebacks instead of a GuidelinesError (exit 2)."""
    f = tmp_path / "g.yaml"
    f.write_text(body)
    with pytest.raises(guidelines.GuidelinesError, match=match):
        guidelines.load(f)


# --- the pre-template schema: refused, with the new key named ----------------------------

@pytest.mark.parametrize(("body", "match"), [
    ("grid: {size: 8}\n", r"grid\.size was replaced by spacing\.grid"),
    ("grid: {snap: true}\n", r"grid\.snap was replaced by"),
    ("grid: {max_resize: 0.5}\n", r"grid\.max_resize was replaced by extensions\.max_resize"),
    ("canvas: {margin: 16}\n", r"canvas\.margin was replaced by spacing\.margin"),
    ("canvas: {gutter: 16}\n", r"canvas\.gutter was replaced by spacing\.gutter"),
    ("check: {severity: {grid: warning}}\n", r"check\.severity was replaced by extensions\.severity"),
    ("check: {decorative_types: [image]}\n", r"check\.decorative_types was replaced by"),
    ("grid: {}\n", r"the grid: section was replaced by spacing\.grid"),
    ("check: {}\n", r"the check: section moved to extensions"),
    ("typography: {title: {size: 12}}\n",
     r"typography\.title was replaced by typography\.visual_title"),
    ("typography: {header: {size: 20}}\n",
     r"typography\.header was replaced by typography\.page_title"),
    ("typography: {heading: {size: 20}}\n", r"typography\.heading: unknown role"),
    ("typography: {callout: {size: 28}}\n",
     r"typography\.callout is an extension role; move it to extensions\.typography\.callout"),
])
def test_retired_keys_name_their_replacement(tmp_path: Path, body: str, match: str):
    f = tmp_path / "g.yaml"
    f.write_text(body)
    with pytest.raises(guidelines.GuidelinesError, match=match):
        guidelines.load(f)


def test_retired_key_names_the_file_that_carries_it(tmp_path: Path):
    org = tmp_path / "org.yaml"
    org.write_text("name: Org\n")
    report = tmp_path / "R.Report"
    report.mkdir()
    (report / ".blueprint.yaml").write_text("canvas: {margin: 16}\n")
    with pytest.raises(guidelines.GuidelinesError, match=r"\.blueprint\.yaml: canvas\.margin"):
        guidelines.load(org, report)


def test_the_shipped_template_and_example_load():
    """template/guidelines.template.yaml is what a client starts from: it must be accepted as
    written, and so must the example this repo ships."""
    root = Path(__file__).resolve().parent.parent
    template = guidelines.load(root / "template" / "guidelines.template.yaml")
    assert (template.spacing, template.page.density_policy) == (
        guidelines.Spacing(grid=8, margin=16, gutter=16), "data")
    assert sorted(template.typography) == ["header", "textbox", "title"]
    example = guidelines.load(root / "guidelines" / "example.yaml")
    assert (example.spacing.margin, example.page.max_visuals) == (16, 6)


# --- typography: three core roles, mapped to the internal checking roles ------------------

def test_core_roles_map_to_internal_roles(tmp_path: Path):
    f = tmp_path / "g.yaml"
    f.write_text("typography:\n"
                 "  page_title: {font: Segoe UI Semibold, size: 20}\n"
                 "  visual_title: {font: Segoe UI, size: 12}\n"
                 "  body: {font: Segoe UI, size: 10}\n")
    g = guidelines.load(f)
    assert sorted(g.typography) == ["header", "textbox", "title"]
    assert g.typography["header"] == guidelines.FontRule(("Segoe UI Semibold",), (20.0,))


def test_extension_roles_come_from_extensions(tmp_path: Path):
    f = tmp_path / "g.yaml"
    f.write_text("typography: {visual_title: {size: 12}}\n"
                 "extensions:\n"
                 "  typography:\n"
                 "    callout: {font: Segoe UI Light, size: 32}\n"
                 "    card_label: {font: Arial, size: 14}\n")
    g = guidelines.load(f)
    assert sorted(g.typography) == ["callout", "card_label", "title"]
    assert g.typography["callout"].sizes == (32.0,)


def test_a_core_role_under_extensions_is_refused(tmp_path: Path):
    f = tmp_path / "g.yaml"
    f.write_text("extensions: {typography: {page_title: {size: 20}}}\n")
    with pytest.raises(guidelines.GuidelinesError,
                       match="extensions.typography.page_title: unknown role"):
        guidelines.load(f)


# --- the core 20%: a key outside it is refused, never silently ignored ----------------------


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "g.yaml"
    path.write_text("version: 1\nname: T\n" + body, encoding="utf-8")
    return path


@pytest.mark.parametrize(("body", "names"), [
    ("spacing: {grid: 8, margn: 16}", ("spacing.margn", "margin")),       # a typo in a core sub-key
    ("palette: {categoricals: ['#FFFFFF']}", ("palette.categoricals", "categorical")),
    ("page: {max_visual: 6}", ("page.max_visual", "max_visuals")),
    ("spacingg: {grid: 8}", ("spacingg", "spacing")),                      # a typo in a section
    ("canvas: {width: 8, bleed: 4}", ("canvas.bleed", "")),                # a key the core doesn't have
])
def test_a_key_outside_the_core_is_refused_with_the_closest_one_named(tmp_path, body, names):
    """It used to load: `spacing: {margn: 16}` left margin at its default and checked nothing, so
    the client's file said one thing and `bp check` did another. "Refuse rather than surprise"."""
    key, suggestion = names
    with pytest.raises(guidelines.GuidelinesError) as err:
        guidelines.load(_write(tmp_path, body))
    assert key in str(err.value)
    if suggestion:
        assert f"did you mean {suggestion}" in str(err.value)


def test_extensions_stay_open_so_an_extension_can_add_its_own_keys(tmp_path):
    """`extensions:` is the pass-through (template/extensions.md): the core reads five sub-keys
    and must not refuse the rest, or no extension could ship without a core change."""
    rules = guidelines.load(_write(tmp_path, "extensions:\n  conditional_formatting: {rules: []}\n"))
    assert rules.raw["extensions"]["conditional_formatting"] == {"rules": []}


def test_core_keys_lists_exactly_what_defaults_yaml_ships():
    """CORE_KEYS is what the loader accepts and defaults.yaml is what ships: a key in one and not
    the other means a client can write something the defaults never mention, or the reverse."""
    defaults = yaml.safe_load(guidelines.DEFAULTS.read_text(encoding="utf-8"))
    for section, value in defaults.items():
        assert section in guidelines.CORE_KEYS, f"defaults.yaml ships {section}, CORE_KEYS doesn't"
        if isinstance(value, dict):
            assert set(value) <= set(guidelines.CORE_KEYS[section]), section
