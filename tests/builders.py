"""Build tiny synthetic PBIR reports in a temp dir, using the shapes observed in schema.md."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from blueprint.pbir import jsonfmt

S = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition"


def write(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(jsonfmt.dump_bytes(doc))


def visual(name: str, x=0, y=0, w=100, h=100, vtype="card", **extra) -> dict:
    return {
        "$schema": f"{S}/visualContainer/2.13.0/schema.json",
        "name": name,
        "position": {"x": x, "y": y, "z": 0, "height": h, "width": w},
        "visual": {"visualType": vtype},
        **extra,
    }


def make_report(root: Path, pages: dict[str, list[dict]], order: list[str] | None = None) -> Path:
    rd = root / "Test.Report"
    write(rd / "definition.pbir", {"version": "4.0",
                                   "datasetReference": {"byPath": {"path": "../Test.SemanticModel"}}})
    d = rd / "definition"
    write(d / "version.json", {"$schema": f"{S}/versionMetadata/1.0.0/schema.json", "version": "2.0.0"})
    write(d / "report.json", {"$schema": f"{S}/report/3.3.0/schema.json",
                              "themeCollection": {}})
    names = list(pages)
    write(d / "pages" / "pages.json", {"$schema": f"{S}/pagesMetadata/1.1.0/schema.json",
                                       "pageOrder": order if order is not None else names,
                                       "activePageName": names[0] if names else None})
    for page_name, visuals in pages.items():
        pd = d / "pages" / page_name
        write(pd / "page.json", {"$schema": f"{S}/page/2.1.0/schema.json", "name": page_name,
                                 "displayName": page_name.title(), "displayOption": "FitToPage",
                                 "height": 720, "width": 1280})
        for v in visuals:
            write(pd / "visuals" / v["name"] / "visual.json", v)
    return rd


def add_theme(report_dir: Path, layer: str, name: str, theme: dict | None, package: str = "SharedResources",
              folder: str = "BuiltInThemes") -> None:
    """Register a theme the way Desktop does (probe 02 phase 2); theme=None leaves the file missing."""
    path = report_dir / "definition" / "report.json"
    doc = jsonfmt.load(path)
    key = "baseTheme" if layer == "base" else "customTheme"
    doc.setdefault("themeCollection", {})[key] = {"name": name, "type": package}
    pkgs = doc.setdefault("resourcePackages", [])
    pkg = next((p for p in pkgs if p["name"] == package), None)
    if pkg is None:
        pkg = {"name": package, "type": package, "items": []}
        pkgs.append(pkg)
    rel = f"{folder}/{name}.json"
    pkg["items"].append({"name": name, "path": rel, "type": "BaseTheme" if layer == "base" else "CustomTheme"})
    write(path, doc)
    if theme is not None:
        write(report_dir / "StaticResources" / package / rel, {"name": name, **theme})


def hex_color(value: str) -> dict:
    return {"solid": {"color": {"expr": {"Literal": {"Value": f"'{value}'"}}}}}


def theme_color(color_id: int, percent: float = 0) -> dict:
    return {"solid": {"color": {"expr": {"ThemeDataColor": {"ColorId": color_id, "Percent": percent}}}}}
