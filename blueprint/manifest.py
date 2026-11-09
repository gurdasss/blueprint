"""The manifest: the handoff between the layout half of the stack and the semantic-model half.

It maps every page and visual to its type, title, position and field bindings, so an agent
doesn't have to re-derive the report's structure from PBIR on every turn (README "The manifest").
It is **generated, never hand-edited**, and is built only from the report's current state, so
``bp manifest`` can always rebuild it. What ``bp apply`` knew at build time (layout, region,
guidelines) is read back from the annotations it left on its pages and visuals.

``generated_at`` is the only non-deterministic field, and it changes only when the rest of the
manifest does, so regenerating an unchanged report is a no-op.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from typing import Any

from blueprint import __version__
from blueprint.guidelines import Guidelines
from blueprint.model import Field, Page, Report, Visual
from blueprint.slots import contracts

FILE = ".blueprint.manifest.json"  # in the .Report folder, next to .blueprint.yaml


def _num(v: float) -> int | float:
    r = round(float(v), 2)
    return int(r) if r.is_integer() else r


def _refs(fields: list[Field]) -> str | list[str]:
    refs = [str(f) for f in fields]
    return refs[0] if len(refs) == 1 else refs


def _visual(v: Visual) -> dict[str, Any]:
    by_visual_type = {c.visual_type: c for c in contracts().values()}
    contract = by_visual_type.get(v.visual_type or "") if v.spec_id else None
    role_to_slot = {s.role: name for name, s in contract.slots.items()} if contract else {}
    r = v.rect
    out: dict[str, Any] = {
        "id": v.name,
        "type": contract.type if contract else v.visual_type,
        "visual_type": v.visual_type,
        "title": v.text if contract is not None and contract.type == "header" else v.title,
        "managed": v.spec_id is not None,
    }
    if v.spec_id is not None:
        out["spec_id"] = v.spec_id
        out["region"] = v.region
    if v.ignored:
        out["ignored"] = True
    out["position"] = ({"x": _num(r.x), "y": _num(r.y), "w": _num(r.width), "h": _num(r.height)}
                       if v.positioned else None)
    out["slots"] = {role_to_slot.get(role, role): _refs(fs) for role, fs in v.fields.items()}
    return out


def _page(p: Page) -> dict[str, Any]:
    out: dict[str, Any] = {"id": p.name, "name": p.display_name}
    if p.spec_page is not None:
        out["spec"] = p.spec
        out["spec_page"] = p.spec_page
        out["layout"] = p.layout
        out["built_with"] = p.guidelines
    out["size"] = None if p.width is None else {"w": _num(p.width), "h": _num(p.height or 0)}
    visuals = sorted(p.visuals, key=lambda v: (v.rect.y, v.rect.x, v.name))
    out["visuals"] = [_visual(v) for v in visuals]
    return out


def build(report: Report, rules: Guidelines, generated_at: str) -> dict[str, Any]:
    return {
        "blueprint_version": __version__,
        "guidelines": {"name": rules.name, "version": rules.version},
        "pbir_schema": report.schema_versions,
        "generated_at": generated_at,
        "pages": [_page(p) for p in report.pages],
    }


def now() -> str:
    """UTC now, or $SOURCE_DATE_EPOCH (the reproducible-builds convention) when set."""
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    moment = datetime.fromtimestamp(int(epoch), UTC) if epoch else datetime.now(UTC)
    return moment.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def dumps(manifest: dict[str, Any]) -> bytes:
    return (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def render(report: Report, rules: Guidelines, previous: bytes | None) -> bytes:
    """The manifest file's bytes. Reuses ``previous``'s generated_at when nothing else changed."""
    fresh = build(report, rules, now())
    if previous is not None:
        try:
            old = json.loads(previous)
        except ValueError:
            old = None
        if isinstance(old, dict) and {**old, "generated_at": None} == {**fresh, "generated_at": None}:
            return dumps({**fresh, "generated_at": old.get("generated_at")})
    return dumps(fresh)
