"""Format-agnostic, in-memory view of a report.

Nothing in here knows about PBIR files. ``blueprint.pbir.reader`` builds these objects;
everything above ``pbir/`` works only with them. ``source`` fields are opaque handles
owned by ``pbir/`` (used later by the writer to patch the original documents in place).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Rect:
    x: float
    y: float
    width: float
    height: float

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def bottom(self) -> float:
        return self.y + self.height


@dataclass(frozen=True)
class ColorUse:
    """One colour set somewhere in a visual or page."""

    where: str  # readable location, e.g. "dataPoint.fill", "title.fontColor", "text"
    kind: str  # "hex" | "theme" (a reference into the theme) | "expression" (e.g. conditional)
    value: str | None = None  # "#E15759" (uppercase) for hex; a description otherwise


@dataclass(frozen=True)
class FontUse:
    """Font settings written for one text role of a visual. None = not written (theme/default)."""

    role: str  # "title" | "subtitle" | "callout" | "textbox"
    family: str | None = None  # the face, e.g. "Segoe UI Semibold" (first entry of a font stack)
    size: float | None = None  # pt
    bold: bool | None = None
    raw_family: str | None = None  # as stored, for messages


@dataclass(frozen=True)
class TextClass:
    font: str | None = None
    size: float | None = None


@dataclass(frozen=True)
class Theme:
    name: str
    layer: str  # "base" | "custom"; custom overrides base
    missing: bool  # referenced, but its file couldn't be found
    # Built-in (SharedResources) themes may be referenced without an embedded file; Desktop
    # loads them from its own install (probe 03 phase 2). Custom themes must be embedded.
    builtin: bool = False
    data_colors: tuple[str, ...] = ()  # uppercase hex
    foreground: str | None = None
    background: str | None = None
    text_classes: dict[str, TextClass] = field(default_factory=dict)  # title, label, callout, …


@dataclass
class Visual:
    name: str
    visual_type: str | None  # None for a group container
    rect: Rect
    z: float | None = None
    title: str | None = None
    is_group: bool = False
    parent_group: str | None = None
    hidden: bool = False
    bound: bool = False  # has at least one field projection (measure/column)
    ignored: bool = False  # `blueprint: ignore` escape hatch
    spec_id: str | None = None  # set when Blueprint created it: the spec visual id it came from
    colors: list[ColorUse] = field(default_factory=list)
    fonts: list[FontUse] = field(default_factory=list)
    source: Any = field(default=None, repr=False, compare=False)


@dataclass
class Page:
    name: str
    display_name: str
    width: float | None  # None when displayOption is DeprecatedDynamic
    height: float | None
    display_option: str
    visuals: list[Visual] = field(default_factory=list)
    spec_page: str | None = None  # set when Blueprint created it: the spec `page:` it came from
    colors: list[ColorUse] = field(default_factory=list)
    source: Any = field(default=None, repr=False, compare=False)


@dataclass
class Report:
    root: Path
    pages: list[Page]
    active_page: str | None
    # e.g. {"visualContainer": ["2.14.0 (validated as 2.13.0)"]}
    schema_versions: dict[str, list[str]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    themes: list[Theme] = field(default_factory=list)  # in layer order: base, then custom
    source: Any = field(default=None, repr=False, compare=False)

    def page(self, name: str) -> Page:
        for p in self.pages:
            if p.name == name:
                return p
        raise KeyError(name)
