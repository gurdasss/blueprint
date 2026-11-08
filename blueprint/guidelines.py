"""Layered guideline resolution.

Layers, later overriding earlier (mappings merge key by key; anything else is replaced):

1. ``blueprint/defaults.yaml``                  ships with the tool
2. organisation guidelines                      ``--guidelines`` or ``$BLUEPRINT_GUIDELINES``
3. ``<report>/.blueprint.yaml``                 committed with the report
4. command-line overrides                       e.g. ``--grid 8``

Only keys a command actually uses are validated here, so new sections can be added to a
guidelines file before the code that reads them exists.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULTS = Path(__file__).resolve().parent / "defaults.yaml"
REPORT_OVERRIDE = ".blueprint.yaml"
ENV_VAR = "BLUEPRINT_GUIDELINES"


class GuidelinesError(Exception):
    pass


@dataclass(frozen=True)
class Grid:
    size: int
    snap: bool


@dataclass(frozen=True)
class Guidelines:
    name: str
    version: int
    grid: Grid
    sources: tuple[str, ...]  # which layers contributed, lowest first
    raw: dict[str, Any]


def merge(base: dict[str, Any], over: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = merge(out[k], v)
        else:
            out[k] = v
    return out


def _read(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise GuidelinesError(f"{path}: {exc}") from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise GuidelinesError(f"{path}: top level must be a mapping")
    return data


def load(
    guidelines: Path | None = None,
    report_dir: Path | None = None,
    overrides: dict[str, Any] | None = None,
) -> Guidelines:
    layers: list[tuple[str, dict[str, Any]]] = [("defaults", _read(DEFAULTS))]
    if guidelines is None and os.environ.get(ENV_VAR):
        guidelines = Path(os.environ[ENV_VAR])
    if guidelines is not None:
        layers.append((str(guidelines), _read(guidelines)))
    if report_dir is not None and (report_dir / REPORT_OVERRIDE).is_file():
        layers.append((str(report_dir / REPORT_OVERRIDE), _read(report_dir / REPORT_OVERRIDE)))
    if overrides:
        layers.append(("command line", overrides))

    raw: dict[str, Any] = {}
    for _, layer in layers:
        raw = merge(raw, layer)
    return Guidelines(
        name=str(raw.get("name", "")),
        version=_int(raw, "version", minimum=1),
        grid=Grid(size=_int(raw.get("grid", {}), "grid.size", minimum=1, key="size"),
                  snap=_bool(raw.get("grid", {}), "grid.snap", key="snap")),
        sources=tuple(name for name, _ in layers),
        raw=raw,
    )


def _int(section: Any, label: str, *, minimum: int, key: str | None = None) -> int:
    value = section.get(key or label) if isinstance(section, dict) else None
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise GuidelinesError(f"{label} must be an integer >= {minimum}, got {value!r}")
    return value


def _bool(section: Any, label: str, *, key: str) -> bool:
    value = section.get(key) if isinstance(section, dict) else None
    if not isinstance(value, bool):
        raise GuidelinesError(f"{label} must be true or false, got {value!r}")
    return value
