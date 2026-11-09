"""Build new PBIR documents (page.json, visual.json) from model-level inputs.

Each shape is the minimal subset of what Desktop wrote when the same object was created by hand
in probe 04 (schema.md "Creating pages and visuals"), with keys in Desktop's order. What
Desktop adds on its own (``sortDefinition``, ``filterConfig`` filters,
``drillFilterOtherVisuals``) is left out. Probe 05 confirmed Desktop accepts these minimal
documents as written and doesn't add those keys on save.

Documents declare the newest *vendored* schema version for their kind, so they validate
exactly, and the writer refuses to create anything that doesn't.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from blueprint.model import Rect
from blueprint.pbir import schemas
from blueprint.pbir.reader import PAGE_ANNOTATION, VISUAL_ANNOTATION

_KIND = "item/report/definition"


def schema_url(kind: str) -> str:
    """URL of the newest vendored version of ``kind`` (e.g. "visualContainer")."""
    versions = schemas.vendored_versions(f"{_KIND}/{kind}")
    if not versions:
        raise LookupError(f"no vendored schema for {kind}")
    return schemas.SchemaRef(f"{_KIND}/{kind}", versions[-1]).url


@dataclass(frozen=True)
class Binding:
    kind: str  # "measure" | "column"
    table: str
    name: str

    def field(self) -> dict:
        key = "Measure" if self.kind == "measure" else "Column"
        return {key: {"Expression": {"SourceRef": {"Entity": self.table}}, "Property": self.name}}

    def projection(self) -> dict:
        # probe 04: category columns carried "active": true; measures had no "active" key.
        p: dict[str, Any] = {"field": self.field(), "queryRef": f"{self.table}.{self.name}",
                             "nativeQueryRef": self.name}
        if self.kind == "column":
            p["active"] = True
        return p


def _literal(value: str) -> dict:
    return {"expr": {"Literal": {"Value": value}}}


def _quote(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def page(name: str, display_name: str, width: int, height: int, spec_page: str) -> dict:
    return {
        "$schema": schema_url("page"),
        "name": name,
        "displayName": display_name,
        "displayOption": "FitToPage",
        "height": height,
        "width": width,
        "annotations": [{"name": PAGE_ANNOTATION, "value": spec_page}],
    }


def title_objects(title: str) -> dict:
    return {"title": [{"properties": {"show": _literal("true"), "text": _literal(_quote(title))}}]}


def visual(name: str, visual_type: str, rect: Rect, z: int, tab_order: int, spec_id: str, *,
           bindings: dict[str, list[Binding]] | None = None, title: str | None = None,
           text: str | None = None) -> dict:
    """A visual container. ``bindings``: query role -> ordered fields. ``text``: textbox content."""
    body: dict[str, Any] = {"visualType": visual_type}
    if bindings:
        body["query"] = {"queryState": {role: {"projections": [b.projection() for b in fields]}
                                        for role, fields in bindings.items()}}
    if text is not None:
        body["objects"] = {"general": [{"properties": {"paragraphs": [{"textRuns": [{"value": text}]}]}}]}
    if title is not None:
        body["visualContainerObjects"] = title_objects(title)
    return {
        "$schema": schema_url("visualContainer"),
        "name": name,
        "position": {"x": rect.x, "y": rect.y, "z": z, "height": rect.height, "width": rect.width,
                     "tabOrder": tab_order},
        "visual": body,
        "annotations": [{"name": VISUAL_ANNOTATION, "value": spec_id}],
    }


def bound_fields(visual_doc: dict) -> dict[str, list[tuple[str, str, str]]]:
    """Existing bindings by role, as (kind, table, name), for comparing with a spec."""
    out: dict[str, list[tuple[str, str, str]]] = {}
    state = (((visual_doc.get("visual") or {}).get("query") or {}).get("queryState")) or {}
    for role, entry in state.items():
        for p in (entry or {}).get("projections") or []:
            f = (p or {}).get("field") or {}
            for key, kind in (("Measure", "measure"), ("Column", "column")):
                if key in f:
                    table = ((f[key].get("Expression") or {}).get("SourceRef") or {}).get("Entity")
                    out.setdefault(role, []).append((kind, table, f[key].get("Property")))
    return out


def with_title(visual_doc: dict, title: str) -> dict:
    """``visual_doc`` with its title text set (and shown), leaving other title formatting alone."""
    body = dict(visual_doc.get("visual") or {})
    vco = dict(body.get("visualContainerObjects") or {})
    entries = list(vco.get("title") or [{}])
    props = dict((entries[0] or {}).get("properties") or {})
    props["show"] = _literal("true")
    props["text"] = _literal(_quote(title))
    entries[0] = {**(entries[0] or {}), "properties": props}
    vco["title"] = entries
    body["visualContainerObjects"] = vco
    return {**visual_doc, "visual": body}
