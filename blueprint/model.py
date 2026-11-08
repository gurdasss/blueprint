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
    ignored: bool = False  # `blueprint: ignore` escape hatch
    source: Any = field(default=None, repr=False, compare=False)


@dataclass
class Page:
    name: str
    display_name: str
    width: float | None  # None when displayOption is DeprecatedDynamic
    height: float | None
    display_option: str
    visuals: list[Visual] = field(default_factory=list)
    source: Any = field(default=None, repr=False, compare=False)


@dataclass
class Report:
    root: Path
    pages: list[Page]
    active_page: str | None
    # e.g. {"visualContainer": ["2.14.0 (validated as 2.13.0)"]}
    schema_versions: dict[str, list[str]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    source: Any = field(default=None, repr=False, compare=False)

    def page(self, name: str) -> Page:
        for p in self.pages:
            if p.name == name:
                return p
        raise KeyError(name)
