"""`bp apply <spec>...`: create or update pages from page specs, one page per spec.

Several specs (or folders of ``*.yaml`` specs) can be given at once. All of them are checked
first (spec, layout, bindings, page ownership), and if any can't be applied nothing is written
and every problem is reported. Then they're applied in order and the manifest is regenerated once.

First run: a new page (sized to the layout's canvas) is created and registered in pages.json,
and one visual per placed spec entry, in the layout region it was assigned.

Re-run: the page and visuals Blueprint created are found again by their annotations, and only
what Blueprint owns is updated: positions (the layout is the source of truth) and titles.
Anything that would need guessing or destroying is refused or reported instead:

- page size differs from the layout's canvas: error (never scale a layout);
- a visual's type changed in the spec: error (delete it in Desktop, re-apply); changed field
  bindings or options are rebound or set in place (render.with_bindings, with_option);
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


def _resolve(placements: list[layouts.Placement], report: Report, visual_dirs: tuple[Path, ...] = (),
             ) -> tuple[dict[str, dict[str, list[render.Binding]]],
                        dict[str, tuple[render.Binding, str]]]:
    """Spec field references -> PBIR bindings by query role, and each visual's sort, both checked
    against the semantic model."""
    if not any(p.visual.slots for p in placements):
        return {}, {}
    pbir = report.source.documents[Path("definition.pbir")].data
    model = semantic.load(semantic.model_dir_for(report.root, pbir))
    known = contracts(visual_dirs)
    out: dict[str, dict[str, list[render.Binding]]] = {}
    sorts: dict[str, tuple[render.Binding, str]] = {}
    problems: list[str] = []
    for p in placements:
        v = p.visual
        roles: dict[str, list[render.Binding]] = {}
        for slot_name, refs in v.slots.items():
            slot = known[v.type].slots[slot_name]
            for j, ref in enumerate(refs):
                at = f"visuals[{v.index}].slots.{slot_name}" + (f"[{j}]" if len(refs) > 1 else "")
                levels = model.hierarchies.get((ref.table, ref.name)) if ref.kind == "column" else None
                if levels is not None:
                    # Table[Name] names a hierarchy built in the model (names are unique in a table):
                    # it binds all its levels in order, as Desktop does when one is dragged (probe 16).
                    if "hierarchy" not in slot.accepts:
                        problems.append(f"{at}: {ref} is a hierarchy, but {v.type}'s {slot_name} doesn't "
                                        "take one (no Desktop probe has verified it there)")
                        continue
                    roles.setdefault(slot.role, []).extend(
                        render.Binding("hierarchy_level", ref.table, ref.name, lvl) for lvl in levels)
                    continue
                try:
                    if ref.kind == "measure":
                        table = model.measure_table(ref.name)
                    else:
                        model.check_column(ref.table, ref.name)
                        table = ref.table
                except semantic.ModelError as exc:
                    problems.append(f"{at}: {exc}")
                    continue
                if ref.aggregate:
                    roles.setdefault(slot.role, []).append(render.Binding(
                        "aggregation", table, ref.name,
                        function=spec.AGGREGATIONS[ref.aggregate], format=ref.format))
                else:
                    roles.setdefault(slot.role, []).append(
                        render.Binding(ref.kind, table, ref.name, format=ref.format))
        if v.sort is not None:
            ref = v.sort.by
            try:
                table = model.measure_table(ref.name) if ref.kind == "measure" else ref.table
                if ref.kind != "measure":
                    model.check_column(ref.table, ref.name)
            except semantic.ModelError as exc:
                problems.append(f"visuals[{v.index}].sort.by: {exc}")
            else:
                sorts[v.id] = (render.Binding(ref.kind, table, ref.name),
                               spec.DIRECTIONS[v.sort.direction])
        for role, fields in roles.items():
            names = [f.projection()["nativeQueryRef"] for f in fields]
            clashes = sorted({n for n in names if names.count(n) > 1})
            for n in clashes:
                problems.append(
                    f"visuals[{v.index}]: two fields in {role} would both be called {n!r}. Desktop "
                    "names count and distinct count of a column the same and adds a digit by hand "
                    "(probe 29); Blueprint won't guess that, so bind one of them")
        out[v.id] = roles
    if problems:
        raise ApplyError("field references don't match the semantic model:\n  " + "\n  ".join(problems))
    return out, sorts


def _find_page(report: Report, page_spec: spec.PageSpec, take_over: bool) -> Page | None:
    """The page this spec builds: by spec id first (so renaming `page:` renames the page instead of
    creating a second one), then by page name for pages made before spec ids existed."""
    sid, name = page_spec.id, page_spec.page
    mine = [p for p in report.pages if p.spec == sid]
    if len(mine) > 1:
        raise ApplyError(f"several pages are marked as built by spec {sid!r}: "
                         + ", ".join(f"{p.display_name!r} ({p.name})" for p in mine)
                         + ". Blueprint can't tell which one the spec owns (a page copied in Desktop "
                         "may carry the mark). Keep one: delete the others, or remove the "
                         "blueprint.spec annotation from their page.json")
    named = [p for p in report.pages if p.spec_page == name and p not in mine]
    if mine:
        if named:
            other = named[0]
            raise ApplyError(f"spec {sid!r} renames its page to {name!r}, but another Blueprint page "
                             f"already has that name (built by spec {other.spec!r}); choose another name")
        return mine[0]
    if len(named) > 1:
        raise ApplyError(f"several pages are marked as Blueprint page {name!r}: "
                         + ", ".join(p.name for p in named))
    if not named:
        return None
    page = named[0]
    if page.spec is None or page.spec == sid or take_over:
        return page  # a page made before spec ids (adopted), or a deliberate take-over
    raise ApplyError(
        f"page {name!r} is built by spec {page.spec!r}, not {sid!r}. If it's the same spec (e.g. "
        f"the file was renamed), set `id: {page.spec}` in it; otherwise use another page name, or "
        "pass --take-over to make this spec build that page")


# Desktop renumbers z and tabOrder in steps of 1000 when it saves a page (probe 05: 0, 1, 2
# became 0, 1000, 2000), so Blueprint writes them that way to avoid a rewrite on the first save.
STEP = 1000


def _next(page: Page | None, key: str) -> int:
    positions = [v.source.data.get("position") for v in (page.visuals if page else [])]
    values = [p.get(key) for p in positions if isinstance(p, dict)]
    nums = [int(x) for x in values if isinstance(x, (int, float)) and not isinstance(x, bool)]
    return (max(nums) // STEP + 1) * STEP if nums else 0


def _bound(fields: dict) -> dict[str, list[tuple]]:
    """Role -> (kind, table, name, level-or-function) per field, for the report's fields or the
    spec's bindings. An aggregation has no level and a hierarchy level has no function, so the
    two share the slot: the tuple keeps its shape, and marks written before aggregations existed
    stay valid."""
    return {role: [(f.kind, f.table, f.name, f.level or f.function) for f in fs]
            for role, fs in fields.items()}


def _formats(fields: dict) -> dict[str, list[str | None]]:
    """Role -> each field's format string. Kept out of the fingerprint: the mark is what is
    *bound*, and a format is formatting that travels inside the projection (probe 29)."""
    return {role: [getattr(f, "format", None) for f in fs] for role, fs in fields.items()}


def _bindings_text(bound: dict[str, list[tuple]]) -> str:
    """Compactly, for the plan: Category [Country, Region]; Y [Total Amount]."""
    def name(kind: str, table: str, field: str, level: str | None) -> str:
        return f"{field}.{level}" if kind == "hierarchy_level" else field
    return "; ".join(f"{role} [{', '.join(name(*f) for f in fields)}]" for role, fields in sorted(bound.items()))


def _title_warnings(placements: list[layouts.Placement], rules: guidelines.Guidelines) -> list[str]:
    """What `bp check` will report under the title rules, said up front. A warning, not a refusal:
    like an overlap with a hand-placed visual, it's the guidelines' call, and check enforces it."""
    headers = [p for p in placements if p.visual.type == "header"]
    out = []
    if rules.page.require_title and not headers:
        out.append("no header: the guidelines require a page title (page.require_title); add a "
                   "`type: header` visual with the title as its `title`, or bp check will fail")
    want = rules.page.title_region
    if want:
        out += [f"{p.visual.id}: header placed in region {p.region.key}, but page.title_region is "
                f"{want!r}; bp check will fail" for p in headers if p.region.role != want]
    return out


def _gap_warnings(page_spec: spec.PageSpec, layout: layouts.Layout,
                  placements: list[layouts.Placement], rules: guidelines.Guidelines) -> list[str]:
    """An empty region leaves a gap. Blueprint never reflows a layout, so it says so and names
    the layouts on the search path that place this spec, on the same canvas and within the
    guidelines, with every region filled."""
    empty = layouts.unused(layout, placements)
    if not empty:
        return []
    fits = []
    for name in layouts.available(rules.layouts.search_path):
        if name == layout.name:
            continue
        try:
            other = layouts.load(name, rules.layouts.search_path)
            if ((other.width, other.height) != (layout.width, layout.height)
                    or layouts.conflicts(other, rules.spacing.grid, rules.spacing.margin,
                                         rules.spacing.gutter)):
                continue
            if not layouts.unused(other, layouts.place(page_spec, other, rules.visuals)):
                fits.append(name)
        except layouts.LayoutError:
            continue
    hint = (f"layout(s) that fit with no gap: {', '.join(fits)}" if fits
            else "no layout on the search path fits this spec with no gap")
    return [(f"layout {layout.name!r} leaves {', '.join(r.key for r in empty)} empty, a gap on "
            f"the page; {hint}")]


def build_plan(args: argparse.Namespace, spec_path: Path) -> Plan:
    report = read_report(args.report)
    rules = guidelines.load(args.guidelines, report.root, guidelines.overrides_from(getattr(args, "overrides", None)),
                            visuals=getattr(args, "visuals", None) or ())
    page_spec = spec.load(spec_path, rules.visuals)
    layout_name = page_spec.layout or rules.layouts.default
    if not layout_name:
        raise ApplyError(f"{page_spec.source}: no layout (set `layout:` or layouts.default in guidelines)")
    layout = layouts.load(layout_name, rules.layouts.search_path)
    clash = layouts.conflicts(layout, rules.spacing.grid, rules.spacing.margin, rules.spacing.gutter)
    if clash:
        raise ApplyError(f"layout {layout.name!r} doesn't fit the guidelines: bp apply and bp fmt "
                         "would keep moving its visuals back and forth, or bp check would flag "
                         "the page it builds. Fix the layout:\n  "
                         + "\n  ".join(clash))
    placements = layouts.place(page_spec, layout, rules.visuals)
    bindings, sorts = _resolve(placements, report, rules.visuals)
    known = contracts(rules.visuals)
    plan = Plan(root=report.root)
    plan.warnings.extend(report.warnings)
    plan.warnings.extend(_title_warnings(placements, rules))
    plan.warnings.extend(_gap_warnings(page_spec, layout, placements, rules))
    built_with = f"{rules.name}@{rules.version}"
    rule = rules.typography.get("header")
    header_style = render.text_style(rule.fonts[0] if rule and rule.fonts else None,
                                     rule.sizes[0] if rule and rule.sizes else None)

    page = _find_page(report, page_spec, getattr(args, "take_over", False))
    if page is None:
        pid = ids.page_id(page_spec.page, {p.name for p in report.pages})
        writer.add_create(plan, PAGES / pid / "page.json",
                          render.page(pid, page_spec.page, layout.width, layout.height, page_spec.page,
                                      layout.name, built_with, page_spec.id),
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
        have = (page.spec_page, page.spec, page.layout, page.guidelines)
        want = (page_spec.page, page_spec.id, layout.name, built_with)
        if have != want:
            data = render.with_annotations(page.source.data, render.page_annotations(
                page_spec.page, layout.name, built_with, page_spec.id))
            notes = []
            if page.spec_page != page_spec.page:
                data = {**data, "displayName": page_spec.page}
                notes.append(f"rename page {page.display_name!r} -> {page_spec.page!r}")
            if page.spec != page_spec.id:
                notes.append(f"built by spec {page_spec.id!r}" + (f" (was {page.spec!r})" if page.spec else ""))
            if (page.layout, page.guidelines) != (layout.name, built_with):
                notes.append(f"layout {layout.name}, guidelines {built_with} "
                             f"(was {page.layout}, {page.guidelines})")
            writer.add_modify(plan, page.source, data, "page: " + "; ".join(notes),
                              force_schema=args.force_schema)

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
            # Bindings that differ are rebound in place: the query is rewritten as for a new
            # visual and Desktop's state about the old fields is cleared (render.with_bindings);
            # title, formatting and position are kept.
            have = _bound(current.fields)
            edited = current.bindings_mark is not None and current.bindings_mark != render.bindings_fingerprint(have)
            if have != _bound(want) or _formats(current.fields) != _formats(want):
                if edited and not getattr(args, "overwrite_edits", False):
                    problems.append(
                        f"visuals[{vs.index}] ({vs.id}): its fields were changed in Desktop since "
                        f"Blueprint wrote them (now {_bindings_text(have)}); the spec says "
                        f"{_bindings_text(_bound(want))}. Put the Desktop change in the spec, or pass "
                        "--overwrite-edits to replace it")
                    continue
                current.source.data = render.with_bindings(current.source.data, want, contract.active_roles,
                                                            contract.all_level_roles)
                if have != _bound(want):
                    current.notes.append(f"rebind {_bindings_text(have)} -> {_bindings_text(_bound(want))}")
                else:
                    current.notes.append("format changed")
            if want and (have != _bound(want) or edited):  # record what is bound now
                mark = render.bindings_fingerprint(_bound(want))
                current.source.data = render.with_annotations(current.source.data,
                                                              render.bindings_annotation(mark))
            # The sort the spec asks for is set in place. A spec that says nothing about sorting
            # leaves whatever is there: Desktop's own default sort, or the user's (probe 31).
            wanted_sort = sorts.get(vs.id)
            if wanted_sort is not None:
                want_def = render.sort_definition(*wanted_sort)
                if render.current_sort(current.source.data) != want_def:
                    current.source.data = render.with_sort(current.source.data, wanted_sort)
                    current.notes.append(f"sort {wanted_sort[0].name} {wanted_sort[1].lower()}")
            # An option the spec sets is set in place; one the spec leaves out is Desktop's (or
            # the user's) to set, and left alone.
            for name, value in vs.options.items():
                opt = contract.options[name]
                prop, others = opt.prop(value), opt.siblings(value)
                stale = any(render.option_literal(current.source.data, opt.object, o) is not None
                            for o in others)
                if stale or render.option_literal(current.source.data, opt.object, prop) != opt.values[value]:
                    current.source.data = render.with_option(current.source.data, opt.object, prop,
                                                             opt.values[value], clear=others)
                    current.notes.append(f"option {name} -> {value}")
            current.rect = rect
            current.positioned = True  # the layout owns this visual's position: restore it
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
                            text_style=header_style if is_header else None,
                            options=[(contract.options[n].object, contract.options[n].prop(val),
                                      contract.options[n].values[val]) for n, val in vs.options.items()],
                            bindings_mark=render.bindings_fingerprint(_bound(want)) if want else None,
                            sort=sorts.get(vs.id), active_roles=contract.active_roles,
                            all_level_roles=contract.all_level_roles)
        writer.add_create(plan, PAGES / pid / "visuals" / vid / "visual.json", doc,
                          f"new {vs.type} {vs.id!r} in region {p.region.key} at "
                          f"{rect.x},{rect.y} {rect.width}x{rect.height}")
        z, tab = z + STEP, tab + STEP
        for other in hand_placed:
            if other.positioned and _intersects(rect, other.rect):
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


def spec_paths(items: list[Path]) -> list[Path]:
    """Spec files from the command line: files as given, folders as their ``*.yaml``, sorted."""
    out: list[Path] = []
    for item in items:
        if item.is_dir():
            found = sorted(item.glob("*.yaml"))
            if not found:
                raise ApplyError(f"{item}: folder has no *.yaml page specs")
            out.extend(found)
        else:
            out.append(item)
    seen: set[Path] = set()
    return [p for p in out if not (p.resolve() in seen or seen.add(p.resolve()))]


def _print(paths: list[Path], plans: list[Plan]) -> None:
    if len(plans) == 1:
        print(plans[0].render())
        return
    print("\n\n".join(f"== {path}\n{plan.render()}" for path, plan in zip(paths, plans, strict=True)))


_SPEC_PROBLEMS = (spec.SpecError, layouts.LayoutError, semantic.ModelError, ApplyError)


def _same_page_twice(paths: list[Path]) -> list[str]:
    """Two specs in one run that would build the same page: the second would fail half-way."""
    problems, ids_seen, pages_seen = [], {}, {}
    for path in paths:
        try:
            s = spec.load(path)
        except spec.SpecError:
            continue  # reported by the pre-flight
        for key, seen, what in ((s.id, ids_seen, "spec id"), (s.page, pages_seen, "page")):
            if key in seen:
                problems.append(f"{path}: {what} {key!r} is also used by {seen[key]}")
            seen.setdefault(key, path)
    return problems


def run(args: argparse.Namespace) -> int:
    paths = spec_paths(args.spec)
    # Pre-flight: every spec against the report as it is now. Nothing is written unless all pass.
    problems = _same_page_twice(paths)
    plans: list[Plan] = []
    for path in paths:
        try:
            plans.append(build_plan(args, path))
        except _SPEC_PROBLEMS as exc:
            problems.append(str(exc) if str(exc).startswith(str(path)) else f"{path}: {exc}")
    if problems:
        if len(paths) == 1:
            raise ApplyError(problems[0])
        raise ApplyError(f"{len(problems)} problem(s) in {len(paths)} spec(s); nothing was "
                         "written:\n" + "\n".join(problems))

    multi = len(paths) > 1
    if args.dry_run:
        if any(p.writes for p in plans):
            plans[-1].warnings.append(f"{manifest.FILE} would be regenerated after these writes"
                                      + ("; later specs were checked against the report as it is "
                                         "now, before the earlier ones" if multi else ""))
        _print(paths, plans)
        return 0

    for i, path in enumerate(paths):
        if i:  # the first plan is still current; later ones must see what earlier specs wrote
            plans[i] = build_plan(args, path)
        try:
            writer.apply(plans[i])
        except Exception as exc:
            if i:
                done = ", ".join(str(p) for p in paths[:i])
                raise ApplyError(f"{path}: {exc}\n(already applied: {done}; the rest were not)") from exc
            raise
    # The manifest describes the report after the writes, so it's rebuilt from disk.
    report = read_report(args.report)
    follow = manifest_cmd.plan_for(report, guidelines.load(
        args.guidelines, report.root, guidelines.overrides_from(getattr(args, "overrides", None)),
        visuals=getattr(args, "visuals", None) or ()))
    writer.apply(follow)
    if multi:
        _print([*paths, Path("manifest")], [*plans, follow])
    else:
        plans[0].writes.extend(follow.writes)
        _print(paths, plans)
    written = sum(len(p.writes) for p in plans) + (len(follow.writes) if multi else 0)
    if written:
        print(f"\nWrote {written} file(s). If the report is open in Power BI Desktop, "
              "accept 'Apply external changes' (unsaved Desktop edits will be overwritten).",
              file=sys.stderr)
    return 0

