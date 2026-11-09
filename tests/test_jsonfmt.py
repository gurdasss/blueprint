from pathlib import Path

import pytest

from blueprint.pbir import jsonfmt


def test_round_trip_is_byte_identical_on_desktop_output(real_report: Path):
    files = sorted(real_report.rglob("*.json")) + sorted(real_report.glob("*.pbir"))
    files = [f for f in files if ".pbi" not in f.parts]
    assert files
    mismatched = [
        str(f.relative_to(real_report))
        for f in files
        if jsonfmt.dump_bytes(jsonfmt.load(f)) != f.read_bytes()
    ]
    assert not mismatched


def test_format_rules():
    doc = {"a": 1, "b": [], "c": {}, "d": [1.5, "é"], "e": None, "f": True}
    assert jsonfmt.dumps(doc) == (
        '{\r\n  "a": 1,\r\n  "b": [],\r\n  "c": {},\r\n'
        '  "d": [\r\n    1.5,\r\n    "é"\r\n  ],\r\n  "e": null,\r\n  "f": true\r\n}'
    )


def test_raw_floats_preserved_and_replaced_floats_reformatted():
    doc = jsonfmt.loads('{"x": 9.7990430622009566, "y": 1.0}')
    assert jsonfmt.dumps(doc) == '{\r\n  "x": 9.7990430622009566,\r\n  "y": 1.0\r\n}'
    doc["x"] = 16.0
    doc["y"] = 2.25
    assert jsonfmt.dumps(doc) == '{\r\n  "x": 16,\r\n  "y": 2.25\r\n}'


def test_duplicate_keys_rejected():
    with pytest.raises(jsonfmt.DuplicateKeyError):
        jsonfmt.loads('{"a": 1, "a": 2}')
