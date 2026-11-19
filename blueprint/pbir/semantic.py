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

Hierarchies built in the model (probe 16) are table members too, with their levels two tabs in:

    \thierarchy Geography
    \t\tlevel Country
    \t\t\tcolumn: Country

A member's properties are lines two tabs in, ``key: value``. ``describe`` reports four of them
as written (``FIELD_PROPERTIES``): ``dataType``, ``sortByColumn`` (a column of the same table,
bare or quoted), ``summarizeBy`` and ``formatString`` (the raw string, backslashes included).
``relationships.tmdl`` holds ``relationship <id>`` blocks with one-tab-in ``fromColumn:`` and
``toColumn:`` (``Table.Column``, either part bare or quoted) and any other properties. All of
these shapes were read from Microsoft's three sample models. None of them has a dynamic format
string (``formatStringDefinition``), so that shape is unverified and not read: a measure that
uses one shows ``format_string: null``.
"""

from __future__ import annotations

import difflib
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

_NAME = r"(?:'(?P<q>(?:[^']|'')+)'|(?P<b>[^\s=']+(?: [^\s=']+)*?))"
_TABLE = re.compile(rf"^table {_NAME}\s*$")
_MEMBER = re.compile(rf"^\t(?P<kind>measure|column) {_NAME}(?:\s*=.*)?\s*$")
_HIERARCHY = re.compile(rf"^\thierarchy {_NAME}\s*$")
_LEVEL = re.compile(rf"^\t\tlevel {_NAME}\s*$")
_PROPERTY = re.compile(r"^\t\t(?P<key>[A-Za-z]+):\s*(?P<value>.*?)\s*$")
_RELATIONSHIP = re.compile(r"^relationship (?P<id>\S+)\s*$")
_REL_PROPERTY = re.compile(r"^\t(?P<key>[A-Za-z]+):\s*(?P<value>.*?)\s*$")
# Table.Column, each part bare or single-quoted ('' for a literal quote).
_QUALIFIED = re.compile(r"^(?:'(?P<tq>(?:[^']|'')+)'|(?P<tb>[^.']+))\.(?:'(?P<cq>(?:[^']|'')+)'|(?P<cb>.+))$")

# TMDL member properties describe reports, as written; a member that doesn't write one gets None.
FIELD_PROPERTIES = {"dataType": "data_type", "sortByColumn": "sort_by", "summarizeBy": "summarize_by",
                    "formatString": "format_string"}


class ModelError(Exception):
    pass


def _did_you_mean(name: str, candidates: Iterable[str], show: Callable[[str], str] = str) -> str:
    """A hint for a name that isn't in the model: the same name in another case (Power BI
    names are case-insensitive, so agents often get the case wrong), else close spellings."""
    pool = sorted(set(candidates))
    same = [c for c in pool if c.lower() == name.lower()]
    close = same or difflib.get_close_matches(name, pool, n=3, cutoff=0.75)
    return f" (did you mean {' or '.join(show(c) for c in close)}?)" if close else ""


@dataclass(frozen=True)
class Relationship:
    """One ``relationship`` block: its two columns, and every other property as written."""
    id: str
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    properties: dict[str, str]


@dataclass
class SemanticModel:
    tables: dict[str, set[str]] = field(default_factory=dict)  # table -> columns
    measures: dict[str, list[str]] = field(default_factory=dict)  # measure -> home table(s)
    hierarchies: dict[tuple[str, str], tuple[str, ...]] = field(default_factory=dict)  # (table, name) -> levels
    hidden_tables: set[str] = field(default_factory=set)  # `isHidden` tables (e.g. Desktop's auto-date ones)
    hidden: set[tuple[str, str]] = field(default_factory=set)  # (table, column or measure) marked `isHidden`
    # (table, column or measure) -> the FIELD_PROPERTIES it writes, by TMDL key, values as written
    properties: dict[tuple[str, str], dict[str, str]] = field(default_factory=dict)
    relationships: list[Relationship] = field(default_factory=list)

    def measure_table(self, name: str) -> str:
        homes = self.measures.get(name, [])
        if not homes:
            raise ModelError(f"no measure [{name}] in the semantic model"
                             + _did_you_mean(name, self.measures, lambda c: f"[{c}]"))
        if len(homes) > 1:
            raise ModelError(f"measure [{name}] exists in several tables ({', '.join(homes)}); "
                             "Blueprint can't tell which one you mean")
        return homes[0]

    def check_column(self, table: str, column: str) -> None:
        if table not in self.tables:
            raise ModelError(f"no table {table!r} in the semantic model "
                             f"(tables: {', '.join(sorted(self.tables)) or 'none'})"
                             + _did_you_mean(table, self.tables, repr))
        if column not in self.tables[table]:
            hint = _did_you_mean(column, self.tables[table], lambda c: f"{table}[{c}]")
            if not hint and column in self.measures:
                hint = f" ({column!r} is a measure: write it as [{column}])"
            raise ModelError(f"table {table!r} has no column {column!r}{hint}")

    def check_hierarchy_level(self, table: str, hierarchy: str, level: str) -> None:
        if table not in self.tables:
            raise ModelError(f"no table {table!r} in the semantic model"
                             + _did_you_mean(table, self.tables, repr))
        levels = self.hierarchies.get((table, hierarchy))
        if levels is None:
            raise ModelError(f"table {table!r} has no hierarchy {hierarchy!r}"
                             + _did_you_mean(hierarchy, [h for t, h in self.hierarchies if t == table],
                                             lambda c: f"{table}[{c}]"))
        if level not in levels:
            raise ModelError(f"hierarchy {hierarchy!r} has no level {level!r} (levels: {', '.join(levels)})")


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


def parse_hidden(text: str) -> tuple[bool, set[str]]:
    """(is the table hidden, names of its hidden columns and measures) from one table file.
    TMDL writes ``isHidden`` as a property line: one tab in for the table, two tabs in under the
    member it belongs to (seen in Microsoft's sample models, e.g. auto-date tables, ID columns)."""
    table_hidden, hidden, member = False, set(), None
    for line in text.replace("\r\n", "\n").split("\n"):
        if line == "\tisHidden" or line.startswith("\tisHidden "):
            table_hidden = True
            continue
        m = _MEMBER.match(line)
        if m:
            member = _name(m)
        elif line.startswith("\t") and not line.startswith("\t\t") and line.strip():
            member = None  # another kind of member (hierarchy, partition, annotation)
        elif member and line.strip() == "isHidden" and line.startswith("\t\t") and not line.startswith("\t\t\t"):
            hidden.add(member)
    return table_hidden, hidden


def _unquote(name: str) -> str:
    """A TMDL name as written in a property value: bare, or single-quoted with '' for '."""
    return name[1:-1].replace("''", "'") if len(name) >= 2 and name[0] == name[-1] == "'" else name


def parse_properties(text: str) -> dict[str, dict[str, str]]:
    """Member name -> the FIELD_PROPERTIES it writes (TMDL key -> value as written, names
    unquoted), from one table file. Only property lines directly under a column or measure count."""
    out: dict[str, dict[str, str]] = {}
    member = None
    for line in text.replace("\r\n", "\n").split("\n"):
        m = _MEMBER.match(line)
        if m:
            member = _name(m)
            out.setdefault(member, {})
            continue
        if line.startswith("\t") and not line.startswith("\t\t") and line.strip():
            member = None  # another kind of member (hierarchy, partition, annotation)
            continue
        p = _PROPERTY.match(line)
        if member is not None and p and p["key"] in FIELD_PROPERTIES:
            value = p["value"]
            out[member][p["key"]] = _unquote(value) if p["key"] == "sortByColumn" else value
    return out


def _qualified(value: str) -> tuple[str, str] | None:
    m = _QUALIFIED.match(value.strip())
    if not m:
        return None
    table = m["tq"].replace("''", "'") if m["tq"] is not None else m["tb"]
    column = m["cq"].replace("''", "'") if m["cq"] is not None else m["cb"]
    return table, column


def parse_relationships(text: str, source: str = "relationships.tmdl") -> list[Relationship]:
    """The ``relationship`` blocks of ``relationships.tmdl``, in file order."""
    out: list[Relationship] = []
    current: dict[str, str] | None = None
    rel_id = ""

    def close() -> None:
        if current is None:
            return
        ends = _qualified(current.pop("fromColumn", "")), _qualified(current.pop("toColumn", ""))
        if None in ends:
            raise ModelError(f"{source}: relationship {rel_id} has no readable fromColumn/toColumn")
        (ft, fc), (tt, tc) = ends
        out.append(Relationship(rel_id, ft, fc, tt, tc, dict(current)))

    for line in text.replace("\r\n", "\n").split("\n"):
        r = _RELATIONSHIP.match(line.lstrip("\ufeff"))
        if r:
            close()
            current, rel_id = {}, r["id"]
            continue
        if line and not line.startswith("\t"):
            close()
            current = None
            continue
        p = _REL_PROPERTY.match(line)
        if current is not None and p:
            current[p["key"]] = p["value"]
    close()
    return out


def parse_hierarchies(text: str) -> dict[str, tuple[str, ...]]:
    """Hierarchy name -> its levels in order, from one ``tables/<name>.tmdl`` file (probe 16)."""
    out: dict[str, list[str]] = {}
    current: list[str] | None = None
    for line in text.replace("\r\n", "\n").split("\n"):
        h = _HIERARCHY.match(line)
        if h:
            current = out.setdefault(_name(h), [])
            continue
        if line.startswith("\t") and not line.startswith("\t\t") and line.strip():
            current = None  # another table member: the hierarchy ended
            continue
        lv = _LEVEL.match(line)
        if lv and current is not None:
            current.append(_name(lv))
    return {name: tuple(levels) for name, levels in out.items()}


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
        for name, levels in parse_hierarchies(text).items():
            model.hierarchies[(table, name)] = levels
        table_hidden, hidden = parse_hidden(text)
        if table_hidden:
            model.hidden_tables.add(table)
        model.hidden |= {(table, name) for name in hidden}
        for m in sorted(measures):
            model.measures.setdefault(m, []).append(table)
        for name, props in parse_properties(text).items():
            model.properties[(table, name)] = props
    rel_file = model_dir / "definition" / "relationships.tmdl"
    if rel_file.is_file():
        try:
            rel_text = rel_file.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError) as exc:
            raise ModelError(f"{rel_file.name}: can't read the model file ({exc})") from exc
        model.relationships = parse_relationships(rel_text)
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
