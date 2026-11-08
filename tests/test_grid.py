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


def test_snap_rect_keeps_right_edge_on_non_multiple_page():
    assert snap_rect(Rect(0, 0, 1275, 8), 8, 1278, 720).right == 1272


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
