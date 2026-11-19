"""`bp describe`: everything needed to write a valid page spec, in one read-only call.

Meant for whoever writes specs, usually an LLM agent: the spec syntax, the visual types and their
slots, the layouts the guidelines can use (with their regions), the guideline limits a page must
respect, and, with ``--report``, the model's fields written in spec syntax and the pages specs
have already built. ``--json`` gives the same content in machine-readable form, and
``--section`` (repeatable) keeps only the named parts, so an agent can ask for just what it needs.

The model section gives each field's type, sort-by column, default summarization and format
string, as the TMDL writes them, and the relationships. A property the TMDL doesn't write is an
explicit ``null`` ("checked: there is none"), never a missing key ("unknown"), so a reader never
has to guess. It is structure only, read fresh from the files: no data, no counts.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from blueprint import guidelines, layouts, spec
from blueprint.guidelines import Guidelines
from blueprint.model import Report
from blueprint.pbir import semantic
from blueprint.pbir.reader import read_report
from blueprint.slots import contracts

SPEC_SYNTAX = {
    "page_keys": {
        "page": "required; the page's display name",
        "layout": "optional; a layout name (default: the guidelines' layouts.default)",
        "id": "optional; the spec's stable identity (default: the file name). Lowercase letters, "
              "digits, hyphens. Re-applying a spec updates the page it built",
        "visuals": "required; a list. Visuals fill free layout regions of their role in list order",
    },
    "visual_keys": {
        "type": "required; one of the visual types",
        "id": "optional; stable identity within the page (default: <type>-<n>)",
        "title": "optional text; required for header (it is the header's text)",
        "region": "optional; a region role in the layout, overriding the type's default role",
        "slots": "mapping of slot name -> field reference, or a list where the slot allows one. "
                 "A slot entry may also be a mapping {field, aggregate, format} (see slot_keys)",
        "options": "optional mapping of option name -> value, from the type's options "
                   "(left out: Desktop's default)",
        "sort": "optional {by: <field>, direction: ascending|descending}; the field must be one "
                "this visual binds. `by` may be a slot-style mapping {field, aggregate} to sort on an "
                "aggregated column (a plain Table[Column] follows the visual's only aggregate of it; "
                "probe 41). Left out: Desktop's own default sort (probe 31)",
        "blueprint": "`ignore`: leave this visual alone (it takes no region)",
    },
    "fields": {
        "Table[Column]": "a column ('Table name'[Column] when the name has spaces or symbols)",
        "[Measure]": "a measure; its table is found in the model",
        "Table[Hierarchy]": "a hierarchy built in the model; binds all its levels in order",
    },
    "slot_keys": {
        "field": "required; the field reference, exactly as in the short form",
        "aggregate": "optional; summarise a column in this visual: "
                     + ", ".join(sorted(spec.AGGREGATIONS))
                     + ". `count` counts non-null values and `distinctcount` distinct ones "
                       "(probe 29). Only where the slot takes a measure",
        "format": "optional; a Power BI format string scoped to this visual, e.g. \"#,0.00\" or "
                  "'\"$\" #,0.00;(\"$\" #,0.00);\"$\" #,0.00' (probe 29). Blueprint writes the "
                  "string as given: it never invents a currency symbol",
    },
    "example": (
        "page: Sales Overview\n"
        "layout: standard-4-up\n"
        "visuals:\n"
        "  - type: header\n"
        "    title: Sales Overview\n"
        "  - type: card\n"
        "    title: Total\n"
        "    region: kpi-row\n"
        "    slots: {value: \"[Total Amount]\"}\n"
        "  - type: column\n"
        "    title: By Country\n"
        "    slots: {category: [\"Sales[Country]\", \"Sales[Region]\"], value: \"[Total Amount]\"}\n"
        "  - type: bar\n"
        "    title: Share by Region\n"
        "    slots: {category: \"Sales[Region]\", value: \"[Total Amount]\"}\n"
    ),
}


SECTIONS = ("spec", "guidelines", "types", "layouts", "model", "pages")
REPORT_SECTIONS = ("model", "pages")  # only with --report


class DescribeError(Exception):
    pass


def run(args: argparse.Namespace) -> int:
    wanted = list(dict.fromkeys(getattr(args, "section", None) or SECTIONS))
    needs_report = [s for s in wanted if s in REPORT_SECTIONS]
    if needs_report and not args.report and getattr(args, "section", None):
        raise DescribeError(f"--section {', '.join(needs_report)} needs --report")
    report = read_report(args.report) if args.report else None
    rules = guidelines.load(args.guidelines, report.root if report else None, guidelines.overrides_from(getattr(args, "overrides", None)),
                            visuals=getattr(args, "visuals", None) or ())
    data = {k: v for k, v in describe(rules, report).items() if k in wanted}
    print(json.dumps(data, indent=2, ensure_ascii=False) if args.json else to_text(data))
    return 0


def describe(rules: Guidelines, report: Report | None) -> dict[str, Any]:
    data: dict[str, Any] = {
        "spec": SPEC_SYNTAX,
        "guidelines": _guidelines(rules),
        "types": _types(rules.visuals),
        "layouts": _layouts(rules),
    }
    if report is not None:
        data["model"] = _model(report)
        data["pages"] = [{"name": p.display_name, "id": p.name, "spec": p.spec, "layout": p.layout,
                          "size": [p.width, p.height]} for p in report.pages]
    return data


def _guidelines(rules: Guidelines) -> dict[str, Any]:
    return {
        "name": rules.name, "version": rules.version, "sources": list(rules.sources),
        "canvas": {"width": rules.canvas.width, "height": rules.canvas.height},
        "spacing": {"grid": rules.spacing.grid, "margin": rules.spacing.margin,
                    "gutter": rules.spacing.gutter},
        "max_visuals": rules.page.max_visuals,
        "density_policy": rules.page.density_policy,
        "require_title": rules.page.require_title,
        "title_region": rules.page.title_region,
        "default_layout": rules.layouts.default,
    }


def _types(visual_dirs: tuple[Path, ...] = ()) -> dict[str, Any]:
    out = {}
    for name, c in contracts(visual_dirs).items():
        out[name] = {
            "visual_type": c.visual_type,
            "region": c.region,
            "slots": {s.name: {"accepts": list(s.accepts), "required": s.required, "list": s.ordered,
                               "list_excludes": list(s.list_excludes)}
                      for s in c.slots.values()},
            "options": {o.name: list(o.values) for o in c.options.values()},
        }
    return out


def _layouts(rules: Guidelines) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name in layouts.available(rules.layouts.search_path):
        entry: dict[str, Any] = {"default": name == rules.layouts.default}
        try:
            layout = layouts.load(name, rules.layouts.search_path)
        except layouts.LayoutError as exc:
            out[name] = {**entry, "usable": False, "problems": [str(exc)]}
            continue
        problems = layouts.conflicts(layout, rules.spacing.grid, rules.spacing.margin,
                                     rules.spacing.gutter)
        roles: dict[str, int] = {}
        for r in layout.regions:
            roles[r.role] = roles.get(r.role, 0) + 1
        out[name] = {**entry, "usable": not problems, "problems": problems,
                     "canvas": [layout.width, layout.height], "roles": roles,
                     "regions": [{"key": r.key, "role": r.role, "x": r.rect.x, "y": r.rect.y,
                                  "w": r.rect.width, "h": r.rect.height} for r in layout.regions]}
    return out


def _quote(table: str) -> str:
    return table if table.replace("_", "a").isalnum() else "'" + table.replace("'", "''") + "'"


def _ref(model: semantic.SemanticModel, quoted_table: str, name: str, is_measure: bool) -> str:
    """A field in spec syntax, flagged when a measure name lives in several tables."""
    if not is_measure:
        return f"{quoted_table}[{name}]"
    homes = model.measures.get(name, [])
    return f"[{name}]" + (f"  (ambiguous: in {', '.join(homes)})" if len(homes) > 1 else "")


def _model(report: Report) -> dict[str, Any]:
    pbir = report.source.documents.get(Path("definition.pbir"))
    try:
        model = semantic.load(semantic.model_dir_for(report.root, pbir.data if pbir else {}))
    except semantic.ModelError as exc:
        return {"available": False, "problem": str(exc), "tables": {}}
    # Hidden columns and measures are listed apart: what a report author sees in Desktop's Data
    # pane comes first. A hidden table's columns count as hidden, but its own visible measures are
    # listed (a hidden table holding the measures is a common pattern: the Procurement sample's
    # visuals use them). A hidden table with nothing visible (auto-date tables) is left out.
    tables: dict[str, Any] = {}
    left_out = []
    for table in sorted(model.tables):
        q = _quote(table)
        measures = sorted(m for m, homes in model.measures.items() if table in homes)
        columns = sorted(model.tables[table])
        hidden = {n for t, n in model.hidden if t == table}
        if table in model.hidden_tables:
            hidden |= set(columns)
            if not [m for m in measures if m not in hidden]:
                left_out.append(table)
                continue
        tables[table] = {
            "columns": [_ref(model, q, c, False) for c in columns if c not in hidden],
            "measures": [_ref(model, q, m, True) for m in measures if m not in hidden],
            "hierarchies": {f"{q}[{h}]": list(levels)
                            for (t, h), levels in sorted(model.hierarchies.items()) if t == table},
            "hidden": [_ref(model, q, n, n in measures) for n in sorted(set(columns) | set(measures))
                       if n in hidden],
            "fields": {_ref(model, q, n, n in measures).split("  (")[0]:
                       _field(model, table, q, n, n in measures, n in hidden)
                       for n in sorted(set(columns) | set(measures))},
        }
    shown = set(tables)
    rels = [r for r in model.relationships if r.from_table in shown and r.to_table in shown]
    return {"available": True, "tables": tables, "hidden_tables": left_out,
            "relationships": [{"from": f"{_quote(r.from_table)}[{r.from_column}]",
                               "to": f"{_quote(r.to_table)}[{r.to_column}]",
                               "properties": r.properties} for r in rels],
            "relationships_left_out": len(model.relationships) - len(rels)}


def _field(model: semantic.SemanticModel, table: str, q: str, name: str, is_measure: bool,
           hidden: bool) -> dict[str, Any]:
    """One field's structure, every key always present: None means the TMDL doesn't write it."""
    props = model.properties.get((table, name), {})
    out: dict[str, Any] = {"kind": "measure" if is_measure else "column", "hidden": hidden}
    for key, label in semantic.FIELD_PROPERTIES.items():
        out[label] = props.get(key)
    if out["sort_by"] is not None:
        out["sort_by"] = f"{q}[{out['sort_by']}]"
    return out


def to_text(data: dict[str, Any]) -> str:
    lines: list[str] = []
    if "guidelines" in data:
        lines += _text_guidelines(data["guidelines"])
    if "spec" in data:
        lines += _text_spec(data["spec"])
    if "types" in data:
        lines += _text_types(data["types"])
    if "layouts" in data:
        lines += _text_layouts(data["layouts"])
    if "model" in data:
        lines += _text_model(data["model"])
    if "pages" in data:
        lines += _text_pages(data["pages"])
    return "\n".join(lines).rstrip()


def _text_guidelines(g: dict[str, Any]) -> list[str]:
    c, sp = g["canvas"], g["spacing"]
    return [f"Guidelines: {g['name'] or '(unnamed)'} v{g['version']}  [{' < '.join(g['sources'])}]",
             (f"  canvas {c['width'] or '*'}x{c['height'] or '*'}, grid {sp['grid']}px, "
             f"margin {sp['margin']}px, gutter {sp['gutter']}px, max_visuals {g['max_visuals'] or 'none'} "
             f"(policy {g['density_policy']})"),
             *(["  every page needs a `type: header` visual (page.require_title)"
                + (f", in a {g['title_region']!r} region" if g["title_region"] else "")]
               if g["require_title"] else
               [f"  a header must be in a {g['title_region']!r} region"] if g["title_region"] else []),
             ""]


def _text_spec(s: dict[str, Any]) -> list[str]:
    lines = ["Spec syntax (YAML)"]
    lines += [f"  {k}: {v}" for k, v in s["page_keys"].items()]
    lines.append("  each visual:")
    lines += [f"    {k}: {v}" for k, v in s["visual_keys"].items()]
    lines.append("  field references:")
    lines += [f"    {k:<17} {v}" for k, v in s["fields"].items()]
    lines.append("  example:")
    lines += [f"    {ln}" for ln in s["example"].splitlines()]
    lines.append("")
    return lines


def _text_types(types: dict[str, Any]) -> list[str]:
    lines = ["Visual types (type -> default region; slots: accepted kinds, * required, [] list allowed)"]
    for name, t in types.items():
        slots = ", ".join(f"{n}{'*' if sl['required'] else ''}{'[]' if sl['list'] else ''}: "
                          f"{'|'.join(sl['accepts'])}"
                          + (f" (a list only without {'/'.join(sl['list_excludes'])})" if sl["list_excludes"] else "")
                          for n, sl in t["slots"].items())
        options = "; options " + ", ".join(f"{n}: {'|'.join(v)}" for n, v in t["options"].items()) \
            if t["options"] else ""
        width = max(map(len, types))
        lines.append(f"  {name:<{width}} region {t['region']:<8} {slots or '(no slots)'}{options}")
    lines.append("")
    return lines


def _text_layouts(lays: dict[str, Any]) -> list[str]:
    lines = ["Layouts"]
    if not lays:
        lines.append("  (none: layouts.search_path is empty; `bp init` writes a starter set)")
    for name, lay in lays.items():
        flag = " (default)" if lay["default"] else ""
        if "canvas" not in lay:
            lines.append(f"  {name}{flag}: unusable: {lay['problems'][0]}")
            continue
        roles = ", ".join(f"{n} {r}" for r, n in lay["roles"].items())
        w, h = lay["canvas"]
        lines.append(f"  {name}{flag}: {w}x{h}; {roles}")
        lines += [f"    unusable with these guidelines: {p}" for p in lay["problems"]]
    lines.append("")
    return lines


def _text_model(m: dict[str, Any]) -> list[str]:
    lines = ["Model fields"]
    if not m["available"]:
        lines.append(f"  not available: {m['problem']}")
    for table, t in m["tables"].items():
        lines.append(f"  {table}")
        if t["measures"]:
            lines.append(f"    measures: {', '.join(t['measures'])}")
        if t["columns"]:
            lines.append(f"    columns:  {', '.join(t['columns'])}")
        for h, levels in t["hierarchies"].items():
            lines.append(f"    hierarchy {h}: {' > '.join(levels)}")
        if t["hidden"]:
            lines.append(f"    hidden:   {', '.join(t['hidden'])}")
        for ref, f in t["fields"].items():
            if f["sort_by"]:
                lines.append(f"    {ref} sorts by {f['sort_by']}")
    if m.get("hidden_tables"):
        lines.append(f"  ({len(m['hidden_tables'])} hidden table(s) with nothing visible, not listed: "
                     f"{', '.join(m['hidden_tables'])})")
    if m.get("relationships"):
        lines.append("  relationships:")
        lines += [f"    {r['from']} -> {r['to']}" for r in m["relationships"]]
    lines.append("  (types, summarization and format strings: --json --section model)")
    lines.append("")
    return lines


def _text_pages(pages: list[dict[str, Any]]) -> list[str]:
    lines = ["Pages (spec = the spec id that built it)"]
    for p in pages:
        w, h = p["size"]
        size = f"{w:g}x{h:g}" if w is not None and h is not None else "no fixed size"
        built = f"spec {p['spec']}, layout {p['layout']}" if p["spec"] else "not built by a spec"
        lines.append(f"  {p['name']}  ({size}; {built})")
    return lines
