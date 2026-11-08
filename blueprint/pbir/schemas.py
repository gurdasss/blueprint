"""Validate PBIR documents against Microsoft's vendored JSON schemas.

Every PBIR file declares its schema, e.g.
``https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.14.0/schema.json``.
Copies of the schemas live under ``schemas/`` (fetched with ``scripts/vendor_schemas.py``).

Desktop can write a minor version the public repo hasn't published yet (the sample report
declares visualContainer 2.14.0 while 2.13.0 is the newest published). So resolution picks
the closest vendored version with the same *major* version, and says whether it was an
exact match. A different major version is unknown, and the caller decides what to do.
Each schema pins its own URL as a ``const`` on ``$schema``, so a non-exact validation
substitutes the vendored URL before checking.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT7

PUBLIC_ROOT = "https://developer.microsoft.com/json-schemas/fabric/"
SCHEMA_DIR = Path(__file__).resolve().parent / "schemas"

_URL = re.compile(
    re.escape(PUBLIC_ROOT) + r"(?P<kind>[\w/]+?)/(?P<ver>\d+\.\d+\.\d+)/(?P<file>schema[\w.-]*\.json)$"
)

Version = tuple[int, int, int]


@dataclass(frozen=True)
class SchemaRef:
    kind: str  # e.g. "item/report/definition/visualContainer"
    version: Version
    file: str = "schema.json"

    @property
    def name(self) -> str:
        return self.kind.rsplit("/", 1)[-1]

    @property
    def url(self) -> str:
        return f"{PUBLIC_ROOT}{self.kind}/{fmt_version(self.version)}/{self.file}"

    @property
    def path(self) -> Path:
        return SCHEMA_DIR / self.kind / fmt_version(self.version) / self.file


@dataclass(frozen=True)
class Resolution:
    declared: SchemaRef
    used: SchemaRef | None  # None: no vendored schema with the same major version

    @property
    def exact(self) -> bool:
        return self.used == self.declared


def fmt_version(v: Version) -> str:
    return ".".join(map(str, v))


def parse_url(url: str) -> SchemaRef | None:
    m = _URL.match(url)
    if not m:
        return None
    major, minor, patch = (int(p) for p in m["ver"].split("."))
    return SchemaRef(m["kind"], (major, minor, patch), m["file"])


def vendored_versions(kind: str) -> list[Version]:
    base = SCHEMA_DIR / kind
    if not base.is_dir():
        return []
    out = []
    for d in base.iterdir():
        parts = d.name.split(".")
        if d.is_dir() and len(parts) == 3 and all(p.isdigit() for p in parts):
            out.append((int(parts[0]), int(parts[1]), int(parts[2])))
    return sorted(out)


def resolve(ref: SchemaRef) -> Resolution:
    same_major = [v for v in vendored_versions(ref.kind) if v[0] == ref.version[0]]
    if not same_major:
        return Resolution(ref, None)
    if ref.version in same_major:
        chosen = ref.version
    else:
        older = [v for v in same_major if v <= ref.version]
        chosen = older[-1] if older else same_major[0]
    return Resolution(ref, SchemaRef(ref.kind, chosen, ref.file))


def _local_path_for(uri: str) -> Path:
    if not uri.startswith(PUBLIC_ROOT):
        raise LookupError(f"refusing to resolve non-Fabric schema reference {uri!r}")
    rel = uri[len(PUBLIC_ROOT):].split("#", 1)[0]
    path = SCHEMA_DIR / rel
    if not path.exists():
        # Upstream quirk: files named schema-embedded.json declare $id schema.embedded.json.
        alt = SCHEMA_DIR / rel.replace("schema.embedded.json", "schema-embedded.json")
        if alt.exists():
            return alt
        raise LookupError(f"schema not vendored: {rel} (run scripts/vendor_schemas.py)")
    return path


def _retrieve(uri: str) -> Resource:
    contents = json.loads(_local_path_for(uri).read_text(encoding="utf-8"))
    return Resource.from_contents(contents, default_specification=DRAFT7)


@cache
def _validator(ref: SchemaRef) -> Draft7Validator:
    schema = json.loads(ref.path.read_text(encoding="utf-8"))
    # Resolve relative $refs against the file's URL, not its $id, so the
    # schema-embedded/schema.embedded naming quirk can't send lookups astray.
    schema = {**schema, "$id": ref.url}
    registry: Registry = Registry(retrieve=_retrieve)  # type: ignore[call-arg]
    return Draft7Validator(schema, registry=registry)


def validate(doc: Any, resolution: Resolution) -> list[str]:
    """Return human-readable schema errors for ``doc`` (empty list when valid)."""
    if resolution.used is None:
        raise LookupError(f"no vendored schema for {resolution.declared.url}")
    if not resolution.exact and isinstance(doc, dict) and "$schema" in doc:
        doc = {**doc, "$schema": resolution.used.url}
    errors = sorted(_validator(resolution.used).iter_errors(doc), key=lambda e: list(e.path))
    return [f"{'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message}" for e in errors]
