"""Blueprint end to end on every local sample report (real, Desktop-saved PBIPs; samples/README.md).

What held on Microsoft's Procurement, Sales and Marketing, and Supplier Quality samples (and was
then opened in Desktop: every page drew with real data): the reader takes them without warnings,
the TMDL reader finds every measure and column the files declare, and a spec built from the
report's own visible fields applies cleanly, passes `check`, and re-applies as a no-op.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from blueprint import guidelines
from blueprint.cli import main
from blueprint.commands.describe import _model
from blueprint.pbir import semantic
from blueprint.pbir.reader import read_report
from blueprint.validate import check_report

ROOT = Path(__file__).resolve().parent.parent
GUIDE = ROOT / "guidelines" / "example.yaml"


def _model_dir(report: Path) -> Path:
    r = read_report(report)
    pbir = r.source.documents[Path("definition.pbir")].data
    return semantic.model_dir_for(r.root, pbir)


def test_reads_without_warnings(real_report: Path):
    r = read_report(real_report)
    assert r.warnings == []
    assert r.pages and sum(len(p.visuals) for p in r.pages)


def test_tmdl_reader_finds_every_declared_member(real_report: Path):
    tables = _model_dir(real_report) / "definition" / "tables"
    text = "\n".join(f.read_text(encoding="utf-8-sig") for f in tables.glob("*.tmdl"))
    declared_measures = len(re.findall(r"^\tmeasure ", text, re.MULTILINE))
    declared_columns = len(re.findall(r"^\tcolumn ", text, re.MULTILINE))
    m = semantic.load(_model_dir(real_report))
    assert sum(len(homes) for homes in m.measures.values()) == declared_measures
    assert sum(len(cols) for cols in m.tables.values()) == declared_columns


def _visible_fields(report: Path) -> tuple[str, list[str]]:
    """The first visible measure, and the visible columns of the first table that has two."""
    tables = _model(read_report(report))["tables"]
    measure = next(m.split("  (")[0] for t in tables.values() for m in t["measures"]
                   if "ambiguous" not in m)
    columns = next(t["columns"][:2] for t in tables.values() if len(t["columns"]) >= 2)
    return measure, columns


def test_a_spec_of_its_own_fields_applies_checks_clean_and_reapplies_as_a_no_op(
        real_report: Path, tmp_path: Path, capsys):
    proj = tmp_path / "proj"
    shutil.copytree(real_report.parent, proj, ignore=shutil.ignore_patterns(".pbi"))
    measure, (col_a, col_b) = _visible_fields(proj)
    spec = tmp_path / "real.yaml"
    spec.write_text(
        "page: Blueprint Test\nlayout: standard-4-up\nvisuals:\n"
        "  - {type: header, title: Blueprint Test}\n"
        f"  - {{type: slicer, region: kpi-row, options: {{style: dropdown}}, slots: {{field: \"{col_a}\"}}}}\n"
        f"  - {{type: card, title: Card, slots: {{value: \"{measure}\"}}}}\n"
        f"  - {{type: table, title: Table, slots: {{columns: [\"{col_a}\", \"{col_b}\", \"{measure}\"]}}}}\n")
    args = ["apply", str(spec), "--report", str(proj), "--guidelines", str(GUIDE)]
    assert main(args) == 0, capsys.readouterr().err
    report = read_report(proj)
    [page] = [p for p in report.pages if p.spec]
    assert len(page.visuals) == 4
    found = [f for f in check_report(report, guidelines.load(GUIDE)).findings if f.page == page.name]
    assert found == []
    capsys.readouterr()
    assert main(args) == 0
    assert capsys.readouterr().out.startswith("No changes.")
