"""Malformed or unusual inputs must give a clear error (exit 2) or a warning, never a crash,
and must never cause Blueprint to overwrite what it can't read. Found by a fuzz audit."""

import os
import shutil
from pathlib import Path

import pytest

from blueprint.cli import main
from blueprint.pbir import jsonfmt

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "examples" / "sales-overview.yaml"
GUIDE = ROOT / "guidelines" / "example.yaml"
CARD = "Fixture.Report/definition/pages/6a692d13619c1d4c0146/visuals/c62803c0b4a8a11ac705/visual.json"
PAGE = "Fixture.Report/definition/pages/6a692d13619c1d4c0146/page.json"
REPORT = "Fixture.Report/definition/report.json"
THEME = "Fixture.Report/StaticResources/SharedResources/BaseThemes/Fluent2-CY26SU10.json"
TMDL = "Fixture.SemanticModel/definition/tables/Sales.tmdl"


def raw(rel, data: bytes):
    return lambda d: (d / rel).write_bytes(data)


def edit(rel, fn):
    def go(d):
        (d / rel).write_bytes(jsonfmt.dump_bytes(fn(jsonfmt.load(d / rel))))
    return go


def pos(**kw):
    return edit(CARD, lambda v: {**v, "position": {**v["position"], **kw}})


CASES = {
    "visual.json is a list": raw(CARD, b"[1, 2]"),
    "visual.json invalid JSON": raw(CARD, b"{oops"),
    "visual.json UTF-16": raw(CARD, '{"name": "x"}'.encode("utf-16")),
    "position is a string": edit(CARD, lambda v: {**v, "position": "top-left"}),
    "x is a string": pos(x="10"),
    "x is null": pos(x=None),
    "negative width": pos(width=-50),
    "annotations not a list": edit(CARD, lambda v: {**v, "annotations": {"a": 1}}),
    "page.json is a list": raw(PAGE, b"[]"),
    "page width is a string": edit(PAGE, lambda p: {**p, "width": "wide"}),
    "report.json is a list": raw(REPORT, b"[]"),
    "theme textClasses malformed": edit(THEME, lambda t: {**t, "textClasses": {"title": "big"}, "visualStyles": {"*": "x"}}),
    "theme file is a list": raw(THEME, b"[]"),
    "definition.pbir is a list": raw("Fixture.Report/definition.pbir", b"[]"),
    "TMDL not UTF-8": raw(TMDL, b"table Sales\n\tmeasure \xff\xfe = 1\n"),
}
COMMANDS = {
    "check": lambda r: ["check", "--report", str(r), "--guidelines", str(GUIDE)],
    "fmt": lambda r: ["fmt", "--report", str(r)],
    "apply": lambda r: ["apply", str(SPEC), "--report", str(r), "--guidelines", str(GUIDE)],
    "manifest": lambda r: ["manifest", "--report", str(r)],
}


@pytest.fixture
def proj(tmp_path: Path) -> Path:
    shutil.copytree(ROOT / "fixtures" / "02-card-and-chart", tmp_path / "proj")
    return tmp_path / "proj"


@pytest.mark.parametrize("case", CASES)
def test_no_crash(proj: Path, case: str, capsys):
    CASES[case](proj)
    for cmd, args in COMMANDS.items():
        assert main(args(proj)) in (0, 1, 2), (case, cmd)  # any exception fails the test
    capsys.readouterr()


@pytest.mark.parametrize("bad", [None, "10", -50])
def test_unreadable_position_is_never_overwritten(proj: Path, bad, capsys):
    key = "width" if bad == -50 else "x"
    pos(**{key: bad})(proj)
    before = (proj / CARD).read_bytes()
    for args in (COMMANDS["fmt"], COMMANDS["apply"], COMMANDS["manifest"]):
        main(args(proj))
    assert (proj / CARD).read_bytes() == before
    out = capsys.readouterr()
    assert "left out of layout" in out.out + out.err


def test_malformed_visual_is_skipped_and_others_processed(proj: Path, capsys):
    raw(CARD, b"[1, 2]")(proj)
    assert main(["fmt", "--report", str(proj)]) == 0
    out = capsys.readouterr().out
    assert "expected a JSON object, got list; skipped" in out
    assert "ca909884eb63347a3230" in out  # the healthy chart was still snapped


def test_report_level_file_broken_is_a_clear_error(proj: Path, capsys):
    raw(REPORT, b"[]")(proj)
    assert main(["inspect", "--report", str(proj)]) == 2
    assert "definition/report.json: expected a JSON object, got list" in capsys.readouterr().err


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores permissions")
def test_read_only_report_fails_cleanly_without_leftovers(proj: Path, capsys):
    dirs = sorted((p for p in (proj / "Fixture.Report").rglob("*") if p.is_dir()), reverse=True)
    for d in [*dirs, proj / "Fixture.Report"]:
        os.chmod(d, 0o555)
    try:
        assert main(["fmt", "--report", str(proj)]) == 2
        assert "nothing was changed" in capsys.readouterr().err
        assert not list(proj.rglob("*.bp-tmp"))
    finally:
        for d in [proj / "Fixture.Report", *dirs]:
            os.chmod(d, 0o755)


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores permissions")
def test_unreadable_file_is_a_clear_error_or_skip(proj: Path, capsys):
    os.chmod(proj / CARD, 0)
    try:
        assert main(["check", "--report", str(proj)]) == 1
        assert "can't read: Permission denied; skipped" in capsys.readouterr().out
    finally:
        os.chmod(proj / CARD, 0o644)


# --- text encodings of the YAML Blueprint reads (specs, guidelines) -------------------------------
# Windows PowerShell 5 writes UTF-16 with a BOM by default (`>`, Out-File), and Notepad can add a
# UTF-8 BOM, so an agent on Windows produces both. They once crashed with a UnicodeDecodeError.

SPEC_TEXT = ("page: Encoded\nlayout: two-up\nvisuals:\n  - {type: header, title: Encoded é}\n"
             "  - {type: card, slots: {value: '[Total Amount]'}}\n"
             "  - {type: column, slots: {category: 'Sales[Country]', value: '[Total Amount]'}}\n")


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig", "utf-16", "utf-16-le-crlf"])
def test_specs_and_guidelines_in_windows_encodings(card_chart_fixture, tmp_path, capsys, encoding):
    proj = tmp_path / "proj"
    shutil.copytree(card_chart_fixture.parent, proj)
    codec, crlf = (encoding.removesuffix("-crlf"), encoding.endswith("-crlf"))

    def encode(text: str) -> bytes:
        text = text.replace("\n", "\r\n") if crlf else text
        data = text.encode("utf-16-le" if codec == "utf-16-le" else codec)
        return (b"\xff\xfe" + data) if codec == "utf-16-le" else data

    spec = tmp_path / "encoded.yaml"
    spec.write_bytes(encode(SPEC_TEXT))
    guide = tmp_path / "g.yaml"
    guide.write_bytes(encode(GUIDE.read_text(encoding="utf-8").replace(
        'search_path: ["layouts"]', f"search_path: ['{GUIDE.parent / 'layouts'}']")))
    assert main(["apply", str(spec), "--report", str(proj), "--guidelines", str(guide)]) == 0
    assert "new page 'Encoded'" in capsys.readouterr().out


def test_undecodable_spec_is_a_clear_error(card_chart_fixture, tmp_path, capsys):
    proj = tmp_path / "proj"
    shutil.copytree(card_chart_fixture.parent, proj)
    spec = tmp_path / "bad.yaml"
    spec.write_bytes(b"page: X\xff\xfe\x80\n")
    assert main(["apply", str(spec), "--report", str(proj), "--guidelines", str(GUIDE)]) == 2
    assert "bad.yaml" in capsys.readouterr().err


def test_spec_keys_that_are_numbers_or_null(card_chart_fixture, tmp_path, capsys):
    """YAML mapping keys can be numbers or null; listing unknown keys once crashed sorting them."""
    proj = tmp_path / "proj"
    shutil.copytree(card_chart_fixture.parent, proj)
    spec = tmp_path / "keys.yaml"
    spec.write_text("page: K\nlayout: two-up\n1: x\nnull: y\nvisuals:\n"
                    "  - {type: header, title: K, 2: a, null: b, zz: c}\n", encoding="utf-8")
    assert main(["apply", str(spec), "--report", str(proj), "--guidelines", str(GUIDE)]) == 2
    err = capsys.readouterr().err
    assert "1: unknown key" in err and "None: unknown key" in err and "visuals[0].zz: unknown key" in err
