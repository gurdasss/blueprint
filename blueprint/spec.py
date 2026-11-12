"""Page spec parsing and validation. Pure: no files other than the spec, no PBIR knowledge.

A page spec describes *intent* (README "Page specs"):

    id: sales-overview             # optional; defaults to the file name. Links this spec to its
                                   # page, so renaming `page:` renames the page (no duplicate)
    page: Sales Overview
    layout: standard-4-up          # optional; defaults to the guidelines' layouts.default
    visuals:
      - type: header
        title: Sales Overview
      - type: column
        id: by-country             # optional stable identity (default: <type>-<n>)
        title: Sales by Country
        slots:
          category: ["Sales[Country]", "Sales[Region]"]   # ordered list = drill-down
          value: "[Total Amount]"
      - type: card
        region: kpi-row            # optional; overrides the region role the type's contract sets
      - type: table
        blueprint: ignore          # hand-placed on purpose; never touched or placed

Field references are syntactic here: ``Table[Column]`` or ``'Table name'[Column]`` is a
column and ``[Name]`` is a measure (its table is resolved against the semantic model later).
``Table[Name]`` may also name a hierarchy built in the model; ``bp apply`` finds that out from the
model and binds its levels, where the slot accepts one.
All problems are collected and reported together, each with its location.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import yaml

from blueprint.slots import Contract, contracts

ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
_COLUMN = re.compile(r"^(?:'(?P<qt>(?:[^']|'')+)'|(?P<t>[A-Za-z_][\w ]*?))\[(?P<c>[^\]]+)\]$")
_MEASURE = re.compile(r"^\[(?P<m>[^\]]+)\]$")
_SPEC_KEYS = {"id", "page", "layout", "visuals"}
_VISUAL_KEYS = {"type", "id", "title", "region", "slots", "options", "sort", "blueprint"}
_ROLE_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class SpecError(Exception):
    def __init__(self, source: str, problems: list[str]) -> None:
        self.source, self.problems = source, problems
        super().__init__(f"{source}: {len(problems)} problem(s)\n  " + "\n  ".join(problems))


# A visual-level aggregation of a column: spec name -> the label render.AGGREGATIONS uses, which
# is also what the reader calls the code Desktop writes (probe 29). `count` is Desktop's "Count"
# (non-null, code 5) and `distinctcount` its "Count (Distinct)" (code 2).
AGGREGATIONS = {"sum": "Sum", "average": "Average", "count": "Count",
                "distinctcount": "DistinctCount", "min": "Min", "max": "Max"}


@dataclass(frozen=True)
class FieldRef:
    kind: str  # "measure" | "column"
    name: str
    table: str | None = None  # None for a measure until resolved against the model
    aggregate: str | None = None  # a key of AGGREGATIONS; columns only (long form)
    format: str | None = None  # a Power BI format string scoped to the visual (long form)

    def __str__(self) -> str:
        ref = f"[{self.name}]" if self.table is None else f"{self.table}[{self.name}]"
        return f"{self.aggregate} of {ref}" if self.aggregate else ref


DIRECTIONS = {"ascending": "Ascending", "descending": "Descending"}


@dataclass(frozen=True)
class SortSpec:
    """`sort: {by: <field>, direction: ascending|descending}` — the visual's own sort.

    Desktop writes one `query.sortDefinition` per visual, so this is a visual key, not a slot
    key. The field must be one the visual binds (probe 31).
    """
    by: FieldRef
    direction: str  # a key of DIRECTIONS


@dataclass(frozen=True)
class VisualSpec:
    index: int  # position in the spec's visuals list
    type: str
    id: str  # stable identity within the page
    title: str | None = None
    slots: dict[str, tuple[FieldRef, ...]] = field(default_factory=dict)
    ignore: bool = False
    region: str | None = None  # region role chosen in the spec; None: the contract's role
    options: dict[str, str] = field(default_factory=dict)  # option name -> value (contract options)
    sort: SortSpec | None = None  # the visual's sort; None: Desktop's own (probe 31)


@dataclass(frozen=True)
class PageSpec:
    page: str
    layout: str | None
    visuals: tuple[VisualSpec, ...]
    source: str = "<spec>"
    id: str = "spec"  # stable identity: links the spec to the page it builds, across renames


def default_id(path: Path) -> str:
    """A spec's default id: its file name, e.g. sales-overview.yaml -> "sales-overview"."""
    slug = re.sub(r"[^a-z0-9]+", "-", path.stem.lower()).strip("-")[:40].strip("-")
    return slug or "spec"


def parse_field(text: Any) -> FieldRef | None:
    if not isinstance(text, str):
        return None
    text = text.strip()
    if m := _MEASURE.match(text):
        return FieldRef("measure", m["m"].strip())
    if m := _COLUMN.match(text):
        table = m["qt"].replace("''", "'") if m["qt"] is not None else m["t"].strip()
        return FieldRef("column", m["c"].strip(), table)
    return None


_SLOT_KEYS = ("field", "aggregate", "format")


def parse_slot(item: Any, at: str, problems: list[str]) -> FieldRef | None:
    """One slot entry: a field reference, or a mapping of a field plus per-slot decisions.

    ``"Sales[Amount]"`` and ``{field: "Sales[Amount]"}`` mean the same thing. The mapping is the
    only way to say more, so there is one way to write each thing (docs/plan.md step 5).
    """
    if not isinstance(item, dict):
        ref = parse_field(item)
        if ref is None:
            problems.append(f"{at}: {item!r} is not a field reference "
                            "(use Table[Column], [Measure], or {field: …, aggregate: …, format: …})")
        return ref
    unknown = set(item) - set(_SLOT_KEYS)
    if unknown:
        problems.append(f"{at}: unknown keys {', '.join(sorted(map(str, unknown)))} "
                        f"(a slot mapping takes {', '.join(_SLOT_KEYS)})")
        return None
    ref = parse_field(item.get("field"))
    if ref is None:
        problems.append(f"{at}.field: {item.get('field')!r} is not a field reference "
                        "(use Table[Column] or [Measure])")
        return None
    aggregate = item.get("aggregate")
    if aggregate is not None:
        if not isinstance(aggregate, str) or aggregate not in AGGREGATIONS:
            problems.append(f"{at}.aggregate: {aggregate!r} isn't one of "
                            f"{', '.join(sorted(AGGREGATIONS))}")
            return None
        if ref.kind != "column":
            problems.append(f"{at}.aggregate: {ref} is a measure; an aggregation is Blueprint "
                            "summarising a column, so write the column, or drop aggregate")
            return None
    fmt = item.get("format")
    if fmt is not None and (not isinstance(fmt, str) or not fmt.strip()):
        problems.append(f"{at}.format: must be a Power BI format string, e.g. \"#,0.00\"")
        return None
    return replace(ref, aggregate=aggregate, format=fmt.strip() if isinstance(fmt, str) else None)


def load(path: Path, visual_dirs: tuple[Path, ...] = ()) -> PageSpec:
    try:
        data = yaml.safe_load(path.read_bytes())  # bytes: PyYAML detects UTF-8, BOM and UTF-16
    except (OSError, yaml.YAMLError) as exc:
        raise SpecError(str(path), [str(exc)]) from exc
    return parse(data, str(path), default_id=default_id(path), visual_dirs=visual_dirs)


def parse(data: Any, source: str = "<spec>", default_id: str = "spec",
          visual_dirs: tuple[Path, ...] = ()) -> PageSpec:
    problems: list[str] = []
    if not isinstance(data, dict):
        raise SpecError(source, ["top level must be a mapping with page, layout and visuals"])
    for key in sorted(set(data) - _SPEC_KEYS, key=str):  # YAML keys may be numbers or null
        problems.append(f"{key}: unknown key (expected: {', '.join(sorted(_SPEC_KEYS))})")

    page = data.get("page")
    if not isinstance(page, str) or not page.strip():
        problems.append("page: required, a non-empty page name")
    layout = data.get("layout")
    if layout is not None and (not isinstance(layout, str) or not layout.strip()):
        problems.append("layout: must be a layout name")
    spec_id = data.get("id", default_id)
    if not isinstance(spec_id, str) or not ID_RE.match(spec_id):
        problems.append(f"id: {spec_id!r} must be lowercase letters, digits and hyphens (max 40)")

    raw_visuals = data.get("visuals")
    visuals: list[VisualSpec] = []
    if not isinstance(raw_visuals, list) or not raw_visuals:
        problems.append("visuals: required, a non-empty list")
        raw_visuals = []
    known = contracts(visual_dirs)
    counts: dict[str, int] = {}
    seen_ids: dict[str, int] = {}
    for i, raw in enumerate(raw_visuals):
        v = _visual(i, raw, known, counts, problems)
        if v is None:
            continue
        if v.id in seen_ids:
            problems.append(f"visuals[{i}].id: {v.id!r} already used by visuals[{seen_ids[v.id]}]")
        seen_ids.setdefault(v.id, i)
        visuals.append(v)

    if problems:
        raise SpecError(source, problems)
    return PageSpec(page.strip(), layout.strip() if layout else None, tuple(visuals), source, spec_id)


def _visual(i: int, raw: Any, known: dict[str, Contract], counts: dict[str, int],
            problems: list[str]) -> VisualSpec | None:
    at = f"visuals[{i}]"
    if not isinstance(raw, dict):
        problems.append(f"{at}: must be a mapping with at least `type`")
        return None
    for key in sorted(set(raw) - _VISUAL_KEYS, key=str):  # YAML keys may be numbers or null
        problems.append(f"{at}.{key}: unknown key (expected: {', '.join(sorted(_VISUAL_KEYS))})")
    vtype = raw.get("type")
    if not isinstance(vtype, str) or vtype not in known:
        problems.append(f"{at}.type: {vtype!r} is not a supported visual type "
                        f"(supported: {', '.join(sorted(known))})")
        return None
    counts[vtype] = counts.get(vtype, 0) + 1

    vid = raw.get("id", f"{vtype}-{counts[vtype]}")
    if not isinstance(vid, str) or not ID_RE.match(vid):
        problems.append(f"{at}.id: {vid!r} must be lowercase letters, digits and hyphens (max 40)")
        vid = f"{vtype}-{counts[vtype]}"
    title = raw.get("title")
    if title is not None and not isinstance(title, str):
        problems.append(f"{at}.title: must be text")
        title = None
    marker = raw.get("blueprint")
    if marker is not None and marker != "ignore":
        problems.append(f"{at}.blueprint: the only accepted value is `ignore`")
    ignore = marker == "ignore"
    region = raw.get("region")
    if region is not None and (not isinstance(region, str) or not _ROLE_RE.match(region)):
        problems.append(f"{at}.region: {region!r} must be a region role, e.g. main or kpi-row")
        region = None
    if vtype == "header" and not ignore and not title:
        problems.append(f"{at}.title: a header needs a title (it is the header's text)")

    slots = {} if ignore else _slots(at, raw.get("slots"), known[vtype], problems)
    options = {} if ignore else _options(at, raw.get("options"), known[vtype], problems)
    sort = None if ignore else _sort(at, raw.get("sort"), slots, problems)
    return VisualSpec(i, vtype, vid, title, slots, ignore, region, options, sort)


def _sort(at: str, raw: Any, slots: dict[str, tuple[FieldRef, ...]],
          problems: list[str]) -> SortSpec | None:
    """`sort: {by: <field>, direction: …}`. Desktop sorts on a field the visual binds, so `by`
    must be one of them — otherwise the sort would be silently ignored (probe 31)."""
    if raw is None:
        return None
    if not isinstance(raw, dict):
        problems.append(f"{at}.sort: must be a mapping with by and direction")
        return None
    unknown = set(raw) - {"by", "direction"}
    if unknown:
        problems.append(f"{at}.sort: unknown keys {', '.join(sorted(map(str, unknown)))} "
                        "(a sort takes by, direction)")
        return None
    by = parse_field(raw.get("by"))
    if by is None:
        problems.append(f"{at}.sort.by: {raw.get('by')!r} is not a field reference "
                        "(use Table[Column] or [Measure])")
        return None
    direction = raw.get("direction")
    if not isinstance(direction, str) or direction not in DIRECTIONS:
        problems.append(f"{at}.sort.direction: {direction!r} isn't one of "
                        f"{', '.join(sorted(DIRECTIONS))}")
        return None
    bound = [ref for refs in slots.values() for ref in refs]
    if not any(ref.kind == by.kind and ref.name == by.name
               and (by.table is None or ref.table == by.table) for ref in bound):
        names = ", ".join(str(ref) for ref in bound) or "nothing"
        problems.append(f"{at}.sort.by: {by} isn't bound by this visual (it binds {names}); "
                        "Desktop sorts on a field the visual shows")
        return None
    return SortSpec(by, direction)


def _options(at: str, raw: Any, contract: Contract, problems: list[str]) -> dict[str, str]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        problems.append(f"{at}.options: must be a mapping of option name -> value")
        return {}
    out = {}
    for name, value in raw.items():
        if isinstance(value, bool):  # YAML 1.1 reads an unquoted on/off as true/false
            value = "on" if value else "off"
        option = contract.options.get(name)
        if option is None:
            allowed = ", ".join(contract.options) or "none"
            problems.append(f"{at}.options.{name}: {contract.type} has no option {name!r} (options: {allowed})")
        elif value not in option.values:
            problems.append(f"{at}.options.{name}: {value!r} isn't one of {', '.join(option.values)}")
        else:
            out[name] = value
    return out


def _slots(at: str, raw: Any, contract: Contract, problems: list[str]) -> dict[str, tuple[FieldRef, ...]]:
    raw = raw if raw is not None else {}
    if not isinstance(raw, dict):
        problems.append(f"{at}.slots: must be a mapping of slot name -> field reference(s)")
        return {}
    out: dict[str, tuple[FieldRef, ...]] = {}
    for name, value in raw.items():
        slot = contract.slots.get(name)
        where = f"{at}.slots.{name}"
        if slot is None:
            allowed = ", ".join(contract.slots) or "none"
            problems.append(f"{where}: {contract.type} has no slot {name!r} (slots: {allowed})")
            continue
        values = value if isinstance(value, list) else [value]
        if isinstance(value, list) and not slot.ordered:
            problems.append(f"{where}: takes a single field, not a list")
            continue
        if not values:
            problems.append(f"{where}: empty list")
            continue
        refs = []
        for j, item in enumerate(values):
            item_at = f"{where}[{j}]" if isinstance(value, list) else where
            ref = parse_slot(item, item_at, problems)
            if ref is None:
                continue
            # An aggregated column is a summarised value, so it belongs where a measure does
            # (probe 29 put one in a table's Values well beside measures), not where a plain
            # column does: a drill-down category of "Sum of Amount" isn't a thing.
            if ref.aggregate and "measure" not in slot.accepts:
                problems.append(f"{item_at}: {name} takes {' or '.join(slot.accepts)}, so it can't "
                                f"take an aggregation ({ref})")
            elif ref.aggregate:
                refs.append(ref)
            elif ref.kind not in slot.accepts:
                hint = ""
                if ref.kind == "column" and slot.accepts == ("measure",):
                    hint = f"; if {ref.name!r} is a measure, write it as [{ref.name}]"
                problems.append(f"{item_at}: {ref} is a {ref.kind}, but {name} accepts "
                                f"{' or '.join(slot.accepts)}{hint}")
            else:
                refs.append(ref)
        if len(refs) == len(values):
            out[name] = tuple(refs)
    for name, slot in contract.slots.items():
        if slot.required and name not in raw:
            problems.append(f"{at}.slots.{name}: required by {contract.type}")
        if len(out.get(name, ())) > 1:
            for other in slot.list_excludes:
                if other in raw:
                    problems.append(f"{at}.slots.{name}: takes one field when {other} is set "
                                    f"(Desktop doesn't draw a {name} list together with a {other} on "
                                    f"{contract.type})")
    return out
