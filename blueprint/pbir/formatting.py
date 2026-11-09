"""Colours and themes in PBIR documents. Every shape here is verified in schema.md (probe 02).

Colours are found by shape, not by property name, because Desktop uses many property
names (``fill``, ``color``, ``fontColor``, ``background.color``, …):

- ``{"solid": {"color": {"expr": EXPR}}}`` anywhere in a document, where EXPR is
  ``{"Literal": {"Value": "'#RRGGBB'"}}`` (a hex colour), ``{"ThemeDataColor": {"ColorId": n,
  "Percent": p}}`` (a theme reference), or anything else (e.g. conditional formatting);
- ``textStyle.color`` as a plain hex string inside textbox ``textRuns``.

Themes: ``report.json`` ``themeCollection.{baseTheme,customTheme} = {name, type}``. The file
is the ``resourcePackages`` item with that name, found in the package of that type, at
``StaticResources/<package name>/<item path>``.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from blueprint.model import ColorUse, FontUse, TextClass, Theme

HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
# Path segments that carry no meaning for a reader of the finding.
_NOISE = {"visual", "objects", "visualContainerObjects", "properties", "general", "paragraphs",
          "textRuns"}


def _where(path: list[str | int]) -> str:
    parts = [p for p in path if isinstance(p, str) and p not in _NOISE]
    return ".".join(parts) or "color"


def _expr_color(expr: Any, path: list[str | int]) -> ColorUse:
    where = _where(path)
    if isinstance(expr, dict):
        lit = expr.get("Literal")
        if isinstance(lit, dict) and isinstance(lit.get("Value"), str):
            v = lit["Value"]
            if len(v) >= 2 and v[0] == v[-1] == "'" and HEX.match(v[1:-1]):
                return ColorUse(where, "hex", v[1:-1].upper())
        theme = expr.get("ThemeDataColor")
        if isinstance(theme, dict):
            return ColorUse(where, "theme",
                            f"ColorId {theme.get('ColorId')}, Percent {theme.get('Percent', 0)}")
        if expr:
            return ColorUse(where, "expression", next(iter(expr)))
    return ColorUse(where, "expression", None)


def colors_in(doc: Any) -> list[ColorUse]:
    """Every colour set in a visual.json or page.json document, in document order."""
    out: list[ColorUse] = []

    def walk(node: Any, path: list[str | int]) -> None:
        if isinstance(node, dict):
            solid = node.get("solid")
            if isinstance(solid, dict) and isinstance(solid.get("color"), dict) and "expr" in solid["color"]:
                out.append(_expr_color(solid["color"]["expr"], path))
            style = node.get("textStyle")
            if isinstance(style, dict) and isinstance(style.get("color"), str):
                c = style["color"]
                out.append(ColorUse("text", "hex", c.upper()) if HEX.match(c)
                           else ColorUse("text", "expression", c))
            for k, v in node.items():
                if k == "solid" or k == "textStyle":
                    continue
                walk(v, [*path, k])
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, [*path, i])

    walk(doc, [])
    return out


BUILTIN_THEME_TYPE = "SharedResources"


def theme_refs(report_doc: dict) -> list[tuple[str, str, str | None, Path | None]]:
    """(layer, theme name, resource type, file path relative to the .Report folder or None)."""
    collection = report_doc.get("themeCollection") or {}
    packages = report_doc.get("resourcePackages") or []
    out = []
    for layer, key in (("base", "baseTheme"), ("custom", "customTheme")):
        ref = collection.get(key)
        if not isinstance(ref, dict) or not ref.get("name"):
            continue
        name, ptype = ref["name"], ref.get("type")
        path = None
        for pkg in packages:
            if not isinstance(pkg, dict) or pkg.get("type") != ptype:
                continue
            for item in pkg.get("items") or []:
                if isinstance(item, dict) and item.get("name") == name and item.get("path"):
                    candidate = Path("StaticResources") / str(pkg.get("name", ptype)) / str(item["path"])
                    if _inside_report(candidate):
                        path = candidate
        out.append((layer, name, ptype, path))
    return out


def _inside_report(rel: Path) -> bool:
    """Paths come from the report itself: never follow one out of the report folder."""
    return not rel.is_absolute() and ".." not in rel.parts and not rel.drive


def theme_from(layer: str, name: str, data: Any, builtin: bool = False) -> Theme:
    def hexes(v: Any) -> tuple[str, ...]:
        return tuple(c.upper() for c in v if isinstance(c, str)) if isinstance(v, list) else ()

    def one(v: Any) -> str | None:
        return v.upper() if isinstance(v, str) and HEX.match(v) else None

    data = data if isinstance(data, dict) else {}
    return Theme(name, layer, False, builtin, hexes(data.get("dataColors")),
                 one(data.get("foreground")), one(data.get("background")), text_classes(data))


# --- fonts (probe 03) ----------------------------------------------------------------------

_SIZE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*(?:D|L|pt)?\s*$")

# Formatting objects whose font settings Blueprint understands, by role. Only these were
# observed in probe 03. Chart data labels also use `labels`, but only a card's `labels` is the
# callout value.
_CONTAINER_ROLES = {"title": "title", "subTitle": "subtitle"}


def first_family(stack: str) -> str | None:
    """First family of a CSS font stack, unquoted: "'Segoe UI Semibold', wf_…, arial" -> "Segoe UI Semibold"."""
    head = stack.split(",", 1)[0].strip().strip("'\"").strip()
    return head or None


def _literal(prop: Any) -> str | None:
    if isinstance(prop, dict):
        lit = (prop.get("expr") or {}).get("Literal")
        if isinstance(lit, dict) and isinstance(lit.get("Value"), str):
            return lit["Value"]
    return None


def _unquote(value: str) -> str:
    """A quoted string literal "'It''s'" -> "It's"."""
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1].replace("''", "'")
    return value


def parse_size(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, str):
        m = _SIZE.match(value)
        if m:
            return float(m.group(1))
    return None


def _font_from_props(role: str, props: dict) -> FontUse | None:
    family_lit = _literal(props.get("fontFamily"))
    size_lit = _literal(props.get("fontSize"))
    bold_lit = _literal(props.get("bold"))
    if family_lit is None and size_lit is None and bold_lit is None:
        return None
    raw = _unquote(family_lit) if family_lit is not None else None
    return FontUse(
        role=role,
        family=first_family(raw) if raw is not None else None,
        size=parse_size(size_lit),
        bold=None if bold_lit is None else bold_lit.lower() == "true",
        raw_family=raw,
    )


def fonts_in(visual: Any) -> list[FontUse]:
    """Font settings in a visual.json ``visual`` object, one entry per role and textbox run."""
    if not isinstance(visual, dict):
        return []
    out: list[FontUse] = []
    vco = visual.get("visualContainerObjects") or {}
    for key, role in _CONTAINER_ROLES.items():
        for entry in vco.get(key) or []:
            font = _font_from_props(role, (entry or {}).get("properties") or {})
            if font:
                out.append(font)
    objects = visual.get("objects") or {}
    if visual.get("visualType") == "card":
        for entry in objects.get("labels") or []:
            font = _font_from_props("callout", (entry or {}).get("properties") or {})
            if font:
                out.append(font)
    for general in objects.get("general") or []:
        for para in ((general or {}).get("properties") or {}).get("paragraphs") or []:
            for run in (para or {}).get("textRuns") or []:
                style = (run or {}).get("textStyle")
                if not isinstance(style, dict) or not style:
                    continue
                fam = style.get("fontFamily")
                weight = style.get("fontWeight")
                out.append(FontUse(
                    role="textbox",
                    family=first_family(fam) if isinstance(fam, str) else None,
                    size=parse_size(style.get("fontSize")),
                    bold=None if weight is None else str(weight).lower() == "bold",
                    raw_family=fam if isinstance(fam, str) else None,
                ))
    return out


def text_classes(data: Any) -> dict[str, TextClass]:
    """Theme ``textClasses``. ``fontFace`` is a plain name or a CSS font stack (not quoted)."""
    out: dict[str, TextClass] = {}
    for name, cls in ((data or {}).get("textClasses") or {}).items():
        if isinstance(cls, dict):
            face = cls.get("fontFace")
            out[name] = TextClass(first_family(face) if isinstance(face, str) else None,
                                  parse_size(cls.get("fontSize")))
    return out
