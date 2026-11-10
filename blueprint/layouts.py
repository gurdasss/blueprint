"""Named layouts (data, not code) and placing a page spec's visuals into their regions.

A layout is ``<search path>/<name>.yaml``:

    name: standard-4-up
    canvas: { width: 1280, height: 720 }
    regions:
      - { role: header, x: 16, y: 16, w: 1248, h: 64 }
      - { role: main,   x: 16, y: 232, w: 616, h: 472 }

Visuals fill regions **in declaration order**: each takes the next unused region whose role
matches the visual's role: its spec's ``region:`` if it has one, else its type's region (from
its slot contract). Running out of regions is an error, never a
reflow. ``blueprint: ignore`` visuals take no region. A region left with no visual leaves a gap
on the page; ``bp apply`` warns and names layouts that fit (:func:`unused`), but never stretches
other regions into it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from blueprint.model import Rect
from blueprint.slots import contracts
from blueprint.spec import PageSpec, VisualSpec


class LayoutError(Exception):
    pass


@dataclass(frozen=True)
class Region:
    role: str
    rect: Rect
    key: str = ""  # "<role>#<n>": the n-th region of that role, in declaration order


@dataclass(frozen=True)
class Layout:
    name: str
    width: int
    height: int
    regions: tuple[Region, ...]
    source: str = ""


@dataclass(frozen=True)
class Placement:
    visual: VisualSpec
    region: Region


def find(name: str, search_path: tuple[Path, ...]) -> Path:
    for directory in search_path:
        candidate = directory / f"{name}.yaml"
        if candidate.is_file():
            return candidate
    if not search_path:
        raise LayoutError(f"layout {name!r} not found: layouts.search_path is empty. Layouts are files "
                          "your guidelines point to (layouts: {search_path: [<folder>]}); the repository "
                          "ships some in guidelines/layouts/, which guidelines/example.yaml uses")
    raise LayoutError(f"layout {name!r} not found in {', '.join(str(d) for d in search_path)}")


def available(search_path: tuple[Path, ...]) -> list[str]:
    """Names of the layouts on the search path, sorted. A name found in several directories is
    listed once (the first one wins, as in :func:`find`)."""
    return sorted({p.stem for d in search_path if d.is_dir() for p in d.glob("*.yaml")})


def load(name: str, search_path: tuple[Path, ...]) -> Layout:
    path = find(name, search_path)
    try:
        data = yaml.safe_load(path.read_bytes())  # bytes: PyYAML detects UTF-8, BOM and UTF-16
    except (OSError, yaml.YAMLError) as exc:
        raise LayoutError(f"{path}: {exc}") from exc
    return parse(data, str(path), expected_name=name)


def _num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def parse(data: Any, source: str = "<layout>", expected_name: str | None = None) -> Layout:
    problems: list[str] = []
    if not isinstance(data, dict):
        raise LayoutError(f"{source}: top level must be a mapping with name, canvas and regions")
    name = data.get("name")
    if not isinstance(name, str) or (expected_name is not None and name != expected_name):
        problems.append(f"name: must be {expected_name!r} (the file name)" if expected_name
                        else "name: required")
    canvas = data.get("canvas")
    canvas = canvas if isinstance(canvas, dict) else {}
    width, height = canvas.get("width"), canvas.get("height")
    if not (isinstance(width, int) and isinstance(height, int) and width > 0 and height > 0):
        problems.append("canvas: needs integer width and height > 0")
        width = height = 0
    regions: list[Region] = []
    per_role: dict[str, int] = {}
    raw_regions = data.get("regions")
    if not isinstance(raw_regions, list) or not raw_regions:
        problems.append("regions: required, a non-empty list")
        raw_regions = []
    for i, r in enumerate(raw_regions):
        at = f"regions[{i}]"
        if not isinstance(r, dict) or not isinstance(r.get("role"), str):
            problems.append(f"{at}: needs a role and x, y, w, h")
            continue
        if not all(_num(r.get(k)) for k in ("x", "y", "w", "h")) or r["w"] <= 0 or r["h"] <= 0:
            problems.append(f"{at}: x, y, w, h must be numbers, with w and h > 0")
            continue
        rect = Rect(r["x"], r["y"], r["w"], r["h"])
        if width and (rect.x < 0 or rect.y < 0 or rect.right > width or rect.bottom > height):
            problems.append(f"{at} ({r['role']}): extends outside the {width}x{height} canvas")
        per_role[r["role"]] = per_role.get(r["role"], 0) + 1
        regions.append(Region(r["role"], rect, f"{r['role']}#{per_role[r['role']]}"))
    if problems:
        raise LayoutError(f"{source}: {len(problems)} problem(s)\n  " + "\n  ".join(problems))
    return Layout(name, width, height, tuple(regions), source)


def conflicts(layout: Layout, grid: int, margin: int, gutter: int = 0) -> list[str]:
    """Ways ``layout`` breaks the guidelines it's used with. A region off the grid or inside the
    margin would make `bp apply` and `bp fmt` undo each other forever (behaviour audit); regions
    closer than the gutter would build pages `bp check` flags."""
    from blueprint.grid import EPS, off_grid_edges  # local: grid imports model only, no cycle
    from blueprint.validate import gutter_gap

    problems = []
    for r in layout.regions:
        off = off_grid_edges(r.rect, grid, layout.width, layout.height)
        if off:
            problems.append(f"region {r.key} is off the {grid}px grid ("
                            + ", ".join(f"{k}={v:g}" for k, v in off.items()) + ")")
        if margin:
            near = [k for k, d in (("left", r.rect.x), ("top", r.rect.y),
                                   ("right", layout.width - r.rect.right),
                                   ("bottom", layout.height - r.rect.bottom)) if d < margin]
            if near:
                problems.append(f"region {r.key} is inside the {margin}px margin ({', '.join(near)})")
    if gutter:
        for i, a in enumerate(layout.regions):
            for b in layout.regions[i + 1:]:
                gap = gutter_gap(a.rect, b.rect)
                if gap is not None and gap < gutter - EPS:
                    problems.append(f"regions {a.key} and {b.key} are {gap:g}px apart, "
                                    f"less than the {gutter}px gutter")
    return problems


def place(spec: PageSpec, layout: Layout, visual_dirs: tuple[Path, ...] = ()) -> list[Placement]:
    """Assign each non-ignored visual the next free region of its role, in spec order."""
    known = contracts(visual_dirs)
    free = list(layout.regions)
    placements: list[Placement] = []
    problems: list[str] = []
    roles = sorted({r.role for r in layout.regions})
    for v in spec.visuals:
        if v.ignore:
            continue
        role = v.region or known[v.type].region
        region = next((r for r in free if r.role == role), None)
        if region is None and v.region and role not in roles:
            problems.append(f"visuals[{v.index}].region: layout {layout.name!r} has no {role!r} "
                            f"region (it has {', '.join(roles)})")
            continue
        if region is None:
            total = sum(r.role == role for r in layout.regions)
            problems.append(f"visuals[{v.index}] ({v.type}): no free {role!r} region left in layout "
                            f"{layout.name!r} (it has {total}); remove a visual, choose another "
                            "layout, or mark it blueprint: ignore")
            continue
        free.remove(region)
        placements.append(Placement(v, region))
    if problems:
        raise LayoutError(f"{spec.source}: " + "\n  ".join(problems))
    return placements


def unused(layout: Layout, placements: list[Placement]) -> list[Region]:
    """Regions no visual was placed in, in declaration order: each is a gap on the page."""
    taken = {p.region.key for p in placements}
    return [r for r in layout.regions if r.key not in taken]
