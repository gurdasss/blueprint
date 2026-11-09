"""Read just enough of a PBIP semantic model (TMDL) to resolve spec field references.

Blueprint never edits the model (that's the Modeling MCP's job). It only needs to know which
tables exist, which columns they have, and which table each measure lives in, because PBIR
binds a measure through its home table (``Entity``), and a spec's ``[Total Amount]`` doesn't
name one.

TMDL shapes relied on, as seen in the fixture and the sample model (``definition/tables/*.tmdl``):

    table Sales                                  # or: table 'Sales Data'
    \tmeasure 'Total Amount' = SUM(Sales[Amount])  # or: measure TotalSales = …
    \tcolumn Country                               # or: column 'Order Date'

Names are bare, or single-quoted with ``''`` for a literal quote. Only lines indented by exactly
one tab are table members; deeper lines are properties and expressions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

_NAME = r"(?:'(?P<q>(?:[^']|'')+)'|(?P<b>[^\s=']+(?: [^\s=']+)*?))"
_TABLE = re.compile(rf"^table {_NAME}\s*$")
_MEMBER = re.compile(rf"^\t(?P<kind>measure|column) {_NAME}(?:\s*=.*)?\s*$")


class ModelError(Exception):
    pass


@dataclass
class SemanticModel:
    tables: dict[str, set[str]] = field(default_factory=dict)  # table -> columns
    measures: dict[str, list[str]] = field(default_factory=dict)  # measure -> home table(s)

    def measure_table(self, name: str) -> str:
        homes = self.measures.get(name, [])
        if not homes:
            raise ModelError(f"no measure [{name}] in the semantic model")
        if len(homes) > 1:
            raise ModelError(f"measure [{name}] exists in several tables ({', '.join(homes)}); "
                             "Blueprint can't tell which one you mean")
        return homes[0]

    def check_column(self, table: str, column: str) -> None:
        if table not in self.tables:
            raise ModelError(f"no table {table!r} in the semantic model "
                             f"(tables: {', '.join(sorted(self.tables)) or 'none'})")
        if column not in self.tables[table]:
            raise ModelError(f"table {table!r} has no column {column!r}")


def _name(m: re.Match) -> str:
    return m["q"].replace("''", "'") if m["q"] is not None else m["b"]


def parse_table(text: str, source: str = "<tmdl>") -> tuple[str, set[str], set[str]]:
    """(table name, columns, measures) from one ``tables/<name>.tmdl`` file."""
    lines = text.replace("\r\n", "\n").split("\n")
    head = next((ln for ln in lines if ln.strip()), "")
    m = _TABLE.match(head.lstrip("﻿"))
    if not m:
        raise ModelError(f"{source}: expected 'table <name>' on the first line, got {head[:60]!r}")
    columns: set[str] = set()
    measures: set[str] = set()
    for line in lines:
        mm = _MEMBER.match(line)
        if mm:
            (measures if mm["kind"] == "measure" else columns).add(_name(mm))
    return _name(m), columns, measures


def load(model_dir: Path) -> SemanticModel:
    if not (model_dir / "definition").is_dir():
        raise ModelError(f"{model_dir}: no definition folder (is it a TMDL semantic model?)")
    tables_dir = model_dir / "definition" / "tables"
    model = SemanticModel()
    if not tables_dir.is_dir():
        return model  # a new report's model has no tables yet (fixtures/01-blank-report)
    for f in sorted(tables_dir.glob("*.tmdl")):
        try:
            text = f.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError) as exc:
            raise ModelError(f"{f.name}: can't read the model file ({exc})") from exc
        table, columns, measures = parse_table(text, f.name)
        model.tables[table] = columns
        for m in sorted(measures):
            model.measures.setdefault(m, []).append(table)
    return model


def model_dir_for(report_dir: Path, definition_pbir: dict) -> Path:
    """The semantic model folder a report binds to via ``datasetReference.byPath`` (probe 04)."""
    ref = (definition_pbir or {}).get("datasetReference") or {}
    by_path = (ref.get("byPath") or {}).get("path")
    if not isinstance(by_path, str) or not by_path:
        kind = "byConnection" if "byConnection" in ref else "no datasetReference"
        raise ModelError(f"report uses {kind}; binding fields needs a local semantic model "
                         "(datasetReference.byPath)")
    path = (report_dir / by_path).resolve()
    if not path.is_dir():
        raise ModelError(f"semantic model folder {by_path!r} not found next to the report")
    return path
