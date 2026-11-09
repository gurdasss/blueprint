"""Layered guideline resolution.

Layers, later overriding earlier (mappings merge key by key; anything else is replaced):

1. ``blueprint/defaults.yaml``                  ships with the tool
2. organisation guidelines                      ``--guidelines`` or ``$BLUEPRINT_GUIDELINES``
3. ``<report>/.blueprint.yaml``                 committed with the report
4. command-line overrides                       e.g. ``--grid 8``

Only keys some command uses are validated, so a guidelines file can contain sections whose
code doesn't exist yet. Those are listed in :data:`NOT_IMPLEMENTED`, so ``bp check`` can say
what it didn't check instead of passing them silently.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from blueprint.policies import DENSITY

DEFAULTS = Path(__file__).resolve().parent / "defaults.yaml"
REPORT_OVERRIDE = ".blueprint.yaml"
ENV_VAR = "BLUEPRINT_GUIDELINES"

SEVERITIES = ("error", "warning", "off")
RULES = ("format", "bounds", "grid", "margin", "overlap", "page-size", "density")
# Documented in README but unchecked until the PBIR format for them is verified.
NOT_IMPLEMENTED = ("typography", "page.require_title", "page.title_region",
                   "canvas.gutter", "layouts")


class GuidelinesError(Exception):
    pass


@dataclass(frozen=True)
class Grid:
    size: int
    snap: bool
    max_resize: float | None  # fraction; None = no limit


@dataclass(frozen=True)
class Canvas:
    width: int | None  # None: page size isn't checked
    height: int | None
    margin: int


@dataclass(frozen=True)
class PageRules:
    max_visuals: int | None
    density_policy: str  # a name from blueprint.policies.DENSITY


@dataclass(frozen=True)
class Palette:
    categorical: tuple[str, ...]  # uppercase hex; empty = palette rule inactive
    background: str | None
    text: str | None
    extra: tuple[str, ...]  # further allowed colours, e.g. sanctioned shades
    enforce: str  # strict (error) | warn (warning) | off

    @property
    def allowed(self) -> frozenset[str]:
        return frozenset([*self.categorical, *self.extra,
                          *(c for c in (self.background, self.text) if c)])

    @property
    def severity(self) -> str:
        return {"strict": "error", "warn": "warning", "off": "off"}[self.enforce]


@dataclass(frozen=True)
class CheckRules:
    severity: dict[str, str]  # rule id -> error | warning | off
    decorative_types: tuple[str, ...]  # may contain other visuals; exempt from margin


@dataclass(frozen=True)
class Guidelines:
    name: str
    version: int
    grid: Grid
    canvas: Canvas
    page: PageRules
    palette: Palette
    check: CheckRules
    sources: tuple[str, ...]  # which layers contributed, lowest first
    raw: dict[str, Any]

    def has(self, dotted: str) -> bool:
        return _get(self.raw, dotted, _MISSING) is not _MISSING

    @property
    def unchecked(self) -> list[str]:
        return [k for k in NOT_IMPLEMENTED if self.has(k)]


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
    return _build(raw, tuple(name for name, _ in layers))


def _build(raw: dict[str, Any], sources: tuple[str, ...]) -> Guidelines:
    severity = _get(raw, "check.severity", {})
    if not isinstance(severity, dict):
        raise GuidelinesError("check.severity must be a mapping of rule -> error|warning|off")
    # PyYAML reads unquoted `off` as False (YAML 1.1); accept it as the level it was meant as.
    severity = {rule: "off" if level is False else level for rule, level in severity.items()}
    for rule, level in severity.items():
        if rule not in RULES:
            raise GuidelinesError(f"check.severity: unknown rule {rule!r} (known: {', '.join(RULES)})")
        if level not in SEVERITIES:
            raise GuidelinesError(f"check.severity.{rule} must be one of {', '.join(SEVERITIES)}")
    missing = [r for r in RULES if r not in severity]
    if missing:
        raise GuidelinesError(f"check.severity: no level for {', '.join(missing)}")

    decorative = _get(raw, "check.decorative_types", [])
    if not isinstance(decorative, list) or not all(isinstance(t, str) for t in decorative):
        raise GuidelinesError("check.decorative_types must be a list of visual type names")

    policy = _get(raw, "page.density_policy")
    if policy not in DENSITY:
        raise GuidelinesError(
            f"page.density_policy must be one of {', '.join(sorted(DENSITY))}, got {policy!r}")

    return Guidelines(
        name=str(raw.get("name", "")),
        version=_int(raw, "version", minimum=1),
        grid=Grid(size=_int(raw, "grid.size", minimum=1),
                  snap=_bool(raw, "grid.snap"),
                  max_resize=_number(raw, "grid.max_resize", nullable=True)),
        canvas=Canvas(width=_int(raw, "canvas.width", minimum=1, nullable=True),
                      height=_int(raw, "canvas.height", minimum=1, nullable=True),
                      margin=_int(raw, "canvas.margin", minimum=0)),
        page=PageRules(max_visuals=_int(raw, "page.max_visuals", minimum=1, nullable=True),
                       density_policy=policy),
        palette=_palette(raw),
        check=CheckRules(severity=dict(severity), decorative_types=tuple(decorative)),
        sources=sources,
        raw=raw,
    )


_MISSING = object()


def _get(raw: dict[str, Any], dotted: str, default: Any = None) -> Any:
    node: Any = raw
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def _int(raw: dict[str, Any], key: str, *, minimum: int, nullable: bool = False) -> int | None:
    value = _get(raw, key)
    if value is None and nullable:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        null = " or null" if nullable else ""
        raise GuidelinesError(f"{key} must be an integer >= {minimum}{null}, got {value!r}")
    return value


def _bool(raw: dict[str, Any], key: str) -> bool:
    value = _get(raw, key)
    if not isinstance(value, bool):
        raise GuidelinesError(f"{key} must be true or false, got {value!r}")
    return value


def _number(raw: dict[str, Any], key: str, *, nullable: bool = False) -> float | None:
    value = _get(raw, key)
    if value is None and nullable:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise GuidelinesError(f"{key} must be a number >= 0 (e.g. 0.25) or null, got {value!r}")
    return float(value)


_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _hex(value: Any, key: str, *, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str) or not _HEX.match(value):
        raise GuidelinesError(f"{key} must be a #RRGGBB colour, got {value!r}")
    return value.upper()


def _hex_list(raw: dict[str, Any], key: str) -> tuple[str, ...]:
    value = _get(raw, key, [])
    if value is None:
        return ()
    if not isinstance(value, list):
        raise GuidelinesError(f"{key} must be a list of #RRGGBB colours")
    return tuple(_hex(v, f"{key}[{i}]") or "" for i, v in enumerate(value))


def _palette(raw: dict[str, Any]) -> Palette:
    enforce = _get(raw, "palette.enforce")
    enforce = "off" if enforce is False else enforce  # unquoted YAML `off` parses as false
    if enforce not in ("strict", "warn", "off"):
        raise GuidelinesError(f"palette.enforce must be strict, warn or off, got {enforce!r}")
    return Palette(
        categorical=_hex_list(raw, "palette.categorical"),
        background=_hex(_get(raw, "palette.background"), "palette.background", nullable=True),
        text=_hex(_get(raw, "palette.text"), "palette.text", nullable=True),
        extra=_hex_list(raw, "palette.extra"),
        enforce=enforce,
    )
