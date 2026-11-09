from pathlib import Path

import pytest

from blueprint.pbir import ids, jsonfmt, registry
from blueprint.pbir.reader import NAME_RE

# --- ids -------------------------------------------------------------------------------------


def test_ids_have_desktop_format_and_are_deterministic():
    a = ids.page_id("Sales Overview", set())
    assert len(a) == 20 and a == a.lower() and int(a, 16) >= 0 and NAME_RE.match(a)
    assert ids.page_id("Sales Overview", set()) == a  # same input, same name: byte-identical output
    assert ids.page_id("Sales overview", set()) != a


def test_ids_distinguish_object_kinds_and_scopes():
    names = {ids.page_id("x", set()), ids.visual_id("p", "x", set()), ids.visual_id("q", "x", set()),
             ids.filter_id("v", "x", set())}
    assert len(names) == 4


def test_collision_gets_a_deterministic_variant():
    first = ids.visual_id("p", "card-1", set())
    second = ids.visual_id("p", "card-1", {first})
    assert second != first and NAME_RE.match(second)
    assert ids.visual_id("p", "card-1", {first}) == second


def test_ids_never_clash_with_desktop_names_in_fixture(card_chart_fixture: Path):
    existing = {p.name for p in (card_chart_fixture / "definition/pages").iterdir() if p.is_dir()}
    assert ids.page_id("Overview", existing) not in existing


# --- registry --------------------------------------------------------------------------------

DOC = {"$schema": "x", "pageOrder": ["a", "b"], "activePageName": "b"}


def test_with_page_appends_like_desktop_and_keeps_active_page():
    out = registry.with_page(DOC, "c")
    assert out == {"$schema": "x", "pageOrder": ["a", "b", "c"], "activePageName": "b"}
    assert DOC["pageOrder"] == ["a", "b"]  # input not mutated
    assert list(out) == list(DOC)  # key order kept, so the diff is one line


def test_with_page_before_and_idempotent():
    assert registry.with_page(DOC, "c", before="a")["pageOrder"] == ["c", "a", "b"]
    assert registry.with_page(DOC, "a") == DOC
    with pytest.raises(registry.RegistryError, match="no page 'z'"):
        registry.with_page(DOC, "c", before="z")


def test_without_page():
    assert registry.without_page(DOC, "a")["pageOrder"] == ["b"]
    with pytest.raises(registry.RegistryError, match="not in pageOrder"):
        registry.without_page(DOC, "z")


def test_registry_rejects_malformed():
    with pytest.raises(registry.RegistryError):
        registry.with_page({"pageOrder": "a"}, "b")


def test_adding_a_page_to_fixture_registry_matches_desktops_diff_shape(blank_fixture: Path):
    path = blank_fixture / "definition/pages/pages.json"
    before = path.read_bytes()
    after = jsonfmt.dump_bytes(registry.with_page(jsonfmt.loads_bytes(before), "d2d26a9c77ea0c92c187"))
    # Probe 04 step 02 (without the activePageName change, which Blueprint never makes):
    assert after.decode().split("\r\n") == [
        "{",
        '  "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json",',
        '  "pageOrder": [',
        '    "6a692d13619c1d4c0146",',
        '    "d2d26a9c77ea0c92c187"',
        "  ],",
        '  "activePageName": "6a692d13619c1d4c0146"',
        "}",
    ]
