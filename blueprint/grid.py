"""Snap visuals to the layout grid. Pure functions over the in-memory model.

Each of a visual's four edges is snapped to the nearest grid line independently, rather
than snapping the position and the size separately. Two visuals whose edges were nearly
aligned therefore end up exactly aligned, and near-equal sizes become equal.

Snapping is idempotent by construction: a grid-aligned edge rounds to itself.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from blueprint.model import Page, Rect, Report, Visual


@dataclass
class SnapResult:
    moved: list[tuple[str, str]] = field(default_factory=list)  # (page, visual)
    warnings: list[str] = field(default_factory=list)


def _nearest(v: float, grid: int) -> int:
    # Round half up (not banker's rounding) so results don't depend on parity.
    return math.floor(v / grid + 0.5) * grid


def _snap_edge(v: float, grid: int, limit: float) -> float:
    """Nearest grid line, treating the page edge ``limit`` as a snap line too.

    An edge that starts on the page never snaps past ``limit``. The page edge matters
    when the page size isn't a multiple of the grid (e.g. 720 on a 7px grid).
    """
    n = _nearest(v, grid)
    if v > limit:
        return n  # already off the page: snap normally; `check` reports it
    if n > limit or abs(limit - v) < abs(n - v):
        return limit
    return n


def _span(lo: float, hi: float, grid: int, limit: float, was_hi: float) -> tuple[float, float]:
    """Snap one axis. A visual never collapses below one grid cell, and growing it to one
    cell must not push it off the page: if there's no room after it, grow it the other way."""
    lo, hi = _snap_edge(lo, grid, limit), _snap_edge(hi, grid, limit)
    if hi - lo < grid:
        if lo + grid <= limit or was_hi > limit:
            hi = lo + grid
        else:
            hi = limit
            lo = max(0, math.floor((limit - grid) / grid) * grid)
    return lo, hi


def snap_rect(rect: Rect, grid: int, page_w: float, page_h: float) -> Rect:
    left, right = _span(rect.x, rect.right, grid, page_w, rect.right)
    top, bottom = _span(rect.y, rect.bottom, grid, page_h, rect.bottom)
    return Rect(left, top, right - left, bottom - top)


def _size(r: Rect) -> str:
    def n(v: float) -> str:
        return str(int(v)) if float(v).is_integer() else f"{v:.1f}"

    return f"{n(r.width)}x{n(r.height)}"


def _overlaps(a: Rect, b: Rect) -> bool:
    return a.x < b.right and b.x < a.right and a.y < b.bottom and b.y < a.bottom


def resize_ratio(before: Rect, after: Rect) -> float:
    """Largest relative change in width or height, e.g. 24 -> 32 tall is 0.33."""
    return max(abs(after.width - before.width) / before.width if before.width else math.inf,
               abs(after.height - before.height) / before.height if before.height else math.inf)


def snap_report(report: Report, grid: int, max_resize: float | None = None) -> SnapResult:
    """Snap every eligible visual in place and report what was skipped and why.

    ``max_resize``: when snapping would change a visual's width or height by more than this
    fraction, the visual is left alone with a warning (coarse grids badly distort small
    visuals; refusing beats surprising). ``None`` disables the limit.
    """
    result = SnapResult()
    for page in report.pages:
        _snap_page(page, grid, max_resize, result)
    return result


def _eligible(page: Page, v: Visual, result: SnapResult) -> bool:
    where = f"{page.display_name} / {v.name}"
    if v.ignored:
        return False
    if v.is_group or v.parent_group:
        # Open question in schema.md: are grouped visuals positioned relative to the group?
        result.warnings.append(f"{where}: skipped (grouped visuals are not supported yet)")
        return False
    return True


def _snap_page(page: Page, grid: int, max_resize: float | None, result: SnapResult) -> None:
    if page.width is None or page.height is None:
        result.warnings.append(
            f"{page.display_name}: skipped (no fixed page size; displayOption "
            f"{page.display_option})"
        )
        return
    before = {v.name: v.rect for v in page.visuals}
    snapped: set[str] = set()
    for v in page.visuals:
        if not _eligible(page, v, result):
            continue
        new = snap_rect(v.rect, grid, page.width, page.height)
        ratio = resize_ratio(v.rect, new)
        if max_resize is not None and ratio > max_resize:
            result.warnings.append(
                f"{page.display_name} / {v.name}: skipped (snapping would resize it "
                f"{_size(v.rect)} -> {_size(new)}, {ratio:.0%} > grid.max_resize {max_resize:.0%})"
            )
            continue
        if new != v.rect:
            v.rect = new
            result.moved.append((page.name, v.name))
        snapped.add(v.name)

    # Warn (never fix) when snapping creates an overlap that didn't exist before. Snapping
    # to the nearest line keeps edge order, so this only happens via the one-cell minimum.
    for i, a in enumerate(page.visuals):
        for b in page.visuals[i + 1:]:
            if a.name not in snapped and b.name not in snapped:
                continue
            if _overlaps(a.rect, b.rect) and not _overlaps(before[a.name], before[b.name]):
                result.warnings.append(
                    f"{page.display_name}: snapping made {a.name} and {b.name} overlap"
                )
