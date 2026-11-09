from pathlib import Path

import pytest

from blueprint.grid import snap_rect, snap_report
from blueprint.model import Rect
from blueprint.pbir.reader import IGNORE_ANNOTATION, read_report
from tests.builders import make_report, visual, write


@pytest.mark.parametrize(
    ("rect", "expected"),
    [
        (Rect(9.8, 4.9, 1268.98, 714.11), Rect(8, 8, 1272, 712)),   # edges snap independently
        (Rect(16, 16, 100, 100), Rect(16, 16, 104, 104)),  # 116 rounds up to 120
        (Rect(4, 4, 8, 8), Rect(8, 8, 8, 8)),                         # .5 rounds up, not to even
        (Rect(10, 10, 2, 2), Rect(8, 8, 8, 8)),                       # never below one cell
        (Rect(1270, 0, 9, 8), Rect(1272, 0, 8, 8)),                   # on page: kept on page
    ],
)
def test_snap_rect(rect, expected):
    assert snap_rect(rect, 8, 1280, 720) == expected


def test_page_edge_is_a_snap_line_on_non_multiple_page():
    assert snap_rect(Rect(0, 0, 1276, 8), 8, 1278, 720).right == 1278  # page edge nearer than 1272
    assert snap_rect(Rect(0, 0, 1273, 8), 8, 1278, 720).right == 1272
    # 720 is not a multiple of 7: a visual sitting on the bottom edge stays on it.
    assert snap_rect(Rect(0, 451, 280, 269), 7, 1280, 720).bottom == 720


def test_growing_to_one_cell_never_pushes_off_page():
    # Sample regression: 24.5px textbox at the page bottom, grid 32 and 64.
    for g in (32, 64):
        r = snap_rect(Rect(1151.39, 694.51, 126.16, 24.5), g, 1280, 720)
        # Grows upward instead; the top stays on the grid (720 isn't a multiple of 32).
        assert r.bottom == 720 and r.y % g == 0 and g <= r.height < 2 * g


def test_already_off_page_is_snapped_not_clamped():
    assert snap_rect(Rect(0, 700, 8, 30), 8, 1280, 720).bottom == 728


def test_snap_invariants_randomised():
    import random

    rng = random.Random(1234)
    for _ in range(5000):
        g = rng.choice([1, 2, 4, 5, 7, 8, 10, 12, 16, 20, 32, 64])
        pw, ph = rng.choice([(1280, 720), (1278, 719), (1920, 1080), (816, 1056)])
        x, y = rng.uniform(0, pw - 1), rng.uniform(0, ph - 1)
        w, h = rng.uniform(0.5, pw - x), rng.uniform(0.5, ph - y)
        r = Rect(x, y, w, h)
        s = snap_rect(r, g, pw, ph)
        assert snap_rect(s, g, pw, ph) == s, (r, g)  # idempotent
        assert s.width >= min(g, pw) and s.height >= min(g, ph), (r, g)
        assert s.x >= 0 and s.y >= 0 and s.right <= pw and s.bottom <= ph, (r, g, s)


def test_snap_is_idempotent_on_rects():
    r = snap_rect(Rect(123.4, 56.7, 89.1, 23.4), 8, 1280, 720)
    assert snap_rect(r, 8, 1280, 720) == r


def test_snap_report_skips_ignored_grouped_and_dynamic(tmp_path: Path):
    rd = make_report(tmp_path, {
        "p": [
            visual("keep", 3, 3, 50, 50, annotations=[{"name": IGNORE_ANNOTATION, "value": "true"}]),
            visual("child", 3, 3, 50, 50, parentGroupName="grp"),
            visual("moves", 3, 3, 50, 50),
        ],
        "dyn": [visual("d", 3, 3, 50, 50)],
    })
    page = rd / "definition/pages/dyn/page.json"
    write(page, {"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json",
                 "name": "dyn", "displayName": "Dyn", "displayOption": "DeprecatedDynamic"})
    r = read_report(rd)
    result = snap_report(r, 8)
    assert result.moved == [("p", "moves")]
    p = r.page("p")
    assert [v.rect.x for v in p.visuals] == [3, 3, 0]
    assert r.page("dyn").visuals[0].rect.x == 3
    joined = "\n".join(result.warnings)
    assert "child: skipped (grouped" in joined
    assert "Dyn: skipped (no fixed page size" in joined
    assert "keep" not in joined  # ignore is silent: it was asked for


def test_warns_when_snapping_creates_overlap(tmp_path: Path):
    # Nearest-line snapping is monotonic, so only the one-cell minimum can create overlaps.
    r = read_report(make_report(tmp_path, {"p": [visual("a", 0, 0, 2, 8), visual("b", 3, 0, 8, 8)]}))
    result = snap_report(r, 8)
    assert any("a and b overlap" in w for w in result.warnings)
