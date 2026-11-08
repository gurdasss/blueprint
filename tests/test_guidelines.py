from pathlib import Path

import pytest

from blueprint import guidelines


def test_defaults():
    g = guidelines.load()
    assert (g.grid.size, g.grid.snap, g.sources) == (8, True, ("defaults",))


def test_layering_order(tmp_path: Path, monkeypatch):
    org = tmp_path / "org.yaml"
    org.write_text("name: Org\ngrid: {size: 4}\n")
    report = tmp_path / "R.Report"
    report.mkdir()
    (report / ".blueprint.yaml").write_text("grid: {size: 12}\n")

    assert guidelines.load(org).grid.size == 4
    g = guidelines.load(org, report)
    assert (g.name, g.grid.size, g.grid.snap) == ("Org", 12, True)  # snap still from defaults
    assert guidelines.load(org, report, {"grid": {"size": 16}}).grid.size == 16

    monkeypatch.setenv(guidelines.ENV_VAR, str(org))
    assert guidelines.load().grid.size == 4


@pytest.mark.parametrize("body", ["grid: {size: 0}", "grid: {size: '8'}", "grid: {snap: 1}", "- a"])
def test_invalid_values_rejected(tmp_path: Path, body: str):
    f = tmp_path / "g.yaml"
    f.write_text(body)
    with pytest.raises(guidelines.GuidelinesError):
        guidelines.load(f)
