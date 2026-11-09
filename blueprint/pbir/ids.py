"""Object names for new pages, visuals and filters.

Desktop names new objects with 20 lowercase hex characters (probe 04: pages, visuals and
filters alike). Blueprint uses the same format, but **derives** each name from what the object
is (a hash of a stable key) rather than drawing it at random. The same spec plus the same
report therefore always produces the same names, which keeps output byte-identical
(README design principle 1).

Desktop accepts these derived names for new objects and keeps them on save (probe 05, README Q4).
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable

from blueprint.pbir.reader import NAME_RE

LENGTH = 20


def derive(*parts: str) -> str:
    """20 lowercase hex characters from the key parts. Deterministic and collision-resistant."""
    digest = hashlib.sha256("\x1f".join(("blueprint", *parts)).encode("utf-8")).hexdigest()
    return digest[:LENGTH]


def unique(parts: Iterable[str], taken: set[str]) -> str:
    """``derive(*parts)``, or a deterministic variant if that name is already taken."""
    parts = tuple(parts)
    name = derive(*parts)
    n = 1
    while name in taken:
        name = derive(*parts, f"#{n}")
        n += 1
    assert NAME_RE.match(name)
    return name


def page_id(page_name: str, taken: set[str]) -> str:
    return unique(("page", page_name), taken)


def visual_id(page: str, spec_id: str, taken: set[str]) -> str:
    return unique(("visual", page, spec_id), taken)


def filter_id(visual: str, field: str, taken: set[str]) -> str:
    return unique(("filter", visual, field), taken)
