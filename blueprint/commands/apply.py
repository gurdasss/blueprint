"""`bp apply <spec>`: create or update one page from a page spec.

First run: a new page (sized to the layout's canvas) is created and registered in pages.json,
and one visual per placed spec entry, in the layout region it was assigned.

Re-run: the page and visuals Blueprint created are found again by their annotations, and only
what Blueprint owns is updated: positions (the layout is the source of truth) and titles.
Anything that would need guessing or destroying is refused or reported instead:

- page size differs from the layout's canvas: error (never scale a layout);
- a visual's type or field bindings changed in the spec: error (delete it in Desktop, re-apply);
- a Blueprint-created visual is no longer in the spec: warning, left in place (never delete);
- a new visual lands on a hand-placed one: warning (`bp check` reports the overlap).

Hand-placed visuals are never touched, and `blueprint: ignore` entries are never created or changed.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from blueprint import guidelines, layouts, manifest, spec
from blueprint.commands import manifest as manifest_cmd
from blueprint.model import Page, Report, Visual
from blueprint.pbir import ids, registry, render, semantic, writer
from blueprint.pbir.reader import read_report
from blueprint.plan import Plan
from blueprint.slots import contracts
from blueprint.validate import _intersects

PAGES = Path("definition/pages")


class ApplyError(Exception):
    pass


def _resolve(placements: list[layouts.Placement], report: Report) -> dict[str, dict[str, list[render.Binding]]]:
    """Spec field references -> PBIR bindings by query role, checked against the semantic model."""
    if not any(p.visual.slots for p in placements):
        return {}
    pbir = report.source.documents[Path("definition.pbir")].data
    model = semantic.load(semantic.model_dir_for(report.root, pbir))
    known = contracts()
    out: dict[str, dict[str, list[render.Binding]]] = {}
    problems: list[str] = []
    for p in placements:
        v = p.visual
        roles: dict[str, list[render.Binding]] = {}
        for slot_name, refs in v.slots.items():
            role = known[v.type].slots[slot_name].role
            for j, ref in enumerate(refs):
                at = f"visuals[{v.index}].slots.{slot_name}" + (f"[{j}]" if len(refs) > 1 else "")
                try:
                    if ref.kind == "measure":
                        table = model.measure_table(ref.name)
                    else:
                        model.check_column(ref.table, ref.name)
                        table = ref.table
                except semantic.ModelError as exc:
                    problems.append(f"{at}: {exc}")
                    continue
                roles.setdefault(role, []).append(render.Binding(ref.kind, table, ref.name))
        out[v.id] = roles
    if problems:
        raise ApplyError("field references don't match the semantic model:\n  " + "\n  ".join(problems))
    return out


def _find_page(report: Report, name: str) -> Page | None:
    pages = [p for p in report.pages if p.spec_page == name]
    if len(pages) > 1:
        raise ApplyError(f"several pages are marked as Blueprint page {name!r}: "
                         + ", ".join(p.name for p in pages))
    return pages[0] if pages else None


# Desktop renumbers z and tabOrder in steps of 1000 when it saves a page (probe 05: 0, 1, 2
# became 0, 1000, 2000), so Blueprint writes them that way to avoid a rewrite on the first save.
STEP = 1000


def _next(page: Page | None, key: str) -> int:
    values = [v.source.data.get("position", {}).get(key) for v in (page.visuals if page else [])]
    nums = [int(x) for x in values if isinstance(x, (int, float)) and not isinstance(x, bool)]
    return (max(nums) // STEP + 1) * STEP if nums else 0


def build_plan(args: argparse.Namespace) -> Plan:
    page_spec = spec.load(args.spec)
    report = read_report(args.report)
    rules = guidelines.load(args.guidelines, report.root)
    layout_name = page_spec.layout or rules.layouts.default
    if not layout_name:
        raise ApplyError(f"{page_spec.source}: no layout (set `layout:` or layouts.default in guidelines)")
    layout = layouts.load(layout_name, rules.layouts.search_path)
    placements = layouts.place(page_spec, layout)
    bindings = _resolve(placements, report)
    known = contracts()
    plan = Plan(root=report.root)
    plan.warnings.extend(report.warnings)
    built_with = f"{rules.name}@{rules.version}"
    rule = rules.typography.get("header")
    header_style = render.text_style(rule.fonts[0] if rule and rule.fonts else None,
                                     rule.sizes[0] if rule and rule.sizes else None,
                                     rule.bold if rule else None)

    page = _find_page(report, page_spec.page)
    if page is None:
        pid = ids.page_id(page_spec.page, {p.name for p in report.pages})
        writer.add_create(plan, PAGES / pid / "page.json",
                          render.page(pid, page_spec.page, layout.width, layout.height, page_spec.page,
                                      layout.name, built_with),
                          f"new page {page_spec.page!r} ({layout.width}x{layout.height}, layout {layout.name})")
        registry_doc = report.source.documents.get(PAGES / "pages.json")
        if registry_doc is None:
            raise ApplyError("definition/pages/pages.json is missing; open and save the report in "
                             "Power BI Desktop first")
        writer.add_modify(plan, registry_doc, registry.with_page(registry_doc.data, pid),
                          f"register page {pid} in pageOrder", force_schema=args.force_schema)
    else:
        pid = page.name
        if (page.width, page.height) != (layout.width, layout.height):
            raise ApplyError(f"page {page.display_name!r} is {page.width}x{page.height} but layout "
                             f"{layout.name!r} is {layout.width}x{layout.height}; Blueprint doesn't "
                             "scale layouts. Resize the page in Desktop or choose a matching layout.")
        if (page.layout, page.guidelines) != (layout.name, built_with):
            writer.add_modify(plan, page.source, render.with_annotations(
                page.source.data, render.page_annotations(page_spec.page, layout.name, built_with)),
                f"page built with layout {layout.name}, guidelines {built_with} "
                f"(was {page.layout}, {page.guidelines})", force_schema=args.force_schema)

    existing: dict[str, Visual] = {v.spec_id: v for v in (page.visuals if page else []) if v.spec_id}
    hand_placed = [v for v in (page.visuals if page else []) if not v.spec_id]
    taken = {v.name for v in (page.visuals if page else [])}
    z, tab = _next(page, "z"), _next(page, "tabOrder")
    problems: list[str] = []

    for p in placements:
        vs, contract, rect = p.visual, known[p.visual.type], p.region.rect
        want = bindings.get(vs.id, {})
        current = existing.pop(vs.id, None)
        if current is not None:
            if current.visual_type != contract.visual_type:
                problems.append(f"visuals[{vs.index}] ({vs.id}): is a {current.visual_type} in the "
                                f"report but {vs.type} ({contract.visual_type}) in the spec")
                continue
            have = {role: [(f.kind, f.table, f.name) for f in fs] for role, fs in current.fields.items()}
            if have != {role: [(b.kind, b.table, b.name) for b in fs] for role, fs in want.items()}:
                problems.append(f"visuals[{vs.index}] ({vs.id}): field bindings differ from the "
                                "report; changing bindings isn't supported yet (delete the visual in "
                                "Desktop and re-apply)")
                continue
            current.rect = rect
            if current.region != p.region.key:
                current.source.data = render.with_annotations(
                    current.source.data, render.visual_annotations(vs.id, p.region.key))
            if vs.type == "header":
                updated = render.with_textbox(current.source.data, vs.title or "", header_style)
                if updated is None:
                    plan.warnings.append(f"{vs.id}: header textbox was edited by hand (not a single "
                                         "text run); its text and style were left as is")
                else:
                    current.source.data = updated
            elif vs.title is not None:
                current.title = vs.title
            continue

        vid = ids.visual_id(pid, vs.id, taken)
        taken.add(vid)
        is_header = vs.type == "header"
        doc = render.visual(vid, contract.visual_type, rect, z, tab, vs.id, p.region.key,
                            bindings=want or None,
                            title=None if is_header else vs.title, text=vs.title if is_header else None,
                            text_style=header_style if is_header else None)
        writer.add_create(plan, PAGES / pid / "visuals" / vid / "visual.json", doc,
                          f"new {vs.type} {vs.id!r} in region {p.region.key} at "
                          f"{rect.x},{rect.y} {rect.width}x{rect.height}")
        z, tab = z + STEP, tab + STEP
        for other in hand_placed:
            if _intersects(rect, other.rect):
                plan.warnings.append(f"{vs.id}: overlaps hand-placed visual {other.name} "
                                     f"({other.visual_type})")
    if problems:
        raise ApplyError("\n  ".join(problems))

    ignored = {v.id for v in page_spec.visuals if v.ignore}
    for sid, v in sorted(existing.items()):
        if sid not in ignored:
            plan.warnings.append(f"{sid}: Blueprint visual {v.name} is no longer in the spec; left "
                                 "in place (delete it in Desktop if it should go)")

    plan.writes.extend(writer.plan_writes(report, force_schema=args.force_schema).writes)
    return plan


def run(args: argparse.Namespace) -> int:
    plan = build_plan(args)
    if args.dry_run:
        if plan.writes:
            plan.warnings.append(f"{manifest.FILE} would be regenerated after these writes")
    else:
        writer.apply(plan)
        # The manifest describes the report after the writes, so it's rebuilt from disk.
        report = read_report(args.report)
        follow = manifest_cmd.plan_for(report, guidelines.load(args.guidelines, report.root))
        writer.apply(follow)
        plan.writes.extend(follow.writes)
    print(plan.render())
    if plan.writes and not args.dry_run:
        print(f"\nWrote {len(plan.writes)} file(s). If the report is open in Power BI Desktop, "
              "accept 'Apply external changes' (unsaved Desktop edits will be overwritten).",
              file=sys.stderr)
    return 0

