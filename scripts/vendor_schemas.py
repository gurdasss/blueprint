"""Vendor Microsoft's PBIR JSON schemas (and every schema they $ref) into the package.

Usage:
    python scripts/vendor_schemas.py <schema-url-or-path> [...]

Each argument is either a full $schema URL as it appears in a report file, or a path
relative to the json-schemas `fabric/` root, e.g.
    item/report/definition/visualContainer/2.14.0/schema.json

Files are written to blueprint/pbir/schemas/<same relative path>. Relative $refs to
other schema files are followed transitively. Already-vendored files are skipped, so
the script is safe to re-run.

Source: https://github.com/microsoft/json-schemas (MIT licensed).
"""

from __future__ import annotations

import json
import posixpath
import sys
import time
import urllib.request
from pathlib import Path

RAW_ROOT = "https://raw.githubusercontent.com/microsoft/json-schemas/main/fabric/"
PUBLIC_ROOT = "https://developer.microsoft.com/json-schemas/fabric/"
DEST = Path(__file__).resolve().parent.parent / "blueprint" / "pbir" / "schemas"


def to_rel(arg: str) -> str:
    for root in (PUBLIC_ROOT, RAW_ROOT):
        if arg.startswith(root):
            return arg[len(root):]
    return arg.lstrip("/")


def fetch(rel: str, attempts: int = 3) -> bytes:
    url = RAW_ROOT + rel
    for i in range(attempts):
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                return resp.read()
        except Exception as exc:
            if i == attempts - 1:
                raise RuntimeError(f"failed to fetch {url}: {exc}") from exc
            time.sleep(2 * (i + 1))
    raise AssertionError("unreachable")


def file_refs(node: object) -> set[str]:
    """Collect the file part of every relative $ref in a schema document."""
    out: set[str] = set()
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str) and not ref.startswith("#"):
            target = ref.split("#", 1)[0]
            if target and "://" not in target:
                out.add(target)
        for v in node.values():
            out |= file_refs(v)
    elif isinstance(node, list):
        for v in node:
            out |= file_refs(v)
    return out


def vendor(start: list[str]) -> None:
    queue = [to_rel(a) for a in start]
    seen: set[str] = set()
    while queue:
        rel = posixpath.normpath(queue.pop())
        if rel in seen:
            continue
        seen.add(rel)
        dest = DEST / rel
        if dest.exists():
            data = dest.read_bytes()
            status = "have"
        else:
            data = fetch(rel)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            status = "got "
        print(f"{status} {rel}")
        base = posixpath.dirname(rel)
        for ref in file_refs(json.loads(data)):
            queue.append(posixpath.join(base, ref))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    vendor(sys.argv[1:])
