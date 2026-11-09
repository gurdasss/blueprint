"""The page registry: ``definition/pages/pages.json``.

Verified in probe 04 (schema.md "Creating pages and visuals"): adding a page appends its name
to ``pageOrder``, and deleting a page removes it. Order lives only in ``pageOrder``; folder
names never imply it. A page folder without a ``pageOrder`` entry is not what Desktop writes,
so the registry must change together with the folder.

``activePageName`` is UI state (Desktop sets it to whatever page was on screen at save time),
so Blueprint never writes it.

These functions return new documents and never mutate their input, so a Plan can hold both the
before and the after.
"""

from __future__ import annotations

from typing import Any


class RegistryError(Exception):
    pass


def _order(doc: Any) -> list[str]:
    if not isinstance(doc, dict):
        raise RegistryError("pages.json must be a JSON object")
    order = doc.get("pageOrder", [])
    if not isinstance(order, list) or not all(isinstance(n, str) for n in order):
        raise RegistryError("pages.json pageOrder must be a list of page names")
    return list(order)


def with_page(doc: Any, name: str, *, before: str | None = None) -> dict:
    """``doc`` with ``name`` in ``pageOrder``: appended (as Desktop does) or inserted before
    ``before``. Already present: unchanged (idempotent)."""
    order = _order(doc)
    if name in order:
        return dict(doc)
    if before is None:
        order.append(name)
    elif before in order:
        order.insert(order.index(before), name)
    else:
        raise RegistryError(f"pages.json: no page {before!r} to insert before")
    return {**doc, "pageOrder": order}


def without_page(doc: Any, name: str) -> dict:
    order = _order(doc)
    if name not in order:
        raise RegistryError(f"pages.json: page {name!r} is not in pageOrder")
    return {**doc, "pageOrder": [n for n in order if n != name]}
