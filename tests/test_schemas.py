from pathlib import Path

from blueprint.pbir import schemas
from blueprint.pbir.reader import read_report
from tests.builders import S, make_report, visual


def ref(url: str) -> schemas.SchemaRef:
    r = schemas.parse_url(url)
    assert r is not None
    return r


def test_parse_url():
    r = ref(f"{S}/visualContainer/2.14.0/schema.json")
    assert (r.name, r.version) == ("visualContainer", (2, 14, 0))
    assert schemas.parse_url("https://example.com/x/1.0.0/schema.json") is None


def test_resolve_newer_minor_falls_back_to_newest_vendored_same_major():
    res = schemas.resolve(ref(f"{S}/visualContainer/2.99.0/schema.json"))
    assert res.used is not None and res.used.version[0] == 2 and not res.exact


def test_resolve_unknown_major():
    assert schemas.resolve(ref(f"{S}/visualContainer/9.0.0/schema.json")).used is None


def test_valid_and_invalid_visual(tmp_path: Path):
    res = schemas.resolve(ref(f"{S}/visualContainer/2.13.0/schema.json"))
    assert schemas.validate(visual("v1"), res) == []
    bad = visual("v1", notAProperty=1)
    bad["name"] = "x" * 51
    errors = schemas.validate(bad, res)
    assert any("notAProperty" in e for e in errors)
    assert any(e.startswith("name:") for e in errors)


def test_builder_output_is_schema_valid(tmp_path: Path):
    r = read_report(make_report(tmp_path, {"p": [visual("v1")]}))
    for doc in r.source.documents.values():
        if doc.schema is not None:
            assert schemas.validate(doc.data, doc.schema) == [], doc.path


def test_sample_report_is_schema_valid(retail_report: Path):
    r = read_report(retail_report)
    for doc in r.source.documents.values():
        if doc.schema is not None:
            assert schemas.validate(doc.data, doc.schema) == [], doc.path
