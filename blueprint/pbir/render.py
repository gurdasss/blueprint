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
from blueprint.pbir.reader import (
    GUIDELINES_ANNOTATION,
    LAYOUT_ANNOTATION,
    PAGE_ANNOTATION,
    REGION_ANNOTATION,
    SPEC_ANNOTATION,
    VISUAL_ANNOTATION,
)

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


def page_annotations(spec_page: str, layout: str, guidelines: str, spec: str) -> list[dict]:
    return [{"name": PAGE_ANNOTATION, "value": spec_page},
            {"name": SPEC_ANNOTATION, "value": spec},
            {"name": LAYOUT_ANNOTATION, "value": layout},
            {"name": GUIDELINES_ANNOTATION, "value": guidelines}]


def visual_annotations(spec_id: str, region: str) -> list[dict]:
    return [{"name": VISUAL_ANNOTATION, "value": spec_id}, {"name": REGION_ANNOTATION, "value": region}]


def with_annotations(doc: dict, wanted: list[dict]) -> dict:
    """``doc`` with Blueprint's annotations set to ``wanted``; any other annotations are kept."""
    names = {a["name"] for a in wanted}
    others = [a for a in doc.get("annotations", []) if not (isinstance(a, dict) and a.get("name") in names)]
    return {**doc, "annotations": [*others, *wanted]}


def page(name: str, display_name: str, width: int, height: int, spec_page: str, layout: str,
         guidelines: str, spec: str) -> dict:
    return {
        "$schema": schema_url("page"),
        "name": name,
        "displayName": display_name,
        "displayOption": "FitToPage",
        "height": height,
        "width": width,
        "annotations": page_annotations(spec_page, layout, guidelines, spec),
    }


def text_style(font: str | None, size: float | None, bold: bool | None) -> dict:
    """A textbox run's ``textStyle`` (probe 03: ``{"fontFamily": "Arial", "fontSize": "20pt",
    "fontWeight": "bold"}``). Desktop drops ``"normal"`` weights, so not-bold writes nothing."""
    style: dict = {}
    if font:
        style["fontFamily"] = font
    if size is not None:
        style["fontSize"] = f"{int(size) if float(size).is_integer() else size}pt"
    if bold:
        style["fontWeight"] = "bold"
    return style


def textbox_objects(text: str, style: dict | None = None) -> dict:
    run: dict = {"value": text}
    if style:
        run["textStyle"] = style
    return {"general": [{"properties": {"paragraphs": [{"textRuns": [run]}]}}]}


STYLE_KEYS = ("fontFamily", "fontSize", "fontWeight")


def with_textbox(visual_doc: dict, text: str, style: dict) -> dict | None:
    """``visual_doc`` with its single text run set to ``text`` and the style keys Blueprint owns
    (font, size, weight) set to ``style``. Other style keys, like colour, are kept. Returns None if
    the textbox no longer has exactly one paragraph with one run (edited by hand: leave it)."""
    body = visual_doc.get("visual") or {}
    try:
        general = body["objects"]["general"]
        paragraphs = general[0]["properties"]["paragraphs"]
        [para] = paragraphs
        [run] = para["textRuns"]
    except (KeyError, IndexError, TypeError, ValueError):
        return None
    kept = {k: v for k, v in (run.get("textStyle") or {}).items() if k not in STYLE_KEYS}
    new_style = {**kept, **style}
    new_run = {k: v for k, v in run.items() if k != "textStyle"}
    new_run["value"] = text
    if new_style:
        new_run["textStyle"] = new_style
    new_para = {**para, "textRuns": [new_run]}
    props = {**general[0]["properties"], "paragraphs": [new_para]}
    new_general = [{**general[0], "properties": props}, *general[1:]]
    return {**visual_doc, "visual": {**body, "objects": {**body["objects"], "general": new_general}}}


def title_objects(title: str) -> dict:
    return {"title": [{"properties": {"show": _literal("true"), "text": _literal(_quote(title))}}]}


def visual(name: str, visual_type: str, rect: Rect, z: int, tab_order: int, spec_id: str,
           region: str, *,
           bindings: dict[str, list[Binding]] | None = None, title: str | None = None,
           text: str | None = None, text_style: dict | None = None) -> dict:
    """A visual container. ``bindings``: query role -> ordered fields. ``text``: textbox content."""
    body: dict[str, Any] = {"visualType": visual_type}
    if bindings:
        body["query"] = {"queryState": {role: {"projections": [b.projection() for b in fields]}
                                        for role, fields in bindings.items()}}
    if text is not None:
        body["objects"] = textbox_objects(text, text_style)
    if title is not None:
        body["visualContainerObjects"] = title_objects(title)
    return {
        "$schema": schema_url("visualContainer"),
        "name": name,
        "position": {"x": rect.x, "y": rect.y, "z": z, "height": rect.height, "width": rect.width,
                     "tabOrder": tab_order},
        "visual": body,
        "annotations": visual_annotations(spec_id, region),
    }


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
