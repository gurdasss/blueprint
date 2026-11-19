"""Where a spec reaches the end of what it can express, Blueprint says so at that moment.

Summarising a column in a visual works, but it is the whole of what a spec can ask for: year-
over-year, % of total, running totals and Top N need a measure in the model, and Blueprint never
creates one. These notes turn a silent quality loss into a named boundary. What apply writes is
unchanged: the golden tests and probe replays compare it byte for byte.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from blueprint.cli import main
from blueprint.commands.apply import SUMMARISED_COLUMN

ROOT = Path(__file__).resolve().parent.parent
GUIDE = ROOT / "guidelines" / "example.yaml"
SPEC = """page: P
layout: two-up
visuals:
  - type: header
    title: P
  - type: card
    title: Total
    slots:
      value: {value}
  - type: column
    title: By Country
    slots:
      category: "Sales[Country]"
      value: {value}
"""


def _apply(tmp_path: Path, name: str, value: str, capsys) -> str:
    report = tmp_path / name / "report"
    shutil.copytree(ROOT / "fixtures" / "02-card-and-chart", report)
    spec = tmp_path / name / "p.yaml"
    spec.write_text(SPEC.replace("{value}", value))
    capsys.readouterr()
    assert main(["apply", str(spec), "--report", str(report), "--guidelines", str(GUIDE)]) == 0
    return capsys.readouterr().out


def test_a_summarised_column_names_the_boundary_and_a_measure_does_not(tmp_path: Path, capsys):
    out = _apply(tmp_path, "agg", '{field: "Sales[Amount]", aggregate: sum}', capsys)
    assert "Notes:" in out and SUMMARISED_COLUMN in out
    assert "card-1 (sum of Sales[Amount]), column-1 (sum of Sales[Amount])" in out
    out = _apply(tmp_path, "measure", '"[Total Amount]"', capsys)
    assert "Notes:" not in out and SUMMARISED_COLUMN not in out


def test_describe_says_when_the_model_has_no_measures(tmp_path: Path, capsys):
    report = tmp_path / "proj"
    shutil.copytree(ROOT / "fixtures" / "02-card-and-chart", report)
    describe = ["describe", "--report", str(report), "--guidelines", str(GUIDE), "--json",
                "--section", "model"]
    assert main(describe) == 0
    assert json.loads(capsys.readouterr().out)["model"]["notes"] == []  # it has [Total Amount]
    tmdl = next((report / "Fixture.SemanticModel" / "definition" / "tables").glob("*.tmdl"))
    tmdl.write_text("\n".join(line for line in tmdl.read_text().split("\n")
                              if not line.startswith("\tmeasure")))
    assert main(describe) == 0
    notes = json.loads(capsys.readouterr().out)["model"]["notes"]
    assert len(notes) == 1 and "no visible measures" in notes[0] and "never creates measures" in notes[0]
