from pathlib import Path

import pytest

from blueprint.pbir import jsonfmt
from blueprint.pbir.reader import IGNORE_ANNOTATION, ReportFormatError, read_report
from tests.builders import make_report, visual, write


def test_reads_pages_in_page_order(tmp_path: Path):
    rd = make_report(tmp_path, {"aaa": [], "bbb": [visual("v1", 8, 16, 200, 100)]},
                     order=["bbb", "aaa"])
    r = read_report(rd)
    assert [p.name for p in r.pages] == ["bbb", "aaa"]
    v = r.page("bbb").visuals[0]
    assert (v.name, v.visual_type, v.rect.x, v.rect.y, v.rect.right) == ("v1", "card", 8, 16, 208)
    assert r.warnings == []


def test_accepts_pbip_and_parent_folder(tmp_path: Path):
    rd = make_report(tmp_path, {"p": []})
    write(tmp_path / "Test.pbip", {"version": "1.0", "artifacts": [{"report": {"path": "Test.Report"}}]})
    assert read_report(tmp_path / "Test.pbip").root == rd
    assert read_report(tmp_path).root == rd


def test_title_and_ignore_annotation(tmp_path: Path):
    title = {"title": [{"properties": {"text": {"expr": {"Literal": {"Value": "'Bob''s sales'"}}}}}]}
    v = visual("v1", annotations=[{"name": IGNORE_ANNOTATION, "value": "true"}])
    v["visual"]["visualContainerObjects"] = title
    r = read_report(make_report(tmp_path, {"p": [v]}))
    got = r.page("p").visuals[0]
    assert got.title == "Bob's sales"
    assert got.ignored


def test_page_missing_from_order_and_bad_folder_names_warn(tmp_path: Path):
    rd = make_report(tmp_path, {"a": [], "b": []}, order=["a", "ghost"])
    (rd / "definition/pages/bad name").mkdir()
    r = read_report(rd)
    assert [p.name for p in r.pages] == ["a", "b"]
    joined = "\n".join(r.warnings)
    assert "'ghost'" in joined and "missing from pageOrder: b" in joined
    assert "bad name: invalid folder name" in joined


def test_legacy_format_refused(tmp_path: Path):
    rd = tmp_path / "Old.Report"
    write(rd / "definition.pbir", {"version": "1.0", "datasetReference": {}})
    write(rd / "report.json", {})
    with pytest.raises(ReportFormatError, match="PBIR-Legacy"):
        read_report(rd)


def test_not_a_report(tmp_path: Path):
    with pytest.raises(ReportFormatError, match="no definition.pbir"):
        read_report(tmp_path)


def test_sample_report(retail_report: Path):
    r = read_report(retail_report)
    assert [p.display_name for p in r.pages] == ["Info", "Overview", "District Monthly Sales", "New Stores"]
    assert sum(len(p.visuals) for p in r.pages) == 24
    assert r.schema_versions["visualContainer"] == ["2.14.0 (validated as 2.13.0)"]
    assert r.warnings == []
    assert r.page("ReportSection2").width is None  # DeprecatedDynamic page has no size
    # Every document parsed must round-trip byte-identically.
    for doc in r.source.documents.values():
        assert jsonfmt.dump_bytes(doc.data) == (r.root / doc.path).read_bytes(), doc.path
