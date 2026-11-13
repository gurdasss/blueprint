"""Guideline checks over the in-memory model. Pure, deterministic, and never mutating.

Used by ``bp check``; later also run after ``bp apply``. Format-level problems (schema
validity, names Desktop ignores) come from ``pbir/`` and are merged in by the command.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from blueprint import grid
from blueprint.guidelines import ROLE_LABEL, STRUCTURAL, Guidelines
from blueprint.model import ColorUse, FontUse, Page, Rect, Report, TextClass, Theme, Visual
from blueprint.policies import DENSITY


@dataclass(frozen=True)
class Finding:
    rule: str
    severity: str  # error | warning
    message: str
    page: str | None = None  # page id (folder name)
    visual: str | None = None


@dataclass
class CheckResult:
    findings: list[Finding] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)  # what was not checked, and why


def _fmt(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else f"{v:.2f}"


class _Collector:
    def __init__(self, rules: Guidelines, result: CheckResult) -> None:
        # palette's severity comes from palette.enforce (README), not extensions.severity.
        self.severity = {**rules.check.severity, "palette": rules.palette.severity}
        self.result = result

    def on(self, rule: str) -> bool:
        return self.severity[rule] != "off"

    def add(self, rule: str, message: str, page: Page | None = None, visual: Visual | None = None):
        if self.on(rule):
            self.result.findings.append(Finding(rule, self.severity[rule], message,
                                                page.name if page else None,
                                                visual.name if visual else None))


def check_report(report: Report, rules: Guidelines) -> CheckResult:
    result = CheckResult()
    c = _Collector(rules, result)
    for page in report.pages:
        _check_page(page, rules, c)
    if rules.palette.categorical and c.on("palette"):
        _check_palette(report, rules, c)
    if rules.typography and c.on("typography"):
        _check_typography(report, rules, c)
    if (rules.page.require_title or rules.page.title_region) and c.on("title"):
        _check_titles(report, rules, c)
    return result


def _check_titles(report: Report, rules: Guidelines, c: _Collector) -> None:
    """Only pages built from a spec: their header is the textbox Blueprint created. A hand-built
    page doesn't say which textbox is its title, and guessing would make false findings."""
    skipped = 0
    for page in report.pages:
        if page.spec_page is None:
            skipped += 1
            continue
        headers = [v for v in page.visuals
                   if v.spec_id and v.visual_type == "textbox" and not v.ignored]
        if rules.page.require_title and not headers:
            c.add("title", "no header: add a `type: header` visual to the page's spec "
                           "(page.require_title)", page)
        want = rules.page.title_region
        for v in headers:
            role = (v.region or "").split("#")[0]
            if want and role != want:
                c.add("title", f"header is in region {v.region or '(none)'}, but page.title_region "
                               f"is {want!r}", page, v)
    if skipped:
        c.result.notes.append(f"title rules not checked on {skipped} page(s) not built from a spec "
                              "(nothing marks which textbox is the title)")


def _check_page(page: Page, rules: Guidelines, c: _Collector) -> None:
    canvas = rules.canvas
    if page.width is None or page.height is None:
        if canvas.width is not None or canvas.height is not None:
            c.add("page-size", f"no fixed size (displayOption {page.display_option})", page)
        c.result.notes.append(f"{page.display_name}: geometry not checked (no fixed page size)")
    else:
        if (canvas.width is not None and page.width != canvas.width) or (
                canvas.height is not None and page.height != canvas.height):
            want = f"{canvas.width or '*'}x{canvas.height or '*'}"
            c.add("page-size", f"page is {_fmt(page.width)}x{_fmt(page.height)}, guidelines say {want}", page)
        _check_geometry(page, rules, c)

    if rules.page.max_visuals is not None:
        counted = DENSITY[rules.page.density_policy](page)
        if len(counted) > rules.page.max_visuals:
            c.add("density", f"{len(counted)} visuals (policy {rules.page.density_policy!r}) > "
                             f"max_visuals {rules.page.max_visuals}; split the page (not done "
                             "automatically)", page)


def _check_geometry(page: Page, rules: Guidelines, c: _Collector) -> None:
    assert page.width is not None and page.height is not None
    w, h, g = page.width, page.height, rules.spacing.grid
    candidates: list[Visual] = []
    grouped = 0
    for v in page.visuals:
        if v.ignored or not v.positioned:
            continue  # unpositioned visuals are reported as format problems
        if v.is_group or v.parent_group:
            grouped += 1
            continue
        candidates.append(v)
    if grouped:
        c.result.notes.append(f"{page.display_name}: {grouped} grouped visual(s) not checked "
                              "(group-relative positioning is unverified)")

    for v in candidates:
        r = v.rect
        out = [f"{name} by {_fmt(d)}" for name, d in (
            ("left", -r.x), ("top", -r.y), ("right", r.right - w), ("bottom", r.bottom - h)) if d > grid.EPS]
        if out:
            c.add("bounds", "outside the page: " + ", ".join(out), page, v)

        off = grid.off_grid_edges(r, g, w, h)
        if off:
            edges = ", ".join(f"{k}={_fmt(val)}" for k, val in off.items())
            c.add("grid", f"off the {g}px grid ({edges}); {_fmt_hint(r, rules, w, h)}", page, v)

        m = rules.spacing.margin
        if m and v.visual_type not in rules.check.decorative_types:
            near = [f"{name} {_fmt(d)}" for name, d in (
                ("left", r.x), ("top", r.y), ("right", w - r.right), ("bottom", h - r.bottom))
                if -grid.EPS <= d < m - grid.EPS]
            if near:
                c.add("margin", f"closer than {m}px to the page edge ({', '.join(near)})", page, v)

    decorative = set(rules.check.decorative_types)
    if rules.spacing.gutter and c.on("gutter"):
        spaced = [v for v in candidates if v.visual_type not in decorative]
        for i, a in enumerate(spaced):
            for b in spaced[i + 1:]:
                gap = gutter_gap(a.rect, b.rect)
                if gap is not None and gap < rules.spacing.gutter - grid.EPS:
                    c.add("gutter", f"{_fmt(gap)}px from {b.name} ({b.visual_type}); "
                                    f"spacing.gutter is {rules.spacing.gutter}px", page, a)

    if c.on("overlap"):
        for i, a in enumerate(candidates):
            for b in candidates[i + 1:]:
                if not _intersects(a.rect, b.rect):
                    continue
                if (a.visual_type in decorative and _contains(a.rect, b.rect)) or (
                        b.visual_type in decorative and _contains(b.rect, a.rect)):
                    continue  # a background or panel holding a visual is fine
                c.add("overlap", f"overlaps {b.name} ({b.visual_type})", page, a)


def _fmt_hint(r: Rect, rules: Guidelines, w: float, h: float) -> str:
    snapped = grid.snap_rect(r, rules.spacing.grid, w, h)
    ratio = grid.resize_ratio(r, snapped)
    if rules.max_resize is not None and ratio > rules.max_resize:
        return f"bp fmt skips it (would resize {ratio:.0%}); fix by hand or mark it blueprint.ignore"
    return "bp fmt fixes this"


def gutter_gap(a: Rect, b: Rect) -> float | None:
    """The gap between two rectangles that sit side by side or one above the other (they share
    part of a row or a column), or None if they overlap or are only diagonal neighbours.
    Touching edges are a gap of 0."""
    across = min(a.right, b.right) - max(a.x, b.x)  # > 0: they share part of a column
    down = min(a.bottom, b.bottom) - max(a.y, b.y)  # > 0: they share part of a row
    if across > grid.EPS and down > grid.EPS:
        return None  # overlapping: the overlap rule's business
    if down > grid.EPS:
        return -across
    if across > grid.EPS:
        return -down
    return None


def _intersects(a: Rect, b: Rect) -> bool:
    return (min(a.right, b.right) - max(a.x, b.x) > grid.EPS
            and min(a.bottom, b.bottom) - max(a.y, b.y) > grid.EPS)


def _contains(outer: Rect, inner: Rect) -> bool:
    e = grid.EPS
    return (outer.x - e <= inner.x and outer.y - e <= inner.y
            and inner.right <= outer.right + e and inner.bottom <= outer.bottom + e)


# --- palette ---------------------------------------------------------------------------


def effective_theme(themes: list[Theme]) -> Theme | None:
    """Custom theme fields override base theme fields. None if no theme file was readable."""
    found = [t for t in themes if not t.missing]
    if not found:
        return None
    eff = found[0]
    for t in found[1:]:
        eff = Theme(t.name, t.layer, False, t.builtin, t.data_colors or eff.data_colors,
                    t.foreground or eff.foreground, t.background or eff.background,
                    {**eff.sentiment, **t.sentiment}, {**eff.divergent, **t.divergent},
                    {**eff.structural, **t.structural},
                    _merge(eff.text_classes, t.text_classes), _merge(eff.visual_text, t.visual_text))
    return eff


def _merge(base: dict[str, TextClass], over: dict[str, TextClass]) -> dict[str, TextClass]:
    out = dict(base)
    for name, cls in over.items():
        b = out.get(name, TextClass())
        out[name] = TextClass(cls.font or b.font, cls.size if cls.size is not None else b.size)
    return out


def _check_palette(report: Report, rules: Guidelines, c: _Collector) -> None:
    pal = rules.palette
    for t in report.themes:
        if t.missing and t.builtin:
            c.result.notes.append(f"built-in {t.layer} theme {t.name!r} isn't embedded in the report; "
                                  "its colours can't be checked")
        elif t.missing:
            c.add("palette", f"{t.layer} theme {t.name!r} is referenced but its file is missing; "
                             "theme colours can't be checked")
    theme = effective_theme(report.themes)
    if theme is not None:
        _check_theme(theme, pal, c)

    allowed = pal.allowed
    theme_refs = expressions = 0
    off_text: list[list[ColorUse]] = []
    for page in report.pages:
        uses: list[tuple[Visual | None, ColorUse]] = [(None, u) for u in page.colors]
        uses += [(v, u) for v in page.visuals if not v.ignored for u in v.colors]
        off: dict[str | None, list[ColorUse]] = {}
        owner: dict[str | None, Visual | None] = {}
        for v, u in uses:
            if u.kind == "theme":
                theme_refs += 1
            elif u.kind == "expression":
                expressions += 1
            elif u.value not in allowed:
                key = v.name if v else None
                off.setdefault(key, []).append(u)
                owner[key] = v
        off_text.extend(off.values())
        for key, bad in off.items():
            listed = ", ".join(f"{u.where} {u.value}" for u in bad)
            c.add("palette", f"colours not in the palette: {listed}", page, owner[key])

    if any(u.where == "text" for bad in off_text for u in bad):
        c.result.notes.append("textbox colours picked from the theme are stored as resolved hex; "
                              "add approved shades to palette.extra")
    if theme_refs and theme is None:
        c.result.notes.append(f"{theme_refs} theme colour reference(s) not checked (no readable theme)")
    if expressions:
        c.result.notes.append(f"{expressions} colour expression(s) not checked "
                              "(e.g. conditional formatting)")


def _check_theme(theme: Theme, pal, c: _Collector) -> None:
    want = pal.categorical
    have = theme.data_colors[:len(want)]
    diffs = [f"{i + 1}: {h} (palette {w})" for i, (h, w) in enumerate(zip(have, want, strict=False))
             if h != w]
    if len(have) < len(want):
        diffs.append(f"theme has only {len(have)} data colours, palette has {len(want)}")
    if diffs:
        c.add("palette", f"theme {theme.name!r} data colours differ from palette.categorical at "
                         + "; ".join(diffs))
    for label, got, expected in (("background", theme.background, pal.background),
                                 ("foreground", theme.foreground, pal.text)):
        if expected and got != expected:
            c.add("palette", f"theme {theme.name!r} {label} is {got}, palette says {expected}")
    for kind, wanted, have in (("sentiment", pal.sentiment, theme.sentiment),
                               ("divergent", pal.divergent, theme.divergent)):
        for key, expected in wanted.items():
            got = have.get(key)
            if got != expected:
                c.add("palette", f"theme {theme.name!r} {kind} colour {key} is "
                                 f"{got or 'not set'}, palette says {expected}")
    for key, theme_key in STRUCTURAL.items():  # findings name the client's key, then the theme's
        expected = getattr(pal, key)
        got = theme.structural.get(theme_key)
        if expected and got != expected:
            c.add("palette", f"theme {theme.name!r} structural colour {key} ({theme_key}) is "
                             f"{got or 'not set'}, palette says {expected}")


# --- typography --------------------------------------------------------------------------

# Where a theme sets each typography role's default, as (textClasses name, Theme.visual_text key).
# probe 03: Desktop's "Title" is textClasses.title. probe 06: visualStyles["*"]["*"].title
# (and .subTitle) outrank textClasses, so a size set there is the one visuals actually get.
# probe 07: the new card's Category label is visualStyles.cardVisual["*"].label (size 12) over
# textClasses.label (its face, Segoe UI).
THEME_SOURCES = {"title": ("title", "title"), "subtitle": (None, "subTitle"), "callout": ("callout", None),
                 "card_label": ("label", "cardVisual.label")}


def theme_font(theme: Theme, role: str) -> TextClass | None:
    """The effective theme default for a typography role: visualStyles over textClasses."""
    cls_name, card = THEME_SOURCES[role]
    cls = theme.text_classes.get(cls_name) if cls_name else None
    vis = theme.visual_text.get(card) if card else None
    if cls is None and vis is None:
        return None
    cls, vis = cls or TextClass(), vis or TextClass()
    return TextClass(vis.font or cls.font, vis.size if vis.size is not None else cls.size)
# Family names seen in reports but not offered by Desktop's font list (probe 03); they look
# like theme font tokens. Reported as unresolved rather than as violations.
UNRESOLVED_FAMILIES = frozenset({"Heading"})


def _num(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else f"{v:g}"


def _font_problems(font: FontUse | TextClass, rule) -> list[str]:
    family = font.family if isinstance(font, FontUse) else font.font
    out = []
    if family is not None and rule.fonts and family not in rule.fonts:
        out.append(f"font {family!r} (allowed: {', '.join(rule.fonts)})")
    if font.size is not None and rule.sizes and font.size not in rule.sizes:
        out.append(f"size {_num(font.size)}pt (allowed: {', '.join(_num(z) for z in rule.sizes)})")
    return out


def _check_typography(report: Report, rules: Guidelines, c: _Collector) -> None:
    roles = rules.typography
    theme = effective_theme(report.themes)
    if theme is None:
        if any(r in THEME_SOURCES for r in roles):
            c.result.notes.append("theme text classes not checked (no readable theme)")
    else:
        for role in THEME_SOURCES:
            font = theme_font(theme, role) if role in roles else None
            if font is not None:
                problems = _font_problems(font, roles[role])
                if problems:
                    c.add("typography",
                          f"theme {theme.name!r} {ROLE_LABEL[role]} text: " + "; ".join(problems))

    unresolved: set[str] = set()
    for page in report.pages:
        for v in page.visuals:
            if v.ignored:
                continue
            problems = []
            for font in v.fonts:
                role = font.role
                if role == "textbox" and v.spec_id is not None and "header" in roles:
                    role = "header"  # a Blueprint header: checked against typography.header
                rule = roles.get(role)
                if rule is None:
                    continue
                if font.family in UNRESOLVED_FAMILIES:
                    unresolved.add(font.family)
                    font = FontUse(font.role, None, font.size, font.bold, font.raw_family)
                problems += [f"{ROLE_LABEL[role]} {p}" for p in _font_problems(font, rule)]
            if problems:
                c.add("typography", "; ".join(dict.fromkeys(problems)), page, v)
    if unresolved:
        c.result.notes.append(f"font name(s) {', '.join(sorted(unresolved))} not checked "
                              "(not a font Desktop offers; likely a theme font token)")
