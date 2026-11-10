"""Slot contracts per visual type: what a spec `type:` means, loaded from ``blueprint/visuals/*.yaml``.

A contract maps a spec type to its PBIR ``visualType``, the layout region role it fills by
default, and its typed slots (spec slot name -> query role, accepted field kind, required,
ordered). Only types whose PBIR shape has been verified in Desktop ship here; the YAML files
cite the probe that verified them.

The core ships seven types: header, card, kpi, column, line, bar, table. Further verified
contracts live in ``visuals/archive/`` and load only when a guidelines file puts a directory
on the visuals search path (``extensions.custom_visuals.search_path``), which `contracts()`
takes as ``extra``. Loading is deterministic: the core directory first, then each extra in
the order given, each sorted by file name.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

import yaml

VISUALS_DIR = Path(__file__).resolve().parent / "visuals"
ARCHIVE_DIR = VISUALS_DIR / "archive"
CORE_TYPES = ("bar", "card", "column", "header", "kpi", "line", "table")
# "hierarchy": a hierarchy built in the model, written like a column (Table[Hierarchy]). It's one
# field, as in Desktop's wells, that binds all its levels in order (probes 16, 18). So a slot that
# takes a single field can take one, without also allowing a list of columns there.
KINDS = ("measure", "column", "hierarchy")


class ContractError(Exception):
    pass


@dataclass(frozen=True)
class Slot:
    name: str
    role: str  # PBIR query role, e.g. "Category"
    accepts: tuple[str, ...]  # subset of KINDS
    required: bool = False
    ordered: bool = False  # an ordered list is allowed (e.g. a drill-down path)
    list_excludes: tuple[str, ...] = ()  # slots that must be empty when this one holds a list


@dataclass(frozen=True)
class Option:
    """A formatting choice a spec may make: each value is the literal written at
    ``visual.objects.<object>[0].properties.<property>`` (as Desktop wrote it in the cited probe).
    Leaving the option out leaves Desktop's default."""
    name: str
    object: str
    property: str
    values: dict[str, str]  # spec value -> PBIR literal, e.g. dropdown -> "'Dropdown'"


@dataclass(frozen=True)
class Contract:
    type: str
    visual_type: str
    region: str
    slots: dict[str, Slot]
    options: dict[str, Option] = field(default_factory=dict)


def _load(path: Path) -> Contract:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    where = path.name
    try:
        slots = {}
        for name, spec in (data.get("slots") or {}).items():
            accepts = spec["accepts"]
            accepts = (accepts,) if isinstance(accepts, str) else tuple(accepts)
            if not accepts or any(a not in KINDS for a in accepts):
                raise ContractError(f"{where}: slot {name}: accepts must be from {KINDS}")
            slots[name] = Slot(name, spec["role"], accepts, bool(spec.get("required", False)),
                               bool(spec.get("ordered", False)), tuple(spec.get("list_excludes", ())))
        options = {}
        for name, spec in (data.get("options") or {}).items():
            if not all(isinstance(k, str) for k in spec["values"]):
                # YAML 1.1 reads an unquoted on/off/yes/no as a boolean: quote it ("on")
                raise ContractError(f"{where}: option {name}: values keys must be strings (quote \"on\")")
            options[name] = Option(name, spec["object"], spec["property"],
                                   {k: str(v) for k, v in spec["values"].items()})
        contract = Contract(data["type"], data["visual_type"], data["region"], slots, options)
        for slot in slots.values():
            unknown = [s for s in slot.list_excludes if s not in slots]
            if unknown or (slot.list_excludes and not slot.ordered):
                raise ContractError(f"{where}: slot {slot.name}: list_excludes needs ordered: true "
                                    "and names of this contract's slots")
    except (KeyError, TypeError, AttributeError) as exc:
        raise ContractError(f"{where}: malformed contract ({exc})") from exc
    if contract.type != path.stem:
        raise ContractError(f"{where}: type {contract.type!r} must match the file name")
    return contract


@cache
def contracts(extra: tuple[Path, ...] = ()) -> dict[str, Contract]:
    """The loaded contracts by spec type: the core seven, plus any directory in ``extra``.

    ``extra`` is part of the cache key, so each distinct search path is loaded once. A type
    defined twice is refused, naming both files: silently shadowing one would change what a
    spec means depending on the search path order.
    """
    out: dict[str, Contract] = {}
    source: dict[str, Path] = {}
    for directory in (VISUALS_DIR, *extra):
        for path in sorted(Path(directory).glob("*.yaml")):
            if path.stem in out:
                raise ContractError(f"visual type {path.stem!r} is defined twice: "
                                    f"{source[path.stem]} and {path}")
            out[path.stem] = _load(path)
            source[path.stem] = path
    return out
