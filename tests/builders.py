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
