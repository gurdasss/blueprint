"""Read and write JSON exactly the way Power BI Desktop does.

Observed in Desktop's PBIR output (see schema.md, "File encoding"):

- UTF-8, no BOM; CRLF line endings; no trailing newline after the closing brace.
- Two-space indent, ``"key": value``; empty containers are written as ``{}`` / ``[]``.
- Non-ASCII characters are written raw, not ``\\uXXXX``-escaped.
- Floats are written by .NET and do not always match Python's shortest ``repr``
  (``9.7990430622009566`` vs ``9.799043062200957``).

Because of the last point, numbers are parsed into :class:`RawFloat`, which remembers
its source text, and are written back verbatim unless the value was replaced. That is
what makes a load/dump round trip byte-identical, so a file Blueprint touches only
changes where Blueprint changed it.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Self

NEWLINE = "\r\n"
INDENT = "  "


class RawFloat(float):
    """A float that remembers the exact text it was parsed from."""

    raw: str

    def __new__(cls, text: str) -> Self:
        obj = super().__new__(cls, text)
        obj.raw = text
        return obj


class DuplicateKeyError(ValueError):
    pass


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in pairs:
        if k in out:
            raise DuplicateKeyError(f"duplicate key {k!r}")
        out[k] = v
    return out


def loads(text: str) -> Any:
    return json.loads(text, parse_float=RawFloat, object_pairs_hook=_pairs)


def load(path: Path) -> Any:
    data = path.read_bytes()
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    return loads(data.decode("utf-8"))


def _number(value: float) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, RawFloat):
        return value.raw
    if not math.isfinite(value):
        raise ValueError(f"cannot serialise non-finite float {value!r}")
    if value.is_integer():
        return str(int(value))
    return repr(value)


def _encode(value: Any, depth: int, out: list[str]) -> None:
    if value is None:
        out.append("null")
    elif isinstance(value, bool):
        out.append("true" if value else "false")
    elif isinstance(value, (int, float)):
        out.append(_number(value))
    elif isinstance(value, str):
        out.append(json.dumps(value, ensure_ascii=False))
    elif isinstance(value, dict):
        if not value:
            out.append("{}")
            return
        pad = NEWLINE + INDENT * (depth + 1)
        out.append("{")
        for i, (k, v) in enumerate(value.items()):
            if not isinstance(k, str):
                raise TypeError(f"JSON object keys must be str, got {type(k).__name__}")
            out.append(("," if i else "") + pad + json.dumps(k, ensure_ascii=False) + ": ")
            _encode(v, depth + 1, out)
        out.append(NEWLINE + INDENT * depth + "}")
    elif isinstance(value, (list, tuple)):
        if not value:
            out.append("[]")
            return
        pad = NEWLINE + INDENT * (depth + 1)
        out.append("[")
        for i, v in enumerate(value):
            out.append(("," if i else "") + pad)
            _encode(v, depth + 1, out)
        out.append(NEWLINE + INDENT * depth + "]")
    else:
        raise TypeError(f"cannot serialise {type(value).__name__}")


def dumps(value: Any) -> str:
    out: list[str] = []
    _encode(value, 0, out)
    return "".join(out)


def dump_bytes(value: Any) -> bytes:
    return dumps(value).encode("utf-8")
