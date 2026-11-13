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

    role: str  # "title" | "subtitle" | "callout" | "card_label" | "textbox"
    family: str | None = None  # the face, e.g. "Segoe UI Semibold" (first entry of a font stack)
    size: float | None = None  # pt
    bold: bool | None = None
    raw_family: str | None = None  # as stored, for messages


@dataclass(frozen=True)
class TextClass:
    font: str | None = None
    size: float | None = None


@dataclass(frozen=True)
class Field:
    """A field a visual is bound to."""

    # "measure" | "column" | "aggregation" (an implicit aggregate of a column) | "date_level" (one
    # level of a date column's automatic date hierarchy; name is the column) | "hierarchy_level" (one
    # level of a hierarchy built in the model; name is the hierarchy)
    kind: str
    table: str | None
    name: str
    function: str | None = None  # aggregation only, e.g. "Sum"
    level: str | None = None  # date_level/hierarchy_level only, e.g. "Year", "Country"
    format: str | None = None  # the projection's format string scoped to the visual (probe 29)

    def __str__(self) -> str:
        # Spec/manifest syntax (README): [Measure], Table[Column]. Manifest only:
        # Sum(Table[Column]), Table[Column].Year (a date level) and Table[Hierarchy].Level
        if self.kind == "measure":
            return f"[{self.name}]"
        column = f"{self.table}[{self.name}]"
        if self.kind == "aggregation":
            return f"{self.function}({column})"
        return f"{column}.{self.level}" if self.kind in ("date_level", "hierarchy_level") else column


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
    sentiment: dict[str, str] = field(default_factory=dict)  # good / neutral / bad (probe 42)
    divergent: dict[str, str] = field(default_factory=dict)  # minimum / center / maximum (probe 44)
    text_classes: dict[str, TextClass] = field(default_factory=dict)  # title, label, callout, …
    # visualStyles defaults: "title"/"subTitle" from ["*"]["*"] (every visual) and "cardVisual.label"
    # from ["cardVisual"]["*"]. These outrank textClasses (probe 06: base theme title fontSize 15
    # beat textClasses.title 18; probe 07: the card label's 12 beat textClasses.label's 10.5).
    visual_text: dict[str, TextClass] = field(default_factory=dict)


@dataclass
class Visual:
    name: str
    visual_type: str | None  # None for a group container
    rect: Rect
    z: float | None = None
    title: str | None = None
    text: str | None = None  # a textbox's text (all runs of all paragraphs)
    is_group: bool = False
    parent_group: str | None = None
    hidden: bool = False
    bound: bool = False  # has at least one field projection (measure/column)
    ignored: bool = False  # `blueprint: ignore` escape hatch
    spec_id: str | None = None  # set when Blueprint created it: the spec visual id it came from
    region: str | None = None  # set by bp apply: the layout region it was placed in, e.g. "main#2"
    bindings_mark: str | None = None  # set by bp apply: fingerprint of the bindings it last wrote
    fields: dict[str, list[Field]] = field(default_factory=dict)  # query role -> bound fields
    colors: list[ColorUse] = field(default_factory=list)
    fonts: list[FontUse] = field(default_factory=list)
    # False when position is missing or not numeric: no layout step touches it (reported instead)
    positioned: bool = True
    source: Any = field(default=None, repr=False, compare=False)
    notes: list[str] = field(default_factory=list, repr=False, compare=False)  # what a command changed


@dataclass
class Page:
    name: str
    display_name: str
    width: float | None  # None when displayOption is DeprecatedDynamic
    height: float | None
    display_option: str
    visuals: list[Visual] = field(default_factory=list)
    spec_page: str | None = None  # set when Blueprint created it: the spec `page:` it came from
    spec: str | None = None  # set by bp apply: the id of the spec that builds this page
    layout: str | None = None  # set by bp apply: the layout it was built with
    guidelines: str | None = None  # set by bp apply: "<name>@<version>" it was built against
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
