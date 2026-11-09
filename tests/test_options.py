"""Spec `options:`: formatting choices a contract declares (the slicer's Dropdown style, probes 20, 22)."""

import shutil
from pathlib import Path

import pytest

from blueprint import spec
from blueprint.cli import main
from blueprint.pbir import jsonfmt
from blueprint.slots import contracts

ROOT = Path(__file__).resolve().parent.parent
GUIDE = ROOT / "guidelines" / "example.yaml"
DROPDOWN = {"data": [{"properties": {"mode": {"expr": {"Literal": {"Value": "'Dropdown'"}}}}}]}


def _spec(visual: dict) -> spec.PageSpec:
    return spec.parse({"page": "P", "visuals": [visual]}, "p.yaml")


def test_contract_declares_the_slicer_style():
    [opt] = contracts()["slicer"].options.values()
    assert (opt.name, opt.object, opt.property, opt.values) == ("style", "data", "mode", {"dropdown": "'Dropdown'"})


@pytest.mark.parametrize(("visual", "match"), [
    ({"type": "slicer", "slots": {"field": "Sales[Country]"}, "options": {"style": "tiles"}},
     r"visuals\[0\]\.options\.style: 'tiles' isn't one of dropdown"),
    ({"type": "slicer", "slots": {"field": "Sales[Country]"}, "options": {"colour": "red"}},
     r"visuals\[0\]\.options\.colour: slicer has no option 'colour' \(options: style\)"),
    ({"type": "card", "slots": {"value": "[A]"}, "options": {"style": "dropdown"}},
     r"card has no option 'style' \(options: none\)"),
    ({"type": "slicer", "slots": {"field": "Sales[Country]"}, "options": "dropdown"},
     r"visuals\[0\]\.options: must be a mapping"),
])
def test_invalid_options(visual, match):
    with pytest.raises(spec.SpecError, match=match):
        _spec(visual)


def _apply(tmp_path: Path, options: str, capsys) -> tuple[int, str]:
    s = tmp_path / "s.yaml"  # same file name every time: same spec id, same page
    s.write_text("page: S\nlayout: standard-4-up\nvisuals:\n  - {type: header, title: S}\n"
                 f"  - {{type: slicer, slots: {{field: 'Sales[Country]'}}{options}}}\n")
    capsys.readouterr()
    code = main(["apply", str(s), "--report", str(tmp_path / "proj"), "--guidelines", str(GUIDE)])
    out = capsys.readouterr()
    return code, out.out + out.err


def _slicer(tmp_path: Path) -> dict:
    [doc] = [d for f in (tmp_path / "proj").rglob("visual.json")
             if (d := jsonfmt.load(f))["visual"]["visualType"] == "slicer"]
    return doc


def test_dropdown_is_written_as_desktop_wrote_it_and_rerun_rules(tmp_path: Path, capsys):
    shutil.copytree(ROOT / "fixtures" / "02-card-and-chart", tmp_path / "proj")
    assert _apply(tmp_path, ", options: {style: dropdown}", capsys)[0] == 0
    assert _slicer(tmp_path)["visual"]["objects"] == DROPDOWN
    code, out = _apply(tmp_path, ", options: {style: dropdown}", capsys)
    assert code == 0 and out.startswith("No changes.")
    code, out = _apply(tmp_path, "", capsys)  # left out: Desktop's (or the user's) to set
    assert code == 0 and out.startswith("No changes.")


def test_changing_an_option_on_rerun_is_refused(tmp_path: Path, capsys):
    shutil.copytree(ROOT / "fixtures" / "02-card-and-chart", tmp_path / "proj")
    assert _apply(tmp_path, "", capsys)[0] == 0
    assert "objects" not in _slicer(tmp_path)["visual"]  # Desktop's default style
    code, out = _apply(tmp_path, ", options: {style: dropdown}", capsys)
    assert code == 2 and "option(s) style differ from the report" in out


def test_unquoted_on_in_a_spec_means_on():
    import yaml
    raw = yaml.safe_load("page: P\nvisuals:\n  - {type: column, slots: {category: 'Sales[Country]', "
                         "value: '[A]'}, options: {labels: on, legend: right}}\n")
    [v] = spec.parse(raw, "p.yaml").visuals
    assert v.options == {"labels": "on", "legend": "right"}
    with pytest.raises(spec.SpecError, match=r"options\.labels: 'off' isn't one of on"):
        spec.parse(yaml.safe_load("page: P\nvisuals:\n  - {type: column, slots: {category: 'S[C]', "
                                  "value: '[A]'}, options: {labels: off}}\n"), "p.yaml")


def test_contract_option_keys_must_be_strings(tmp_path, monkeypatch):
    from blueprint import slots
    (tmp_path / "x.yaml").write_text("type: x\nvisual_type: x\nregion: main\nslots: {}\n"
                                     "options: {labels: {object: labels, property: show, values: {on: 'true'}}}\n")
    with pytest.raises(slots.ContractError, match="values keys must be strings"):
        slots._load(tmp_path / "x.yaml")
