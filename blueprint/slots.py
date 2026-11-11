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
CORE_TYPES = ("bar", "card", "column", "header", "kpi", "line", "matrix", "slicer", "table")
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
    # Desktop marks this slot's column projections `"active": true` (every chart's Category,
    # probes 04/08/12; the slicer's Values and the matrix's Rows/Columns, probe 20). It is a fact
    # about one well of one visual type, so it belongs in the type's contract: the core must not
    # carry the shape of a type it doesn't ship, and a custom visual can declare it without a
    # code change.
    active: bool = False


@dataclass(frozen=True)
class Option:
    """A formatting choice a spec may make: each value is the literal written at
    ``visual.objects.<object>[0].properties.<property>`` (as Desktop wrote it in the cited probe).
    Leaving the option out leaves Desktop's default."""
    name: str
    object: str
    property: str
    values: dict[str, str]  # spec value -> PBIR literal, e.g. dropdown -> "'Dropdown'"
    # A value may write a different property of the same object than ``property`` (the legend's
    # `off` writes `show`, its positions write `position`): spec value -> property.
    properties: dict[str, str] = field(default_factory=dict)

    def prop(self, value: str) -> str:
        """The property ``value`` writes."""
        return self.properties.get(value, self.property)

    def siblings(self, value: str) -> frozenset[str]:
        """The other properties this option's values write. Choosing ``value`` removes them, so a
        legend moved from `off` to `top` isn't left hidden by the `show: false` `off` wrote."""
        return frozenset(self.prop(v) for v in self.values) - {self.prop(value)}


@dataclass(frozen=True)
class Contract:
    type: str
    visual_type: str
    region: str
    slots: dict[str, Slot]
    options: dict[str, Option] = field(default_factory=dict)

    @property
    def active_roles(self) -> frozenset[str]:
        """The query roles whose column projections carry ``"active": true`` (see ``Slot.active``)."""
        return frozenset(s.role for s in self.slots.values() if s.active)


def _read(path: Path) -> dict:
    """The raw YAML of one contract file, before ``inherits:`` is resolved."""
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ContractError(f"{path.name}: top level must be a mapping")
    return data


def _resolve(name: str, raw: dict[str, tuple[Path, dict]], chain: tuple[str, ...] = ()) -> dict:
    """``name``'s raw contract with its ``inherits:`` chain merged in (template/visuals.md).

    The parent's ``slots``, ``options`` and ``region`` are copied; the child overrides them key
    by key, so it can change one slot without restating the others. ``type`` and ``visual_type``
    are never inherited: a contract that didn't name its own PBIR type would silently claim its
    parent's, and only a probe can say what Desktop writes for a type.
    """
    path, data = raw[name]
    parent = data.get("inherits")
    if parent is None:
        return data
    if not isinstance(parent, str):
        raise ContractError(f"{path.name}: inherits must be a visual type name")
    if name in chain or parent == name:
        cycle = " -> ".join((*chain, name, parent))
        raise ContractError(f"{path.name}: inherits is a cycle ({cycle})")
    if parent not in raw:
        raise ContractError(f"{path.name}: inherits unknown type {parent!r} "
                            f"(loaded: {', '.join(sorted(raw))})")
    for required in ("type", "visual_type"):
        if required not in data:
            raise ContractError(f"{path.name}: {required} is never inherited; "
                                f"declare it alongside inherits: {parent}")
    if path.parent == VISUALS_DIR and raw[parent][0].parent != VISUALS_DIR:
        raise ContractError(f"{path.name}: a core contract can't inherit {parent!r} from "
                            f"{raw[parent][0].parent} (the core must load on its own)")
    base = _resolve(parent, raw, (*chain, name))
    merged = {**base, **data}
    merged.pop("inherits", None)
    for section in ("slots", "options"):
        if section not in data:  # not mentioned: the parent's, as they are
            continue
        child = data[section] or {}
        if not child:  # mentioned and empty: the child says it has none
            merged[section] = {}
            continue
        merged[section] = {**(base.get(section) or {}), **child}
    return merged


def _contract(data: dict, where: str, stem: str) -> Contract:
    try:
        slots = {}
        for name, spec in (data.get("slots") or {}).items():
            accepts = spec["accepts"]
            accepts = (accepts,) if isinstance(accepts, str) else tuple(accepts)
            if not accepts or any(a not in KINDS for a in accepts):
                raise ContractError(f"{where}: slot {name}: accepts must be from {KINDS}")
            slots[name] = Slot(name, spec["role"], accepts, bool(spec.get("required", False)),
                               bool(spec.get("ordered", False)), tuple(spec.get("list_excludes", ())),
                               bool(spec.get("active", False)))
        options = {}
        for name, spec in (data.get("options") or {}).items():
            if not all(isinstance(k, str) for k in spec["values"]):
                # YAML 1.1 reads an unquoted on/off/yes/no as a boolean: quote it ("on")
                raise ContractError(f"{where}: option {name}: values keys must be strings (quote \"on\")")
            literals, props = {}, {}
            for key, raw in spec["values"].items():
                if isinstance(raw, dict):  # {property: show, literal: "false"}: another property
                    literals[key], props[key] = str(raw["literal"]), str(raw["property"])
                else:
                    literals[key] = str(raw)
            options[name] = Option(name, spec["object"], spec["property"], literals, props)
        contract = Contract(data["type"], data["visual_type"], data["region"], slots, options)
        for slot in slots.values():
            unknown = [s for s in slot.list_excludes if s not in slots]
            if unknown or (slot.list_excludes and not slot.ordered):
                raise ContractError(f"{where}: slot {slot.name}: list_excludes needs ordered: true "
                                    "and names of this contract's slots")
    except (KeyError, TypeError, AttributeError) as exc:
        raise ContractError(f"{where}: malformed contract ({exc})") from exc
    if contract.type != stem:
        raise ContractError(f"{where}: type {contract.type!r} must match the file name")
    return contract


def _load(path: Path) -> Contract:
    """One contract file on its own (no ``inherits:`` to resolve)."""
    return _contract(_read(path), path.name, path.stem)


@cache
def contracts(extra: tuple[Path, ...] = ()) -> dict[str, Contract]:
    """The loaded contracts by spec type: the core (``CORE_TYPES``), plus any directory in ``extra``.

    ``extra`` is part of the cache key, so each distinct search path is loaded once. A type
    defined twice is refused, naming both files: silently shadowing one would change what a
    spec means depending on the search path order.
    """
    raw: dict[str, tuple[Path, dict]] = {}
    for directory in (VISUALS_DIR, *extra):
        for path in sorted(Path(directory).glob("*.yaml")):
            if path.stem in raw:
                raise ContractError(f"visual type {path.stem!r} is defined twice: "
                                    f"{raw[path.stem][0]} and {path}")
            raw[path.stem] = (path, _read(path))
    # every file is read before any inherits: is resolved, so a child may sit in any loaded
    # directory and name a parent from another one (a core parent, for a contract outside the core)
    out = {name: _contract(_resolve(name, raw), path.name, path.stem)
           for name, (path, _) in raw.items()}
    seen: dict[str, str] = {}
    for name, contract in out.items():
        if contract.visual_type in seen:
            raise ContractError(f"visual type {contract.visual_type!r} is claimed by both "
                                f"{seen[contract.visual_type]!r} and {name!r}: a spec's type must "
                                "say which PBIR visual it builds")
        seen[contract.visual_type] = name
    return out
