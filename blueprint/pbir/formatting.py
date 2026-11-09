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

from blueprint.model import ColorUse, Theme

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


def theme_refs(report_doc: dict) -> list[tuple[str, str, Path | None]]:
    """(layer, theme name, file path relative to the .Report folder or None if unresolvable)."""
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
        out.append((layer, name, path))
    return out


def _inside_report(rel: Path) -> bool:
    """Paths come from the report itself: never follow one out of the report folder."""
    return not rel.is_absolute() and ".." not in rel.parts and not rel.drive


def theme_from(layer: str, name: str, data: Any) -> Theme:
    def hexes(v: Any) -> tuple[str, ...]:
        return tuple(c.upper() for c in v if isinstance(c, str)) if isinstance(v, list) else ()

    def one(v: Any) -> str | None:
        return v.upper() if isinstance(v, str) and HEX.match(v) else None

    data = data if isinstance(data, dict) else {}
    return Theme(name, layer, False, hexes(data.get("dataColors")),
                 one(data.get("foreground")), one(data.get("background")))
