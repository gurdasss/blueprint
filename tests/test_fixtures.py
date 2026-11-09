"""The committed fixtures are genuine Desktop output: everything Blueprint does must hold on them."""

import json
import shutil
from pathlib import Path

from blueprint.cli import main
from blueprint.pbir import jsonfmt, schemas
from blueprint.pbir.reader import read_report


def _snapshot(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def test_blank_report(blank_fixture: Path):
    r = read_report(blank_fixture)
    [page] = r.pages
    assert (page.display_name, page.width, page.height, page.visuals) == ("Page 1", 1920, 1080, [])
    assert len(page.name) == 20 and int(page.name, 16) >= 0  # Desktop's 20-hex ids
    assert [(t.layer, t.name, t.missing) for t in r.themes] == [("base", "Fluent2-CY26SU10", False)]
    assert r.warnings == []


def test_card_and_chart(card_chart_fixture: Path):
    r = read_report(card_chart_fixture)
    [page] = r.pages
    kinds = {v.visual_type: v for v in page.visuals}
    assert set(kinds) == {"cardVisual", "clusteredColumnChart"}
    assert kinds["cardVisual"].title == "Total" and kinds["cardVisual"].bound
    assert kinds["clusteredColumnChart"].bound


def test_every_file_round_trips_and_validates(blank_fixture: Path, card_chart_fixture: Path):
    for rd in (blank_fixture, card_chart_fixture):
        r = read_report(rd)
        for doc in r.source.documents.values():
            assert jsonfmt.dump_bytes(doc.data) == doc.raw, doc.path
        assert schemas.validate_documents(r.source.documents.values()) == []
        for f in rd.parent.rglob("*.json"):  # also theme, model and project files
            raw = f.read_bytes()
            assert jsonfmt.dump_bytes(jsonfmt.loads_bytes(raw)) == raw, f


def test_fmt_idempotent_and_valid_on_fixture(card_chart_fixture: Path, tmp_path: Path, capsys):
    copy = tmp_path / "02" / card_chart_fixture.name
    shutil.copytree(card_chart_fixture.parent, copy.parent)
    original = _snapshot(copy)
    assert main(["fmt", "--report", str(copy)]) == 0
    once = _snapshot(copy)
    assert main(["fmt", "--report", str(copy)]) == 0
    assert "No changes." in capsys.readouterr().out
    assert _snapshot(copy) == once != original
    assert all(k.endswith("visual.json") for k in original if original[k] != once[k])
    main(["check", "--report", str(copy), "--json"])
    out = json.loads(capsys.readouterr().out)
    assert [f for f in out["findings"] if f["rule"] in ("grid", "format", "bounds")] == []


def test_fixtures_are_never_modified_by_tests(blank_fixture: Path, card_chart_fixture: Path):
    # Guard: these are evidence. Run read-only commands only against the committed folders.
    for rd in (blank_fixture, card_chart_fixture):
        before = _snapshot(rd.parent)
        assert main(["check", "--report", str(rd)]) in (0, 1)
        assert main(["fmt", "--report", str(rd), "--dry-run"]) == 0
        assert _snapshot(rd.parent) == before
