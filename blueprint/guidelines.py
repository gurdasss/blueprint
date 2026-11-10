"""Layered guideline resolution.

Layers, later overriding earlier (mappings merge key by key; anything else is replaced):

1. ``blueprint/defaults.yaml``                  ships with the tool
2. organisation guidelines                      ``--guidelines`` or ``$BLUEPRINT_GUIDELINES``
3. ``<report>/.blueprint.yaml``                 committed with the report
4. command-line overrides                       e.g. ``--grid 8``

Core keys (v1): version, name, canvas, spacing, page, palette, typography, layouts.
The ``extensions:`` key is reserved for future opt-in features; the core validator
ignores it. Keys some command uses are validated; unrecognised keys in ``extensions:``
are silently passed through.
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
RULES = ("format", "bounds", "grid", "margin", "gutter", "overlap", "page-size", "density", "typography",
         "title")
NOT_IMPLEMENTED: tuple[str, ...] = ()

# Severity defaults baked into code — no longer in the client's YAML.
DEFAULT_SEVERITY: dict[str, str] = {
    "format": "error",
    "bounds": "error",
    "grid": "error",
    "margin": "warning",
    "gutter": "warning",
    "overlap": "warning",
    "page-size": "warning",
    "density": "warning",
    "typography": "error",
    "title": "error",
}

# Visual types allowed to contain other visuals (backgrounds, panels); exempt from margin/gutter.
DEFAULT_DECORATIVE_TYPES = ("image", "shape", "basicShape")


class GuidelinesError(Exception):
    pass


@dataclass(frozen=True)
class Spacing:
    grid: int
    margin: int
    gutter: int  # minimum gap between neighbouring visuals; 0: not checked


@dataclass(frozen=True)
class Canvas:
    width: int | None  # None: page size isn't checked
    height: int | None


@dataclass(frozen=True)
class PageRules:
    max_visuals: int | None
    density_policy: str  # a name from blueprint.policies.DENSITY
    require_title: bool  # pages built from a spec must have a header
    title_region: str | None  # the region role that header must be in; None: any


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


TYPOGRAPHY_ROLES = ("page_title", "visual_title", "body")
# Old role names accepted for backward compat; mapped to new names internally.
_ROLE_COMPAT = {"header": "page_title", "title": "visual_title", "subtitle": "body",
                "callout": "body", "card_label": "body", "textbox": "body"}


@dataclass(frozen=True)
class FontRule:
    fonts: tuple[str, ...]  # allowed faces, exact names from Desktop's font list; () = any
    sizes: tuple[float, ...]  # allowed sizes in pt; () = any


@dataclass(frozen=True)
class Layouts:
    search_path: tuple[Path, ...]  # absolute; relative entries resolve against their own file
    default: str | None


@dataclass(frozen=True)
class CheckRules:
    severity: dict[str, str]  # rule id -> error | warning | off
    decorative_types: tuple[str, ...]  # may contain other visuals; exempt from margin and gutter


# --- Backward-compatible shims (consumed by validate.py and commands until step 3) -----------

@dataclass(frozen=True)
class _GridCompat:
    """Shim so ``rules.grid.size`` still works while consumers use the old paths."""
    size: int
    snap: bool = True
    max_resize: float | None = 0.25


@dataclass(frozen=True)
class _CanvasCompat:
    """Shim so ``rules.canvas.margin`` and ``rules.canvas.gutter`` still work."""
    width: int | None
    height: int | None
    margin: int
    gutter: int


class Guidelines:
    """Frozen guidelines object. Uses __slots__ + __init__ instead of dataclass
    to allow a ``canvas`` property that returns the backward-compatible shim."""

    __slots__ = ("name", "version", "spacing", "_canvas", "page", "palette",
                 "typography", "layouts", "check", "sources", "raw")

    def __init__(self, *, name: str, version: int, spacing: Spacing, canvas: Canvas,
                 page: PageRules, palette: Palette, typography: dict[str, FontRule],
                 layouts: Layouts, check: CheckRules, sources: tuple[str, ...],
                 raw: dict[str, Any]) -> None:
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "version", version)
        object.__setattr__(self, "spacing", spacing)
        object.__setattr__(self, "_canvas", canvas)
        object.__setattr__(self, "page", page)
        object.__setattr__(self, "palette", palette)
        object.__setattr__(self, "typography", typography)
        object.__setattr__(self, "layouts", layouts)
        object.__setattr__(self, "check", check)
        object.__setattr__(self, "sources", sources)
        object.__setattr__(self, "raw", raw)

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError("Guidelines is immutable")

    # --- Backward-compatible access (step 3 simplifies this back to a dataclass) ---

    @property
    def canvas(self) -> _CanvasCompat:
        """Returns a compat shim with width, height, margin AND gutter so old code
        that reads ``rules.canvas.margin`` still works."""
        return _CanvasCompat(
            width=self._canvas.width, height=self._canvas.height,
            margin=self.spacing.margin, gutter=self.spacing.gutter,
        )

    @property
    def grid(self) -> _GridCompat:
        snap = _get(self.raw, "grid.snap")
        snap = snap if isinstance(snap, bool) else True
        max_resize = _get(self.raw, "grid.max_resize", _MISSING)
        if max_resize is _MISSING:
            max_resize = 0.25  # default when not explicitly set
        elif max_resize is None:
            pass  # explicit null disables it
        elif isinstance(max_resize, bool) or not isinstance(max_resize, (int, float)):
            max_resize = 0.25
        return _GridCompat(size=self.spacing.grid, snap=snap,
                           max_resize=float(max_resize) if max_resize is not None else None)


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
        data = yaml.safe_load(path.read_bytes())  # bytes: PyYAML detects UTF-8, BOM and UTF-16
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
        layers.append((str(guidelines), _anchor(_read(guidelines), guidelines)))
    if report_dir is not None and (report_dir / REPORT_OVERRIDE).is_file():
        override = report_dir / REPORT_OVERRIDE
        layers.append((str(override), _anchor(_read(override), override)))
    if overrides:
        layers.append(("command line", overrides))

    raw: dict[str, Any] = {}
    for _, layer in layers:
        raw = merge(raw, layer)
    return _build(raw, tuple(name for name, _ in layers))


def _build(raw: dict[str, Any], sources: tuple[str, ...]) -> Guidelines:
    # Severity: use defaults, allow overrides from raw for backward compat with existing files.
    severity = dict(DEFAULT_SEVERITY)
    raw_severity = _get(raw, "check.severity", {})
    if isinstance(raw_severity, dict):
        for rule, level in raw_severity.items():
            level = "off" if level is False else level  # YAML 1.1: unquoted off → False
            if rule not in RULES:
                raise GuidelinesError(f"check.severity: unknown rule {rule!r} (known: {', '.join(RULES)})")
            if not isinstance(level, str) or level not in SEVERITIES:
                raise GuidelinesError(f"check.severity.{rule} must be one of {', '.join(SEVERITIES)}")
            severity[rule] = level

    decorative = _get(raw, "check.decorative_types", list(DEFAULT_DECORATIVE_TYPES))
    if not isinstance(decorative, list) or not all(isinstance(t, str) for t in decorative):
        raise GuidelinesError("check.decorative_types must be a list of visual type names")

    policy = _get(raw, "page.density_policy")
    if not isinstance(policy, str) or policy not in DENSITY:
        raise GuidelinesError(
            f"page.density_policy must be one of {', '.join(sorted(DENSITY))}, got {policy!r}")

    return Guidelines(
        name=str(raw.get("name", "")),
        version=_int(raw, "version", minimum=1),
        spacing=_spacing(raw),
        canvas=Canvas(width=_int(raw, "canvas.width", minimum=1, nullable=True),
                      height=_int(raw, "canvas.height", minimum=1, nullable=True)),
        page=PageRules(max_visuals=_int(raw, "page.max_visuals", minimum=1, nullable=True),
                       density_policy=policy,
                       require_title=_bool(raw, "page.require_title"),
                       title_region=_title_region(raw)),
        palette=_palette(raw),
        typography=_typography(raw),
        layouts=_layouts(raw),
        check=CheckRules(severity=severity, decorative_types=tuple(decorative)),
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


def _spacing(raw: dict[str, Any]) -> Spacing:
    # Accept both new paths (spacing.*) and old paths (grid.size, canvas.margin, canvas.gutter).
    # New paths take priority if both exist.
    grid = _get(raw, "spacing.grid")
    if grid is None:
        grid = _get(raw, "grid.size")
    if grid is None:
        grid = 8  # fallback
    if isinstance(grid, bool) or not isinstance(grid, int) or grid < 1:
        raise GuidelinesError(f"spacing.grid must be an integer >= 1, got {grid!r}")

    margin = _get(raw, "spacing.margin")
    if margin is None:
        margin = _get(raw, "canvas.margin")
    if margin is None:
        margin = 0
    if isinstance(margin, bool) or not isinstance(margin, int) or margin < 0:
        raise GuidelinesError(f"spacing.margin must be an integer >= 0, got {margin!r}")

    gutter = _get(raw, "spacing.gutter")
    if gutter is None:
        gutter = _get(raw, "canvas.gutter")
    if gutter is None:
        gutter = 0
    if isinstance(gutter, bool) or not isinstance(gutter, int) or gutter < 0:
        raise GuidelinesError(f"spacing.gutter must be an integer >= 0, got {gutter!r}")

    # Validate old-path keys that the compat shim exposes (step 3 removes these).
    snap = _get(raw, "grid.snap")
    if snap is not None and not isinstance(snap, bool):
        raise GuidelinesError(f"grid.snap must be true or false, got {snap!r}")
    max_resize = _get(raw, "grid.max_resize")
    if max_resize is not None:
        if isinstance(max_resize, bool) or not isinstance(max_resize, (int, float)) or max_resize < 0:
            raise GuidelinesError(f"grid.max_resize must be a number >= 0 or null, got {max_resize!r}")

    return Spacing(grid=grid, margin=margin, gutter=gutter)


def _palette(raw: dict[str, Any]) -> Palette:
    enforce = _get(raw, "palette.enforce")
    enforce = "off" if enforce is False else enforce  # unquoted YAML `off` parses as false
    if not isinstance(enforce, str) or enforce not in ("strict", "warn", "off"):
        raise GuidelinesError(f"palette.enforce must be strict, warn or off, got {enforce!r}")
    return Palette(
        categorical=_hex_list(raw, "palette.categorical"),
        background=_hex(_get(raw, "palette.background"), "palette.background", nullable=True),
        text=_hex(_get(raw, "palette.text"), "palette.text", nullable=True),
        extra=_hex_list(raw, "palette.extra"),
        enforce=enforce,
    )


def _typography(raw: dict[str, Any]) -> dict[str, FontRule]:
    section = _get(raw, "typography")
    if section is None:
        return {}
    if not isinstance(section, dict):
        raise GuidelinesError("typography must be a mapping of role -> {font, size}")
    out: dict[str, FontRule] = {}
    for role, spec in section.items():
        key = f"typography.{role}"
        if role in _ROLE_COMPAT:
            role = _ROLE_COMPAT[role]
        if role not in TYPOGRAPHY_ROLES:
            raise GuidelinesError(f"{key}: unknown role (known: {', '.join(TYPOGRAPHY_ROLES)})")
        if not isinstance(spec, dict):
            raise GuidelinesError(f"{key} must be a mapping with font and/or size")
        if "weight" in spec:
            raise GuidelinesError(
                f"{key}.weight: Power BI has no separate weight; a weight is part of the font "
                "face. Use the exact name from Desktop's font list, e.g. font: Segoe UI Semibold")
        if "bold" in spec:
            raise GuidelinesError(
                f"{key}.bold: Power BI encodes weight in the font face name. "
                "Use font: Segoe UI Semibold instead of bold: true")
        unknown = set(spec) - {"font", "size"}
        if unknown:
            raise GuidelinesError(f"{key}: unknown keys {', '.join(sorted(map(str, unknown)))}")
        fonts = spec.get("font", [])
        fonts = [fonts] if isinstance(fonts, str) else fonts
        if not isinstance(fonts, list) or not all(isinstance(f, str) and f.strip() for f in fonts):
            raise GuidelinesError(f"{key}.font must be a font name or a list of names")
        sizes = spec.get("size", [])
        sizes = [sizes] if isinstance(sizes, (int, float)) and not isinstance(sizes, bool) else sizes
        if not isinstance(sizes, list) or not all(
                isinstance(z, (int, float)) and not isinstance(z, bool) and z > 0 for z in sizes):
            raise GuidelinesError(f"{key}.size must be a positive number (pt) or a list of them")
        out[role] = FontRule(tuple(f.strip() for f in fonts), tuple(float(z) for z in sizes))
    return out


def _title_region(raw: dict[str, Any]) -> str | None:
    value = _get(raw, "page.title_region")
    if value is not None and (not isinstance(value, str) or not value.strip()):
        raise GuidelinesError(f"page.title_region must be a region role (e.g. header) or null, got {value!r}")
    return value.strip() if value else None


def _anchor(layer: dict[str, Any], path: Path) -> dict[str, Any]:
    """Resolve a layer's relative layouts.search_path entries against the file declaring them,
    so a guidelines file works from any current directory."""
    section = layer.get("layouts")
    if not isinstance(section, dict) or not isinstance(section.get("search_path"), list):
        return layer
    base = path.resolve().parent
    resolved = [str((base / p).resolve()) if isinstance(p, str) else p for p in section["search_path"]]
    return {**layer, "layouts": {**section, "search_path": resolved}}


def _layouts(raw: dict[str, Any]) -> Layouts:
    search = _get(raw, "layouts.search_path", [])
    if not isinstance(search, list) or not all(isinstance(p, str) and p for p in search):
        raise GuidelinesError("layouts.search_path must be a list of directories")
    default = _get(raw, "layouts.default")
    if default is not None and (not isinstance(default, str) or not default.strip()):
        raise GuidelinesError("layouts.default must be a layout name")
    return Layouts(tuple(Path(p) for p in search), default)
