"""In-memory model -> Plan -> report folder.

The writer never regenerates documents. It takes the parsed document the reader kept,
overwrites only the fields Blueprint owns, and re-serialises it with ``jsonfmt``. Because
``jsonfmt`` round-trips Desktop's output byte for byte, everything else in the file stays
exactly as it was.

Fields owned in existing visuals: ``position.x/y/width/height`` (``z`` and ``tabOrder`` are
kept) and the title text (only when the model sets one). ``add_modify`` and ``add_create`` let a
command patch other documents (e.g. the page registry) or create new ones.

Safety checks, all made before anything is written:
- a changed document must not gain schema errors; a created one must validate exactly;
- creating never overwrites: the target must not exist when the plan is made or applied;
- documents whose schema major version is unknown are refused unless ``force_schema``;
- ``apply`` refuses when a file on disk no longer matches what was read.
"""

from __future__ import annotations

import os
from pathlib import Path

from blueprint.model import Report, Visual
from blueprint.pbir import jsonfmt, render, schemas
from blueprint.pbir.reader import NAME_RE, Document, _title
from blueprint.plan import FileWrite, Plan


class WriteError(Exception):
    pass


def plan_writes(report: Report, *, force_schema: bool = False) -> Plan:
    plan = Plan(root=report.root)
    for page in report.pages:
        for visual in page.visuals:
            if visual.source is None:
                continue  # not on disk yet; created through add_create
            write = _visual_write(visual, force_schema=force_schema)
            if write is not None:
                plan.writes.append(write)
    return plan


_FIELDS = ("x", "y", "width", "height")


def _visual_write(visual: Visual, *, force_schema: bool) -> FileWrite | None:
    doc: Document = visual.source
    pos = doc.data.get("position", {})
    changes = []
    new_pos = dict(pos)
    for key in _FIELDS:
        new = getattr(visual.rect, key)
        old = pos.get(key)
        if old is None or float(old) != float(new):
            new_pos[key] = new
            changes.append(f"{key} {_fmt(old)} -> {_fmt(new)}")
    # doc.data may already carry in-memory edits (e.g. bp apply updating annotations); position
    # and title go on top, and the whole document becomes one write, so changes never collide.
    data = {**doc.data, "position": new_pos}
    current_title = _title(doc.data.get("visual") or {})
    if visual.title is not None and visual.title != current_title:
        data = render.with_title(data, visual.title)
        changes.append(f"title {current_title!r} -> {visual.title!r}")
    after = jsonfmt.dump_bytes(data)
    if after == doc.raw:
        return None
    _check_schema(doc, data, force_schema=force_schema)
    return FileWrite(doc.path, doc.raw, after,
                     (f"{visual.name}: " + (", ".join(changes) or "Blueprint annotations"),))


def add_modify(plan: Plan, doc: Document, data: dict, note: str, *, force_schema: bool = False) -> None:
    """Replace an existing document's content, subject to the same schema checks as visuals."""
    _check_schema(doc, data, force_schema=force_schema)
    after = jsonfmt.dump_bytes(data)
    if after != doc.raw:
        plan.writes.append(FileWrite(doc.path, doc.raw, after, (note,)))


def add_create(plan: Plan, rel: Path, data: dict, note: str) -> None:
    """Add a new document. It must declare a vendored schema and validate *exactly* (no older
    approximation), its folder names must be names Desktop accepts, and nothing may exist at
    ``rel`` already."""
    for part in rel.parent.parts[2:]:  # definition/pages/<page>/visuals/<visual>
        if part not in ("visuals",) and not NAME_RE.match(part):
            raise WriteError(f"{rel}: {part!r} is not a name Desktop accepts")
    if (plan.root / rel).exists() or any(w.path == rel for w in plan.writes):
        raise WriteError(f"{rel}: already exists; refusing to overwrite")
    ref = schemas.parse_url(data.get("$schema", "")) if isinstance(data.get("$schema"), str) else None
    res = schemas.resolve(ref) if ref else None
    if res is None or not res.exact:
        raise WriteError(f"{rel}: new documents must declare an exactly vendored schema")
    errors = schemas.validate(data, res)
    if errors:
        raise WriteError(f"{rel}: would create a schema-invalid file:\n  " + "\n  ".join(errors[:10]))
    plan.writes.append(FileWrite(rel, None, jsonfmt.dump_bytes(data), (note,)))


def _fmt(v: float | None) -> str:
    if v is None:
        return "-"
    v = float(v)
    return str(int(v)) if v.is_integer() else f"{v:.2f}"


def _check_schema(doc: Document, data: dict, *, force_schema: bool) -> None:
    res = doc.schema
    if res is None:
        return
    if res.used is None:
        if force_schema:
            return
        raise WriteError(
            f"{doc.path}: schema {res.declared.url} has an unknown major version; "
            "refusing to write (pass --force-schema to override)"
        )
    # Block only on errors this change introduces. A file can already fail validation without
    # being broken: Desktop writes schema versions before Microsoft publishes them, and a newer
    # minor version may add properties the nearest vendored schema doesn't know. Desktop accepts
    # those files, and refusing to touch them would stop Blueprint every time Desktop updates.
    # The baseline is the file as read from disk, not the in-memory document, so an in-memory
    # edit that breaks the schema is still caught.
    before = set(schemas.validate(jsonfmt.loads_bytes(doc.raw), res)) if doc.raw else set()
    introduced = [e for e in schemas.validate(data, res) if e not in before]
    if introduced:
        detail = "\n  ".join(introduced[:10])
        raise WriteError(f"{doc.path}: this change would introduce schema errors:\n  {detail}")


def apply(plan: Plan) -> None:
    """Write every file in the plan, or none if any precondition fails.

    Phase 1 checks that each target still matches what was read. Phase 2 writes every
    new file to a temp file beside its target. Phase 3 renames them all into place. A
    failure in phase 1 or 2 leaves the report untouched. A failure in phase 3 (rare: the
    rename is atomic per file) is reported with the files already replaced.
    """
    root = plan.root
    for w in plan.writes:
        target = root / w.path
        current = target.read_bytes() if target.exists() else None
        if current != w.before:
            raise WriteError(f"{w.path}: changed on disk since it was read; re-run the command")

    temps: list[tuple[Path, Path]] = []
    try:
        for w in plan.writes:
            target = root / w.path
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_name(f".{target.name}.bp-tmp")
            temps.append((tmp, target))
            with open(tmp, "wb") as fh:
                fh.write(w.after)
                fh.flush()
                os.fsync(fh.fileno())
            if target.exists():
                # Replacing a file must not change its permissions (or git sees a mode change).
                os.chmod(tmp, target.stat().st_mode & 0o7777)
    except BaseException:
        for tmp, _ in temps:
            tmp.unlink(missing_ok=True)
        raise

    done: list[Path] = []
    try:
        for tmp, target in temps:
            os.replace(tmp, target)
            done.append(target)
    except OSError as exc:
        for tmp, _ in temps:
            tmp.unlink(missing_ok=True)
        replaced = ", ".join(str(p.relative_to(root)) for p in done) or "none"
        raise WriteError(f"write interrupted after replacing: {replaced}: {exc}") from exc

