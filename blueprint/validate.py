"""Guideline checks over the in-memory model. Pure, deterministic, and never mutating.

Used by ``bp check``; later also run after ``bp apply``. Format-level problems (schema
validity, names Desktop ignores) come from ``pbir/`` and are merged in by the command.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from blueprint import grid
from blueprint.guidelines import Guidelines
from blueprint.model import Page, Rect, Report, Visual
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
        self.severity = rules.check.severity
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
    return result


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
    w, h, g = page.width, page.height, rules.grid.size
    candidates: list[Visual] = []
    grouped = 0
    for v in page.visuals:
        if v.ignored:
            continue
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

        m = rules.canvas.margin
        if m and v.visual_type not in rules.check.decorative_types:
            near = [f"{name} {_fmt(d)}" for name, d in (
                ("left", r.x), ("top", r.y), ("right", w - r.right), ("bottom", h - r.bottom))
                if -grid.EPS <= d < m - grid.EPS]
            if near:
                c.add("margin", f"closer than {m}px to the page edge ({', '.join(near)})", page, v)

    if c.on("overlap"):
        decorative = set(rules.check.decorative_types)
        for i, a in enumerate(candidates):
            for b in candidates[i + 1:]:
                if not _intersects(a.rect, b.rect):
                    continue
                if (a.visual_type in decorative and _contains(a.rect, b.rect)) or (
                        b.visual_type in decorative and _contains(b.rect, a.rect)):
                    continue  # a background or panel holding a visual is fine
                c.add("overlap", f"overlaps {b.name} ({b.visual_type})", page, a)


def _fmt_hint(r: Rect, rules: Guidelines, w: float, h: float) -> str:
    snapped = grid.snap_rect(r, rules.grid.size, w, h)
    ratio = grid.resize_ratio(r, snapped)
    if rules.grid.max_resize is not None and ratio > rules.grid.max_resize:
        return f"bp fmt skips it (would resize {ratio:.0%}); fix by hand or mark it blueprint.ignore"
    return "bp fmt fixes this"


def _intersects(a: Rect, b: Rect) -> bool:
    return (min(a.right, b.right) - max(a.x, b.x) > grid.EPS
            and min(a.bottom, b.bottom) - max(a.y, b.y) > grid.EPS)


def _contains(outer: Rect, inner: Rect) -> bool:
    e = grid.EPS
    return (outer.x - e <= inner.x and outer.y - e <= inner.y
            and inner.right <= outer.right + e and inner.bottom <= outer.bottom + e)
