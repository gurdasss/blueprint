"""Named policies: behaviour that branches, implemented in code and selected by name in config.

Guidelines files never contain conditionals (README design principle 5). When a rule needs
branching, it lives here as a named function, and config picks one by name.
"""

from __future__ import annotations

from collections.abc import Callable

from blueprint.model import Page, Visual

DensityPolicy = Callable[[Page], list[Visual]]


def _containers(page: Page) -> list[Visual]:
    return [v for v in page.visuals if not v.is_group]


def density_all(page: Page) -> list[Visual]:
    """Every visual container except groups."""
    return _containers(page)


def density_visible(page: Page) -> list[Visual]:
    """Containers that aren't hidden. Hidden visuals usually belong to bookmark states."""
    return [v for v in _containers(page) if not v.hidden]


def density_data(page: Page) -> list[Visual]:
    """Visible containers bound to fields; textboxes, images and shapes don't count."""
    return [v for v in density_visible(page) if v.bound]


DENSITY: dict[str, DensityPolicy] = {
    "all": density_all,
    "visible": density_visible,
    "data": density_data,
}
