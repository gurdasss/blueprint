"""Report folder on disk -> :mod:`blueprint.model`.

Reading is lenient: anything surprising becomes a warning on the returned Report rather
than an exception, so ``bp inspect`` works on reports Blueprint can't (yet) write to.
Only things that make the folder unreadable raise :class:`ReportFormatError`.

Facts this module relies on are recorded, with evidence, in ``schema.md``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from blueprint.model import Page, Rect, Report, Theme, Visual
from blueprint.pbir import formatting, jsonfmt, schemas

# Microsoft Learn: object/folder names "must consist of one or more word characters
# (letters, digits, underscores) or hyphens"; Desktop silently ignores anything else.
# The page and visualContainer schemas cap `name` at 50 characters.
NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,50}$")

# Desktop ignores `annotations`, so Blueprint's own markers live there.
IGNORE_ANNOTATION = "blueprint.ignore"

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
        raw = (self.dir / rel).read_bytes()
        try:
            data = jsonfmt.loads_bytes(raw)
        except ValueError as exc:
            raise ReportFormatError(f"{rel}: invalid JSON: {exc}") from exc
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
        doc = self.load_required(rel_dir / "page.json")
        if doc is None:
            return None
        d = doc.data
        if d.get("name") != rel_dir.name:
            self.warnings.append(f"{rel_dir}: page name {d.get('name')!r} differs from folder")
        page = Page(
            name=rel_dir.name,
            display_name=d.get("displayName", ""),
            width=d.get("width"),
            height=d.get("height"),
            display_option=d.get("displayOption", ""),
            colors=formatting.colors_in(d),
            source=doc,
        )
        for folder in self.subdirs(rel_dir / "visuals"):
            vrel = rel_dir / "visuals" / folder
            if not NAME_RE.match(folder):
                self.warnings.append(f"{vrel}: invalid folder name; Desktop ignores it")
                continue
            vdoc = self.load_required(vrel / "visual.json")
            if vdoc is not None:
                page.visuals.append(self.read_visual(vdoc, folder))
        return page

    def read_visual(self, doc: Document, folder: str) -> Visual:
        d = doc.data
        if d.get("name") != folder:
            self.warnings.append(f"{doc.path}: visual name {d.get('name')!r} differs from folder")
        pos = d.get("position", {})
        visual = d.get("visual") or {}
        notes = {a.get("name"): a.get("value") for a in d.get("annotations", []) if isinstance(a, dict)}
        return Visual(
            name=folder,
            visual_type=visual.get("visualType"),
            rect=Rect(pos.get("x", 0), pos.get("y", 0), pos.get("width", 0), pos.get("height", 0)),
            z=pos.get("z"),
            title=_title(visual),
            is_group="visualGroup" in d,
            parent_group=d.get("parentGroupName"),
            hidden=bool(d.get("isHidden", False)),
            bound=_bound(visual),
            ignored=str(notes.get(IGNORE_ANNOTATION, "")).lower() == "true",
            colors=formatting.colors_in(visual),
            source=doc,
        )


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
