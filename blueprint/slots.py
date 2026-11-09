"""Slot contracts per visual type: what a spec `type:` means, loaded from ``blueprint/visuals/*.yaml``.

A contract maps a spec type to its PBIR ``visualType``, the layout region role it fills by
default, and its typed slots (spec slot name -> query role, accepted field kind, required,
ordered). Only types whose PBIR shape has been verified in Desktop ship here; the YAML files
cite the probe that verified them.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from pathlib import Path

import yaml

VISUALS_DIR = Path(__file__).resolve().parent / "visuals"
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


@dataclass(frozen=True)
class Contract:
    type: str
    visual_type: str
    region: str
    slots: dict[str, Slot]


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
                               bool(spec.get("ordered", False)))
        contract = Contract(data["type"], data["visual_type"], data["region"], slots)
    except (KeyError, TypeError, AttributeError) as exc:
        raise ContractError(f"{where}: malformed contract ({exc})") from exc
    if contract.type != path.stem:
        raise ContractError(f"{where}: type {contract.type!r} must match the file name")
    return contract


@cache
def contracts() -> dict[str, Contract]:
    return {p.stem: _load(p) for p in sorted(VISUALS_DIR.glob("*.yaml"))}
