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

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from blueprint.model import Rect
from blueprint.pbir import schemas
from blueprint.pbir.reader import (
    BINDINGS_ANNOTATION,
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
    kind: str  # "measure" | "column" | "hierarchy_level"
    table: str
    name: str  # the measure, column or hierarchy
    level: str | None = None  # hierarchy_level only

    def field(self) -> dict:
        source = {"SourceRef": {"Entity": self.table}}
        if self.kind == "hierarchy_level":
            # probe 16: a level of a hierarchy built in the model
            return {"HierarchyLevel": {"Expression": {"Hierarchy": {"Expression": source, "Hierarchy": self.name}},
                                       "Level": self.level}}
        key = "Measure" if self.kind == "measure" else "Column"
        return {key: {"Expression": source, "Property": self.name}}

    def projection(self, active: bool | None = None) -> dict:
        if self.kind == "hierarchy_level":
            refs = {"queryRef": f"{self.table}.{self.name}.{self.level}",
                    "nativeQueryRef": f"{self.name} {self.level}"}
        else:
            refs = {"queryRef": f"{self.table}.{self.name}", "nativeQueryRef": self.name}
        p: dict[str, Any] = {"field": self.field(), **refs}
        if active is not None:
            p["active"] = active
        return p


# Roles whose column projections Desktop marks "active": every chart's Category (probes 04, 08, 12),
# the slicer's Values and the matrix's Rows and Columns (probe 20). It depends on the visual type:
# a table's Values (probe 08) and a KPI's TrendLine columns don't carry it.
ACTIVE_ROLES = frozenset({"Category"})
ACTIVE_BY_TYPE = {"slicer": frozenset({"Values"}), "pivotTable": frozenset({"Rows", "Columns"})}


def _active(visual_type: str, role: str) -> bool:
    return role in ACTIVE_ROLES or role in ACTIVE_BY_TYPE.get(visual_type, frozenset())


def _projections(role: str, fields: list[Binding], visual_type: str = "") -> list[dict]:
    """Projections for one role. In an active role (_active) every column is "active": true, as in
    Desktop's own drill-down (fixture 02), and a hierarchy's levels are active only on its first
    level, as Desktop created them (probe 16; the rest is drill view state)."""
    out, seen = [], set()
    marked = _active(visual_type, role)
    for b in fields:
        active = None
        if marked and b.kind == "column":
            active = True
        elif marked and b.kind == "hierarchy_level":
            active = (b.table, b.name) not in seen
            seen.add((b.table, b.name))
        out.append(b.projection(active))
    return out


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


def bindings_fingerprint(bound: dict[str, list[tuple]]) -> str:
    """A short, stable digest of role -> (kind, table, name, level) per field, in field order.
    Drill state (``active``) and Desktop's extras don't enter it, only what is bound where."""
    canonical = json.dumps([[role, [list(f) for f in fields]] for role, fields in sorted(bound.items())],
                           ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def bindings_annotation(mark: str) -> list[dict]:
    return [{"name": BINDINGS_ANNOTATION, "value": mark}]


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
           text: str | None = None, text_style: dict | None = None,
           options: list[tuple[str, str, str]] | None = None, bindings_mark: str | None = None) -> dict:
    """A visual container. ``bindings``: query role -> ordered fields. ``text``: textbox content.
    ``options``: (object, property, literal) formatting choices from the contract."""
    body: dict[str, Any] = {"visualType": visual_type}
    if bindings:
        # Desktop writes roles in alphabetical order (probe 10: Goal, Indicator, TrendLine).
        body["query"] = {"queryState": {role: {"projections": _projections(role, fields, visual_type)}
                                        for role, fields in sorted(bindings.items())}}
    if text is not None:
        body["objects"] = textbox_objects(text, text_style)
    if options:
        objects = body.setdefault("objects", {})
        for obj, prop, literal in options:
            entry = (objects.setdefault(obj, [{"properties": {}}]))[0]
            entry.setdefault("properties", {})[prop] = _literal(literal)
    if title is not None:
        body["visualContainerObjects"] = title_objects(title)
    return {
        "$schema": schema_url("visualContainer"),
        "name": name,
        "position": {"x": rect.x, "y": rect.y, "z": z, "height": rect.height, "width": rect.width,
                     "tabOrder": tab_order},
        "visual": body,
        "annotations": visual_annotations(spec_id, region)
        + (bindings_annotation(bindings_mark) if bindings_mark else []),
    }


def with_bindings(visual_doc: dict, visual_type: str, bindings: dict[str, list[Binding]]) -> dict:
    """``visual_doc`` with its query replaced by what a new visual with these bindings gets, and
    the state Desktop keeps about the old fields cleared, so the visual is as Blueprint would
    create it apart from what the user formatted:

    - ``query.queryState``: rendered as for a new visual (the verified shapes);
    - ``query.sortDefinition``: kept only if every field it sorts on is still bound;
    - ``filterConfig`` filters Desktop adds on its own (no ``filter`` condition, no ``howCreated``,
      probe 21) on fields no longer bound: dropped (Desktop adds them again on save); filters with
      a condition or made by the user are kept;
    - ``expansionStates`` (a slicer's expanded nodes, probe 20) naming a field no longer bound:
      dropped.

    A new Blueprint visual has none of the dropped parts, and Desktop takes it (probes 05-24)."""
    body = dict(visual_doc.get("visual") or {})
    state = {role: {"projections": _projections(role, fields, visual_type)}
             for role, fields in sorted(bindings.items())}
    bound = [p["field"] for entry in state.values() for p in entry["projections"]]
    refs = {p["queryRef"] for entry in state.values() for p in entry["projections"]}
    query: dict[str, Any] = {"queryState": state}
    sort = (body.get("query") or {}).get("sortDefinition")
    if isinstance(sort, dict) and all(s.get("field") in bound for s in sort.get("sort") or [] if isinstance(s, dict)):
        query["sortDefinition"] = sort
    body["query"] = query
    if "expansionStates" in body:
        kept = [e for e in body["expansionStates"] if isinstance(e, dict) and all(
            ref in refs for lv in e.get("levels") or [] for ref in (lv.get("queryRefs") or []))]
        if kept:
            body["expansionStates"] = kept
        else:
            del body["expansionStates"]
    out = {**visual_doc, "visual": body}
    config = visual_doc.get("filterConfig")
    if isinstance(config, dict) and isinstance(config.get("filters"), list):
        filters = [f for f in config["filters"] if not (
            isinstance(f, dict) and "filter" not in f and "howCreated" not in f and f.get("field") not in bound)]
        if filters:
            out["filterConfig"] = {**config, "filters": filters}
        else:
            out = {k: v for k, v in out.items() if k != "filterConfig"}
    return out


def with_option(visual_doc: dict, obj: str, prop: str, literal: str) -> dict:
    """``visual_doc`` with ``visual.objects.<obj>[0].properties.<prop>`` set to ``literal``,
    leaving every other formatting property as it is."""
    body = dict(visual_doc.get("visual") or {})
    objects = dict(body.get("objects") or {})
    entries = list(objects.get(obj) or [{}])
    first = dict(entries[0] or {})
    props = dict(first.get("properties") or {})
    props[prop] = _literal(literal)
    entries[0] = {**first, "properties": props}
    objects[obj] = entries
    body["objects"] = objects
    return {**visual_doc, "visual": body}


def option_literal(visual_doc: dict, obj: str, prop: str) -> str | None:
    """The literal at ``visual.objects.<obj>[0].properties.<prop>``, or None."""
    try:
        return visual_doc["visual"]["objects"][obj][0]["properties"][prop]["expr"]["Literal"]["Value"]
    except (KeyError, IndexError, TypeError):
        return None


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
