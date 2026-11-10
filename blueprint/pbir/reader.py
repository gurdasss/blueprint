"""Report folder on disk -> :mod:`blueprint.model`.

Reading is lenient: anything surprising becomes a warning on the returned Report rather
than an exception, so ``bp inspect`` works on reports Blueprint can't (yet) write to.
Only things that make the folder unreadable raise :class:`ReportFormatError`.

Facts this module relies on are recorded, with evidence, in ``schema.md``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from blueprint.model import Field, Page, Rect, Report, Theme, Visual
from blueprint.pbir import formatting, jsonfmt, schemas

# Microsoft Learn: object/folder names "must consist of one or more word characters
# (letters, digits, underscores) or hyphens"; Desktop silently ignores anything else.
# The page and visualContainer schemas cap `name` at 50 characters.
NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,50}$")

# Desktop ignores `annotations` and keeps them across saves (probe 01), so Blueprint's own
# markers live there.
IGNORE_ANNOTATION = "blueprint.ignore"
PAGE_ANNOTATION = "blueprint.page"  # on a page Blueprint created: the spec's `page:` name
SPEC_ANNOTATION = "blueprint.spec"  # on a Blueprint page: id of the spec that builds it
VISUAL_ANNOTATION = "blueprint.visual"  # on a visual Blueprint created: the spec visual id
LAYOUT_ANNOTATION = "blueprint.layout"  # on a Blueprint page: layout name used by bp apply
GUIDELINES_ANNOTATION = "blueprint.guidelines"  # on a Blueprint page: "<name>@<version>"
REGION_ANNOTATION = "blueprint.region"  # on a Blueprint visual: "<role>#<n>" (n-th region of role)
# on a Blueprint visual: fingerprint of the bindings bp apply last wrote (render.bindings_fingerprint),
# so a re-run can tell a spec change (rebind) from an edit made in Desktop (refuse)
BINDINGS_ANNOTATION = "blueprint.bindings"


def annotations(doc: dict) -> dict[str, str]:
    notes = doc.get("annotations", [])
    return {a["name"]: a.get("value") for a in (notes if isinstance(notes, list) else [])
            if isinstance(a, dict) and isinstance(a.get("name"), str)}


def _number(v):
    """A JSON number (not a bool), else None."""
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None

PAGES = Path("definition/pages")


class ReportFormatError(Exception):
    pass


@dataclass
class Document:
    """One parsed JSON file, kept verbatim so the writer can patch it in place."""

    path: Path  # relative to the .Report folder
    data: Any
    schema: schemas.Resolution | None
    raw: bytes = b""  # file contents as read; the writer refuses to overwrite if they changed


@dataclass
class ReportSource:
    report_dir: Path
    documents: dict[Path, Document] = field(default_factory=dict)


def find_report_dir(path: Path) -> Path:
    """Accept a ``*.Report`` folder, a ``*.pbip`` file, or a folder holding exactly one ``*.Report``."""
    path = path.resolve()
    if path.is_file() and path.suffix == ".pbip":
        doc = jsonfmt.load(path)
        try:
            rel = doc["artifacts"][0]["report"]["path"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ReportFormatError(f"{path}: no artifacts[0].report.path") from exc
        path = (path.parent / rel).resolve()
    if path.is_dir() and not (path / "definition.pbir").exists():
        candidates = sorted(p for p in path.glob("*.Report") if p.is_dir())
        if len(candidates) == 1:
            path = candidates[0]
        elif len(candidates) > 1:
            names = ", ".join(c.name for c in candidates)
            raise ReportFormatError(f"{path}: several reports found ({names}); pass one")
    if not (path / "definition.pbir").is_file():
        raise ReportFormatError(f"{path}: not a PBIP report folder (no definition.pbir)")
    return path


def read_report(path: Path) -> Report:
    return _Reader(find_report_dir(path)).read()


class _Reader:
    def __init__(self, report_dir: Path) -> None:
        self.dir = report_dir
        self.src = ReportSource(report_dir)
        self.warnings: list[str] = []
        self.versions: dict[str, set[str]] = {}

    # -- files ---------------------------------------------------------------

    def exists(self, rel: Path) -> bool:
        return (self.dir / rel).is_file()

    def subdirs(self, rel: Path) -> list[str]:
        full = self.dir / rel
        return sorted(p.name for p in full.iterdir() if p.is_dir()) if full.is_dir() else []

    def load(self, rel: Path) -> Document:
        try:
            raw = (self.dir / rel).read_bytes()
        except OSError as exc:
            raise ReportFormatError(f"{rel}: can't read: {exc.strerror or exc}") from exc
        try:
            data = jsonfmt.loads_bytes(raw)
        except ValueError as exc:  # includes UnicodeDecodeError
            raise ReportFormatError(f"{rel}: invalid JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise ReportFormatError(f"{rel}: expected a JSON object, got {type(data).__name__}")
        res = None
        url = data.get("$schema") if isinstance(data, dict) else None
        ref = schemas.parse_url(url) if isinstance(url, str) else None
        if ref is not None:
            res = schemas.resolve(ref)
            label = schemas.fmt_version(ref.version)
            if res.used is None:
                label += " (unknown major version)"
                self.warnings.append(f"{rel}: unknown schema {url}")
            elif not res.exact:
                label += f" (validated as {schemas.fmt_version(res.used.version)})"
            self.versions.setdefault(ref.name, set()).add(label)
        elif url is not None:
            self.warnings.append(f"{rel}: unrecognised $schema {url!r}")
        doc = Document(rel, data, res, raw)
        self.src.documents[rel] = doc
        return doc

    def load_required(self, rel: Path) -> Document | None:
        if not self.exists(rel):
            self.warnings.append(f"{rel}: missing (required)")
            return None
        return self.load(rel)

    def load_part(self, rel: Path) -> Document | None:
        """A page or visual document: unreadable or malformed ones become a warning and are
        skipped (so nothing touches them), rather than making the whole report unreadable."""
        try:
            return self.load_required(rel)
        except ReportFormatError as exc:
            self.warnings.append(f"{exc}; skipped")
            return None

    # -- report --------------------------------------------------------------

    def read(self) -> Report:
        pbir = self.load(Path("definition.pbir")).data
        legacy = str(pbir.get("version")) == "1.0" or not (self.dir / "definition").is_dir()
        if legacy:
            raise ReportFormatError(
                f"{self.dir.name}: report is in PBIR-Legacy format (single report.json). "
                "Blueprint only supports PBIR (a definition/ folder). Open and save it in a "
                "recent Power BI Desktop to convert."
            )
        if not self.exists(Path("definition/version.json")):
            raise ReportFormatError(f"{self.dir.name}: definition/version.json missing")
        self.load(Path("definition/version.json"))
        report_doc = self.load_required(Path("definition/report.json"))
        themes = self.read_themes(report_doc.data) if report_doc is not None else []

        order: list[str] = []
        active: str | None = None
        if self.exists(PAGES / "pages.json"):
            meta = self.load(PAGES / "pages.json").data
            order = list(meta.get("pageOrder", []))
            active = meta.get("activePageName")

        pages: dict[str, Page] = {}
        for folder in self.subdirs(PAGES):
            if not NAME_RE.match(folder):
                self.warnings.append(f"{PAGES / folder}: invalid folder name; Desktop ignores it")
                continue
            page = self.read_page(PAGES / folder)
            if page is not None:
                pages[folder] = page

        ordered: list[Page] = []
        for name in order:
            if name in pages:
                ordered.append(pages.pop(name))
            else:
                self.warnings.append(f"pages.json: pageOrder lists {name!r}, which has no folder")
        if pages:
            if order:
                missing = ", ".join(sorted(pages))
                self.warnings.append(f"pages.json: pages missing from pageOrder: {missing}")
            ordered.extend(pages[k] for k in sorted(pages))
        if active is not None and active not in {p.name for p in ordered}:
            self.warnings.append(f"pages.json: activePageName {active!r} is not a page")

        return Report(
            root=self.dir,
            pages=ordered,
            active_page=active,
            schema_versions={k: sorted(v) for k, v in sorted(self.versions.items())},
            warnings=self.warnings,
            themes=themes,
            source=self.src,
        )

    def read_themes(self, report_doc: dict) -> list[Theme]:
        themes = []
        for layer, name, ptype, rel in formatting.theme_refs(report_doc):
            builtin = ptype == formatting.BUILTIN_THEME_TYPE
            if rel is None or not self.exists(rel):
                themes.append(Theme(name, layer, missing=True, builtin=builtin))
                continue
            try:
                data = self.load(rel).data
            except ReportFormatError as exc:
                self.warnings.append(f"{rel}: theme file unreadable: {exc}")
                themes.append(Theme(name, layer, missing=True, builtin=builtin))
                continue
            themes.append(formatting.theme_from(layer, name, data, builtin))
        return themes

    def read_page(self, rel_dir: Path) -> Page | None:
        doc = self.load_part(rel_dir / "page.json")
        if doc is None:
            return None
        d = doc.data
        if d.get("name") != rel_dir.name:
            self.warnings.append(f"{rel_dir}: page name {d.get('name')!r} differs from folder")
        page = Page(
            name=rel_dir.name,
            display_name=d.get("displayName", ""),
            width=self.size(d, "width", rel_dir),
            height=self.size(d, "height", rel_dir),
            display_option=d.get("displayOption", ""),
            spec_page=annotations(d).get(PAGE_ANNOTATION),
            spec=annotations(d).get(SPEC_ANNOTATION),
            layout=annotations(d).get(LAYOUT_ANNOTATION),
            guidelines=annotations(d).get(GUIDELINES_ANNOTATION),
            colors=formatting.colors_in(d),
            source=doc,
        )
        for folder in self.subdirs(rel_dir / "visuals"):
            vrel = rel_dir / "visuals" / folder
            if not NAME_RE.match(folder):
                self.warnings.append(f"{vrel}: invalid folder name; Desktop ignores it")
                continue
            vdoc = self.load_part(vrel / "visual.json")
            if vdoc is not None:
                page.visuals.append(self.read_visual(vdoc, folder))
        return page

    def size(self, d: dict, key: str, rel_dir: Path):
        v = d.get(key)
        if v is None:
            return None
        n = _number(v)
        if n is None or n <= 0:
            self.warnings.append(f"{rel_dir}/page.json: {key} {v!r} is not a positive number; "
                                 "the page is treated as having no fixed size")
            return None
        return n

    def read_visual(self, doc: Document, folder: str) -> Visual:
        d = doc.data
        if d.get("name") != folder:
            self.warnings.append(f"{doc.path}: visual name {d.get('name')!r} differs from folder")
        pos = d.get("position")
        pos = pos if isinstance(pos, dict) else {}
        coords = {k: _number(pos.get(k)) for k in ("x", "y", "width", "height")}
        bad = [k for k, v in coords.items() if v is None or (k in ("width", "height") and v < 0)]
        if bad:
            self.warnings.append(f"{doc.path}: position {', '.join(bad)} missing or not a valid "
                                 "number; the visual is left out of layout")
        visual = d.get("visual")
        visual = visual if isinstance(visual, dict) else {}
        notes = annotations(d) if isinstance(d.get("annotations", []), list) else {}
        return Visual(
            name=folder,
            visual_type=visual.get("visualType"),
            rect=Rect(*(coords[k] if k not in bad else 0 for k in ("x", "y", "width", "height"))),
            positioned=not bad,
            z=pos.get("z"),
            title=_title(visual),
            text=_textbox_text(visual) if visual.get("visualType") == "textbox" else None,
            is_group="visualGroup" in d,
            parent_group=d.get("parentGroupName"),
            hidden=bool(d.get("isHidden", False)),
            bound=_bound(visual),
            ignored=str(notes.get(IGNORE_ANNOTATION, "")).lower() == "true",
            spec_id=notes.get(VISUAL_ANNOTATION),
            region=notes.get(REGION_ANNOTATION),
            bindings_mark=notes.get(BINDINGS_ANNOTATION),
            fields=_fields(visual),
            colors=formatting.colors_in(visual),
            fonts=formatting.fonts_in(visual),
            source=doc,
        )


# Aggregation "Function" codes, as Desktop names them. Probe 29 took each one from Desktop's own
# output on a fresh field: the codes don't follow the menu order, and the UI's "Count" is 5 while
# "Count (Distinct)" is 2. An unknown code is still shown by number rather than guessed.
AGGREGATE_FUNCTIONS = {0: "Sum", 1: "Average", 2: "DistinctCount", 3: "Min", 4: "Max", 5: "Count"}


def _field(f: dict) -> Field | None:
    """One projection's field: a measure or column (probe 04), or an implicit aggregate of a
    column (probe 10: ``{"Aggregation": {"Expression": {"Column": …}, "Function": 0}}``)."""
    for key, kind in (("Measure", "measure"), ("Column", "column")):
        if isinstance(f.get(key), dict):
            src = (f[key].get("Expression") or {}).get("SourceRef") or {}
            return Field(kind, src.get("Entity"), f[key].get("Property", ""))
    level = f.get("HierarchyLevel")
    if isinstance(level, dict):
        return _hierarchy_level(level)
    agg = f.get("Aggregation")
    if isinstance(agg, dict):
        inner = _field(agg.get("Expression") or {})
        code = agg.get("Function")
        if inner is not None and inner.kind == "column" and isinstance(code, int) and not isinstance(code, bool):
            return Field("aggregation", inner.table, inner.name, AGGREGATE_FUNCTIONS.get(code, f"Aggregate{code}"))
    return None


def _path(node: Any, *keys: str) -> Any:
    """``node[k1][k2]…``, or None as soon as a step isn't a dict holding that key."""
    for key in keys:
        node = node.get(key) if isinstance(node, dict) else None
    return node


def _hierarchy_level(level: dict) -> Field | None:
    """One level of a hierarchy, in either verified shape. ``Level`` is the level's name.

    - probe 13, a date column's automatic date hierarchy: ``{"Expression": {"Hierarchy":
      {"Expression": {"PropertyVariationSource": {"Expression": {"SourceRef": {"Entity": T}},
      "Name": "Variation", "Property": C}}, "Hierarchy": "Date Hierarchy"}}, "Level": L}``
      -> ``date_level`` (T, column C, L);
    - probe 16, a hierarchy built in the model: ``{"Expression": {"Hierarchy": {"Expression":
      {"SourceRef": {"Entity": T}}, "Hierarchy": H}}, "Level": L}`` -> ``hierarchy_level``
      (T, hierarchy H, L).
    """
    hier = _path(level, "Expression", "Hierarchy")
    lvl = level.get("Level")
    source = _path(hier, "Expression", "PropertyVariationSource")
    if source is not None:
        table, name, kind = _path(source, "Expression", "SourceRef", "Entity"), _path(source, "Property"), "date_level"
    else:
        table, name, kind = _path(hier, "Expression", "SourceRef", "Entity"), _path(hier, "Hierarchy"), "hierarchy_level"
    if all(isinstance(v, str) for v in (table, name, lvl)):
        return Field(kind, table, name, level=lvl)
    return None


def _fields(visual: dict) -> dict[str, list[Field]]:
    """Bound fields by query role, in projection order. Field shapes not listed in ``_field`` are skipped."""
    out: dict[str, list[Field]] = {}
    state = (visual.get("query") or {}).get("queryState") or {}
    for role, entry in state.items():
        for p in (entry or {}).get("projections") or [] if isinstance(entry, dict) else []:
            f = (p or {}).get("field")
            field = _field(f) if isinstance(f, dict) else None
            if field is not None:
                fmt = (p or {}).get("format")  # probe 29: a format string scoped to the visual
                if isinstance(fmt, str) and fmt:
                    field = replace(field, format=fmt)
                out.setdefault(role, []).append(field)
    return out


def _textbox_text(visual: dict) -> str | None:
    """Text of a textbox: runs joined, paragraphs separated by newlines (sample, probe 03 shapes)."""
    paragraphs = []
    for general in (visual.get("objects") or {}).get("general") or []:
        for para in ((general or {}).get("properties") or {}).get("paragraphs") or []:
            runs = (para or {}).get("textRuns") or []
            paragraphs.append("".join(str((r or {}).get("value", "")) for r in runs))
    return "\n".join(paragraphs) if paragraphs else None


def _bound(visual: dict) -> bool:
    """True when ``visual.query.queryState`` has at least one field projection."""
    state = (visual.get("query") or {}).get("queryState") or {}
    return any((role or {}).get("projections") for role in state.values() if isinstance(role, dict))


def _title(visual: dict) -> str | None:
    """Title text from ``visualContainerObjects.title``, when it is a plain string literal."""
    try:
        value = visual["visualContainerObjects"]["title"][0]["properties"]["text"]["expr"]["Literal"]["Value"]
    except (KeyError, IndexError, TypeError):
        return None
    if isinstance(value, str) and len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1].replace("''", "'")
    return None
