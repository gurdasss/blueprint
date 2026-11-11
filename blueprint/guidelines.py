"""Layered guideline resolution.

Layers, later overriding earlier (mappings merge key by key; anything else is replaced):

1. ``blueprint/defaults.yaml``                  ships with the tool
2. organisation guidelines                      ``--guidelines`` or ``$BLUEPRINT_GUIDELINES``
3. ``<report>/.blueprint.yaml``                 committed with the report
4. command-line overrides                       e.g. ``--grid 8``

Core keys (v1): version, name, canvas, spacing, page, palette, typography, layouts.
Everything else is opt-in under ``extensions:`` (see ``template/extensions.md``): extra
typography roles, severity overrides, decorative types, ``max_resize`` and
``custom_visuals.search_path`` (directories of visual contracts beyond the core seven). Keys the core
doesn't know inside ``extensions:`` are passed through untouched.

Keys from the pre-template schema (``grid:``, ``canvas.margin``, ``canvas.gutter``,
``check:``, the six old typography roles) are refused with the new key named, rather than
ignored: ignoring them would silently change what is checked.
"""

from __future__ import annotations

import difflib
import os
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
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

# Severity defaults baked into code: not part of the client's core file (extensions.severity
# overrides them). error fails `bp check`; warning is reported; off is skipped.
DEFAULT_SEVERITY: dict[str, str] = {
    "format": "error",      # schema-invalid files, names Desktop ignores, missing required files
    "bounds": "error",      # visual extends outside the page
    "grid": "error",        # an edge is off the grid (page edges count as grid lines)
    "margin": "warning",    # an edge is closer to the page edge than spacing.margin
    "gutter": "warning",    # two side-by-side or stacked visuals are closer than spacing.gutter
    "overlap": "warning",   # visuals partially overlap
    "page-size": "warning", # page size differs from canvas.width/height
    "density": "warning",   # more visuals than page.max_visuals
    "typography": "error",  # a font or size outside the typography guidelines
    "title": "error",       # a spec-built page has no header, or it's outside page.title_region
}

# The extensions.* sub-keys the core itself reads. Anything else under extensions: is passed
# through untouched for an extension validator, so this is documentation, not a whitelist.
EXTENSION_KEYS = ("severity", "decorative_types", "max_resize", "typography", "custom_visuals")

# Visual types allowed to contain other visuals (backgrounds, panels); exempt from margin/gutter.
DEFAULT_DECORATIVE_TYPES = ("image", "shape", "basicShape")

# `bp fmt` leaves a visual alone (with a warning) if snapping would change its width or height
# by more than this fraction. extensions.max_resize overrides it; null disables the limit.
DEFAULT_MAX_RESIZE = 0.25


class GuidelinesError(Exception):
    pass


@dataclass(frozen=True)
class Spacing:
    grid: int
    margin: int  # minimum distance from visual edges to the page edge
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


# The core's three client-facing roles, each mapped to the internal checking role it covers
# (the names `formatting.fonts_in` produces). page_title is the textbox `bp apply` creates for
# a `type: header` visual, visual_title a visual's own title, body any other textbox.
CORE_ROLES = {"page_title": "header", "visual_title": "title", "body": "textbox"}
# Further internal roles, opt-in under `extensions.typography` (template/extensions.md):
# subtitle, the old card's value and the new card's value (callout) and its Category label.
EXTENSION_ROLES = ("subtitle", "callout", "card_label")
TYPOGRAPHY_ROLES = tuple(CORE_ROLES) + EXTENSION_ROLES
# Internal role -> the client's name for it, for messages: a finding or note must name a key the
# client can actually write (the internal names are refused by the loader).
ROLE_LABEL = {**{internal: client for client, internal in CORE_ROLES.items()},
              **{role: role for role in EXTENSION_ROLES}}
ROLE_KEY = {**{internal: f"typography.{client}" for client, internal in CORE_ROLES.items()},
            **{role: f"extensions.typography.{role}" for role in EXTENSION_ROLES}}


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


@dataclass(frozen=True)
class Guidelines:
    name: str
    version: int
    canvas: Canvas
    spacing: Spacing
    page: PageRules
    palette: Palette
    typography: dict[str, FontRule]  # keyed by internal role (see CORE_ROLES)
    layouts: Layouts
    check: CheckRules
    visuals: tuple[Path, ...]  # extra directories of visual contracts; core seven always load
    max_resize: float | None
    sources: tuple[str, ...]
    raw: dict[str, Any] = field(repr=False)

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
    visuals: Sequence[Path] = (),
) -> Guidelines:
    """``visuals``: command-line ``--visuals DIR`` entries. They are **added** to whatever
    ``extensions.custom_visuals.search_path`` already names, rather than layered over it:
    ``merge()`` replaces a list, so a layer would otherwise drop the report's own opt-in and
    turn its pages into "unknown type"."""
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

    for name, layer in layers:
        _refuse_retired_keys(layer, name)
        _refuse_unknown_keys(layer, name)

    raw: dict[str, Any] = {}
    for _, layer in layers:
        raw = merge(raw, layer)
    return _build(raw, tuple(name for name, _ in layers),
                  tuple(Path(d).resolve() for d in visuals))


def overrides_from(settings: Sequence[str] | None) -> dict[str, Any] | None:
    """Layer 4 (``--set KEY=VALUE``, repeatable) as a guidelines layer.

    One flag for the whole core file, so the layering is real for every key instead of the one
    (``--grid``) that happened to have a flag. The key is a dotted path into the file
    (``spacing.grid``, ``typography.body.font``, ``extensions.severity.grid``) and the loader
    refuses a path outside the core, naming the closest real key."""
    if not settings:
        return None
    out: dict[str, Any] = {}
    for setting in settings:
        key, sep, text = setting.partition("=")
        if not sep:
            raise GuidelinesError(f"--set {setting}: expected KEY=VALUE, e.g. --set spacing.grid=8")
        parts = key.strip().split(".")
        if not all(parts) or not key.strip():
            raise GuidelinesError(f"--set {setting}: {key.strip()!r} is not a guidelines key "
                                  "(a dotted path, e.g. spacing.grid or typography.body.font)")
        nested: dict[str, Any] = {parts[-1]: _setting_value(text, setting)}
        for part in reversed(parts[:-1]):
            nested = {part: nested}
        out = merge(out, nested)
    return out


def _setting_value(text: str, setting: str) -> Any:
    """``--set``'s value, read as YAML so a number, a boolean, null and a list all work."""
    try:
        value = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise GuidelinesError(f"--set {setting}: {exc}") from exc
    # YAML reads a leading # as a comment, and a colour is the one core value that starts with
    # one: `--set palette.text=#333333` means the string, not nothing.
    return text if value is None and text.strip() not in ("null", "~", "") else value


# Keys of the pre-template schema -> what replaces them. Refused per layer, so the file that
# still carries one is named.
RETIRED: tuple[tuple[str, str], ...] = (
    ("grid.size", "spacing.grid"),
    ("grid.snap", "nothing: bp fmt always snaps"),
    ("grid.max_resize", "extensions.max_resize"),
    ("canvas.margin", "spacing.margin"),
    ("canvas.gutter", "spacing.gutter"),
    ("check.severity", "extensions.severity"),
    ("check.decorative_types", "extensions.decorative_types"),
)


# The whole core file: section -> its sub-keys (``()``: the section is a scalar). This is the
# "core 20%" in one place, and the loader refuses anything else so a typo can't pass silently:
# `spacing: {margn: 16}` used to load with the default margin and check nothing. `typography`'s
# roles are checked in _refuse_retired_keys (they map to internal roles), and `extensions:` is a
# pass-through for keys the core doesn't know.
CORE_KEYS: dict[str, tuple[str, ...]] = {
    "version": (),
    "name": (),
    "canvas": ("width", "height"),
    "spacing": ("grid", "margin", "gutter"),
    "page": ("max_visuals", "density_policy", "require_title", "title_region"),
    "palette": ("categorical", "background", "text", "extra", "enforce"),
    "typography": tuple(CORE_ROLES),
    "layouts": ("search_path", "default"),
}
PASS_THROUGH = "extensions"


def _unknown(name: str, known: Sequence[str], where: str, source: str) -> GuidelinesError:
    pool = sorted(known)
    same = [k for k in pool if k.lower() == name.lower()]
    close = same or difflib.get_close_matches(name, pool, n=2, cutoff=0.7)
    hint = f" (did you mean {' or '.join(close)}?)" if close else ""
    return GuidelinesError(f"{source}: unknown key {where}{name}{hint}. "
                           f"Known here: {', '.join(pool)}. Anything else goes under extensions:")


def _refuse_unknown_keys(layer: dict[str, Any], source: str) -> None:
    """Refuse a key the core doesn't implement, naming the closest one it does.

    Only `extensions:` is open: the core reads five sub-keys there and passes the rest through
    untouched (template/extensions.md), so an extension's own keys must not be refused here."""
    for key, value in layer.items():
        if key == PASS_THROUGH:
            continue
        if key not in CORE_KEYS:
            raise _unknown(str(key), [*CORE_KEYS, PASS_THROUGH], "", source)
        sub_keys = CORE_KEYS[key]
        if sub_keys and isinstance(value, dict):
            for inner in value:
                if inner not in sub_keys:
                    raise _unknown(str(inner), sub_keys, f"{key}.", source)


def _refuse_retired_keys(layer: dict[str, Any], source: str) -> None:
    for old, new in RETIRED:
        if _get(layer, old, _MISSING) is not _MISSING:
            raise GuidelinesError(f"{source}: {old} was replaced by {new}")
    if isinstance(layer.get("grid"), dict):
        raise GuidelinesError(f"{source}: the grid: section was replaced by spacing.grid")
    if isinstance(layer.get("check"), dict):
        raise GuidelinesError(f"{source}: the check: section moved to extensions "
                              "(extensions.severity, extensions.decorative_types)")
    section = layer.get("typography")
    if isinstance(section, dict):
        for role in section:
            if role in CORE_ROLES.values():  # the old name of a core role
                client = ROLE_LABEL[role]
                raise GuidelinesError(
                    f"{source}: typography.{role} was replaced by typography.{client}")
            if role in EXTENSION_ROLES:
                raise GuidelinesError(
                    f"{source}: typography.{role} is an extension role; "
                    f"move it to extensions.typography.{role}")
            if role not in CORE_ROLES:
                raise GuidelinesError(
                    f"{source}: typography.{role}: unknown role "
                    f"(core roles: {', '.join(CORE_ROLES)})")


def _build(raw: dict[str, Any], sources: tuple[str, ...],
           extra_visuals: tuple[Path, ...] = ()) -> Guidelines:
    ext = _get(raw, "extensions", {})
    if ext is None:
        ext = {}
    if not isinstance(ext, dict):
        raise GuidelinesError("extensions must be a mapping")

    policy = _get(raw, "page.density_policy")
    if not isinstance(policy, str) or policy not in DENSITY:
        raise GuidelinesError(
            f"page.density_policy must be one of {', '.join(sorted(DENSITY))}, got {policy!r}")

    return Guidelines(
        name=str(raw.get("name", "")),
        version=_int(raw, "version", minimum=1),
        canvas=Canvas(width=_int(raw, "canvas.width", minimum=1, nullable=True),
                      height=_int(raw, "canvas.height", minimum=1, nullable=True)),
        spacing=Spacing(grid=_int(raw, "spacing.grid", minimum=1),
                        margin=_int(raw, "spacing.margin", minimum=0),
                        gutter=_int(raw, "spacing.gutter", minimum=0)),
        page=PageRules(max_visuals=_int(raw, "page.max_visuals", minimum=1, nullable=True),
                       density_policy=policy,
                       require_title=_bool(raw, "page.require_title"),
                       title_region=_title_region(raw)),
        palette=_palette(raw),
        typography=_typography(raw, ext),
        layouts=_layouts(raw),
        check=CheckRules(severity=_severity(ext), decorative_types=_decorative(ext)),
        visuals=_visuals(ext) + tuple(d for d in extra_visuals if d not in _visuals(ext)),
        max_resize=_max_resize(ext),
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


def _severity(ext: dict[str, Any]) -> dict[str, str]:
    severity = dict(DEFAULT_SEVERITY)
    raw_severity = ext.get("severity", {})
    if raw_severity is None:
        return severity
    if not isinstance(raw_severity, dict):
        raise GuidelinesError("extensions.severity must be a mapping of rule -> error|warning|off")
    for rule, level in raw_severity.items():
        level = "off" if level is False else level  # YAML 1.1: unquoted off -> False
        if rule not in RULES:
            raise GuidelinesError(
                f"extensions.severity: unknown rule {rule!r} (known: {', '.join(RULES)})")
        if not isinstance(level, str) or level not in SEVERITIES:
            raise GuidelinesError(
                f"extensions.severity.{rule} must be one of {', '.join(SEVERITIES)}")
        severity[rule] = level
    return severity


def _decorative(ext: dict[str, Any]) -> tuple[str, ...]:
    value = ext.get("decorative_types", list(DEFAULT_DECORATIVE_TYPES))
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(t, str) for t in value):
        raise GuidelinesError("extensions.decorative_types must be a list of visual type names")
    return tuple(value)


def _visuals(ext: dict[str, Any]) -> tuple[Path, ...]:
    """extensions.custom_visuals.search_path: directories holding further visual contracts.
    A missing directory is refused here rather than later as a confusing "unknown type"."""
    section = ext.get("custom_visuals")
    if section is None:
        return ()
    if not isinstance(section, dict):
        raise GuidelinesError("extensions.custom_visuals must be a mapping with search_path")
    unknown = set(section) - {"search_path"}
    if unknown:
        raise GuidelinesError("extensions.custom_visuals: unknown keys "
                              + ", ".join(sorted(map(str, unknown))))
    search = section.get("search_path", [])
    if not isinstance(search, list) or not all(isinstance(p, str) and p for p in search):
        raise GuidelinesError("extensions.custom_visuals.search_path must be a list of directories")
    out = []
    for entry in search:
        path = Path(entry)
        if not path.is_dir():
            raise GuidelinesError(
                f"extensions.custom_visuals.search_path: {entry} is not a directory")
        out.append(path)
    return tuple(out)


def _max_resize(ext: dict[str, Any]) -> float | None:
    if "max_resize" not in ext:
        return DEFAULT_MAX_RESIZE
    value = ext["max_resize"]
    if value is None:
        return None  # explicit null: no limit
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise GuidelinesError(
            f"extensions.max_resize must be a number >= 0 or null, got {value!r}")
    return float(value)


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


def _typography(raw: dict[str, Any], ext: dict[str, Any]) -> dict[str, FontRule]:
    """Core roles from `typography:`, extension roles from `extensions.typography:`, both keyed
    by the internal role name the checking code and the theme writer use."""
    out: dict[str, FontRule] = {}
    for section, prefix, allowed in (
            (_get(raw, "typography"), "typography", CORE_ROLES),
            (ext.get("typography"), "extensions.typography",
             {r: r for r in EXTENSION_ROLES})):
        if section is None:
            continue
        if not isinstance(section, dict):
            raise GuidelinesError(f"{prefix} must be a mapping of role -> {{font, size}}")
        for role, spec in section.items():
            key = f"{prefix}.{role}"
            if role not in allowed:
                raise GuidelinesError(f"{key}: unknown role (known: {', '.join(allowed)})")
            out[allowed[role]] = _font_rule(spec, key)
    return out


def _font_rule(spec: Any, key: str) -> FontRule:
    if not isinstance(spec, dict):
        raise GuidelinesError(f"{key} must be a mapping with font and/or size")
    for banned, why in (
        ("weight", ("Power BI has no separate weight; a weight is part of the font face. Use "
                    "the exact name from Desktop's font list, e.g. font: Segoe UI Semibold")),
        ("bold", ("the core typography rule doesn't check bold. For a visual's text a weight "
                   "is part of the face name (font: Segoe UI Semibold); a textbox run's own "
                   "fontWeight is no longer checked")),
    ):
        if banned in spec:
            raise GuidelinesError(f"{key}.{banned}: {why}")
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
    return FontRule(tuple(f.strip() for f in fonts), tuple(float(z) for z in sizes))


def _title_region(raw: dict[str, Any]) -> str | None:
    value = _get(raw, "page.title_region")
    if value is not None and (not isinstance(value, str) or not value.strip()):
        raise GuidelinesError(f"page.title_region must be a region role (e.g. header) or null, got {value!r}")
    return value.strip() if value else None


def _anchor(layer: dict[str, Any], path: Path) -> dict[str, Any]:
    """Resolve a layer's relative search_path entries (layouts, and extensions.custom_visuals)
    against the file declaring them, so a guidelines file works from any current directory."""
    base = path.resolve().parent
    out = layer
    section = out.get("layouts")
    if isinstance(section, dict) and isinstance(section.get("search_path"), list):
        out = {**out, "layouts": {**section, "search_path": _resolve_paths(section["search_path"], base)}}
    ext = out.get("extensions")
    visuals = ext.get("custom_visuals") if isinstance(ext, dict) else None
    if isinstance(visuals, dict) and isinstance(visuals.get("search_path"), list):
        out = {**out, "extensions": {
            **ext, "custom_visuals": {**visuals,
                                      "search_path": _resolve_paths(visuals["search_path"], base)}}}
    return out


def _resolve_paths(entries: list[Any], base: Path) -> list[Any]:
    return [str((base / p).resolve()) if isinstance(p, str) else p for p in entries]


def _layouts(raw: dict[str, Any]) -> Layouts:
    search = _get(raw, "layouts.search_path", [])
    if not isinstance(search, list) or not all(isinstance(p, str) and p for p in search):
        raise GuidelinesError("layouts.search_path must be a list of directories")
    default = _get(raw, "layouts.default")
    if default is not None and (not isinstance(default, str) or not default.strip()):
        raise GuidelinesError("layouts.default must be a layout name")
    return Layouts(tuple(Path(p) for p in search), default)
