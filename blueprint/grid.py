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


def snap_rect(rect: Rect, grid: int, page_w: float, page_h: float) -> Rect:
    left, top = _nearest(rect.x, grid), _nearest(rect.y, grid)
    right, bottom = _nearest(rect.right, grid), _nearest(rect.bottom, grid)
    # Snapping must not push an edge that was on the page off it.
    if right > page_w and rect.right <= page_w:
        right = math.floor(page_w / grid) * grid
    if bottom > page_h and rect.bottom <= page_h:
        bottom = math.floor(page_h / grid) * grid
    # A visual never collapses below one grid cell.
    right = max(right, left + grid)
    bottom = max(bottom, top + grid)
    return Rect(left, top, right - left, bottom - top)


def _overlaps(a: Rect, b: Rect) -> bool:
    return a.x < b.right and b.x < a.right and a.y < b.bottom and b.y < a.bottom


def snap_report(report: Report, grid: int) -> SnapResult:
    """Snap every eligible visual in place and report what was skipped and why."""
    result = SnapResult()
    for page in report.pages:
        _snap_page(page, grid, result)
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


def _snap_page(page: Page, grid: int, result: SnapResult) -> None:
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
