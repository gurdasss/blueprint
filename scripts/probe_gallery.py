"""Build the Desktop probe that looks for where the theme's structural keys paint (probe 48).

Usage:
    python scripts/probe_gallery.py <dest folder> <probe 46 folder>

Probe 46 found that of the nine structural keys it set, only `foregroundNeutralSecondary` (secondary
grey text) and `disabledText` (the Filters pane's left edge) changed anything on four existing
pages (cards, a KPI, charts, a table). Probe 48 asks where the other seven paint:
`foregroundNeutralTertiary` #9B30FF, `foregroundNeutralLight` #FF6A00, `backgroundLight` #4639FF,
`backgroundNeutral` #3BFFD0, `backgroundDark` #8A5A2B, `tableAccent` #0000FF, `shapeStroke` #FF0000.
They already carry those loud values in probe 46's final theme (the base here), each unique in the
whole theme, so one capture of a gallery is enough: a pixel of a candidate colour proves the key
paints there, no control capture needed. Blueprint builds two pages from specs with every visual type
it can build (`bp apply`, nothing by hand): **Gallery A** (table, matrix, two slicers, column, bar,
line, pie, donut, scatter, multi-row card, KPI) and **Gallery B** (stacked column, 100% stacked
column, stacked bar, area, card, a list slicer).

PREDICTIONS (written before the probe is opened). Counted as exact pixels of each candidate
colour in the captures, plus pixels within 6 per channel (thin lines are anti-aliased):

 H1  At least one more key paints somewhere on the gallery than on probe 46's pages. Low
     confidence: probe 46 already covered cards, a KPI, a table, line/bar/column/donut/pie. New
     element types here are a matrix, slicers (list and dropdown), a scatter, a multi-row card,
     stacked and area charts.
 H2  Best guesses, each low confidence: slicers (dropdown border, list item rule) take a background
     or stroke key (`backgroundNeutral`, `shapeStroke`); axis and gridlines of the cartesian charts
     take `backgroundDark` or `shapeStroke`; the table and matrix grid take `tableAccent` (the
     name suggests it). Whichever of them paints is recorded with where, from the diff of
     coordinates.
 H3  Some keys paint nothing in any static state: hover, selection, focus, disabled and error
     states can't be captured, and a key such as `foregroundNeutralLight` or
     `foregroundNeutralTertiary` may only appear in them. "No pixels" is "not seen in a static
     capture", never "unused".
 H4  Reloading changes no `visual.json` (theme-driven), as probes 42 and 46 found.

All content is the demo's financial sample.
"""

import shutil
import sys
import tempfile
from pathlib import Path

from _probe import git, make_probe

from blueprint.cli import main as bp

SALES = '{ field: "financials[Sales]", aggregate: sum }'
PROFIT = '{ field: "financials[Profit]", aggregate: sum }'
GROSS = '{ field: "financials[Gross Sales]", aggregate: sum }'
COUNTRY, SEGMENT, DATE = '"financials[Country]"', '"financials[Segment]"', '"financials[Date]"'


def layout(name: str, cols: int, rows: int, w: int, h: int) -> str:
    out = [f"# Probe 48: {cols}x{rows} regions under a header (grid 8, margin 24, gutter 16).",
           f"name: {name}", "canvas: { width: 1280, height: 720 }", "regions:",
           "  - { role: header, x: 24, y: 24, w: 1232, h: 64 }"]
    for r in range(rows):
        for c in range(cols):
            out.append(f"  - {{ role: main, x: {24 + c * (w + 16)}, y: {104 + r * (h + 16)}, w: {w}, h: {h} }}")
    return "\n".join(out) + "\n"


def page(title: str, layout_name: str, visuals: list[str]) -> str:
    return (f"page: {title}\nlayout: {layout_name}\nvisuals:\n  - {{ type: header, title: {title} }}\n"
            + "".join(f"  - {v}\n" for v in visuals))


SPECS = {
    "gallery-a.yaml": page("Gallery A", "gallery-12", [
        f'{{ type: table, id: a-table, title: Table, slots: {{ columns: [{COUNTRY}, {SEGMENT}, {SALES}, {PROFIT}] }} }}',
        f'{{ type: matrix, id: a-matrix, title: Matrix, slots: {{ rows: {COUNTRY}, columns: {SEGMENT}, values: {SALES} }} }}',
        f'{{ type: slicer, id: a-slicer-list, title: List slicer, slots: {{ field: {COUNTRY} }} }}',
        f'{{ type: slicer, id: a-slicer-drop, title: Dropdown slicer, options: {{ style: dropdown }}, slots: {{ field: {SEGMENT} }} }}',
        f'{{ type: column, id: a-column, title: Column, options: {{ labels: "on" }}, slots: {{ category: {COUNTRY}, value: {SALES} }} }}',
        f'{{ type: bar, id: a-bar, title: Bar, slots: {{ category: {COUNTRY}, value: {SALES} }} }}',
        f'{{ type: line, id: a-line, title: Line, slots: {{ category: {DATE}, value: {SALES} }} }}',
        f'{{ type: pie, id: a-pie, title: Pie, slots: {{ category: {SEGMENT}, value: {SALES} }} }}',
        f'{{ type: donut, id: a-donut, title: Donut, options: {{ legend: bottom }}, slots: {{ category: {COUNTRY}, value: {SALES} }} }}',
        f'{{ type: scatter, id: a-scatter, title: Scatter, slots: {{ category: {COUNTRY}, x: {SALES}, y: {PROFIT} }} }}',
        f'{{ type: multi-row-card, id: a-mrc, title: Multi-row card, slots: {{ fields: [{COUNTRY}, {SALES}, {PROFIT}] }} }}',
        f'{{ type: kpi, id: a-kpi, title: KPI, region: main, slots: {{ value: {SALES}, trend: {DATE}, target: {GROSS} }} }}']),
    "gallery-b.yaml": page("Gallery B", "gallery-6", [
        f'{{ type: stacked-column, id: b-stacked-col, title: Stacked column, slots: {{ category: {COUNTRY}, value: {SALES}, legend: {SEGMENT} }} }}',
        f'{{ type: stacked-column-100, id: b-stacked-100, title: 100% stacked column, slots: {{ category: {COUNTRY}, value: {SALES}, legend: {SEGMENT} }} }}',
        f'{{ type: stacked-bar, id: b-stacked-bar, title: Stacked bar, slots: {{ category: {COUNTRY}, value: {SALES}, legend: {SEGMENT} }} }}',
        f'{{ type: area, id: b-area, title: Area, slots: {{ category: {DATE}, value: {SALES} }} }}',
        f'{{ type: card, id: b-card, title: Card, slots: {{ value: {SALES} }} }}',
        f'{{ type: slicer, id: b-slicer, title: Segment list, slots: {{ field: {SEGMENT} }} }}']),
}

STEPS = """\
# Probe 48: where do the structural colours paint?

Blueprint built two pages, **Gallery A** and **Gallery B**, with every visual type it can make.
Claude opens the report through the bridge, captures both pages and measures the pixels. You only:

1. Open the report if it isn't open yet. Click **Refresh now** if it asks. Don't click anything inside
   a visual.
2. Tell Claude when the pages show data. Nothing needs saving.
"""

if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    dest, base = Path(sys.argv[1]), Path(sys.argv[2])
    cache = base / "financial.SemanticModel" / ".pbi" / "cache.abf"
    if not cache.is_file():
        sys.exit(f"no data cache at {cache}")
    with tempfile.TemporaryDirectory() as stage:
        shutil.copytree(base, stage + "/src",
                        ignore=shutil.ignore_patterns(".git", ".pbi", "STEPS.md", "snap.sh"))
        make_probe(Path(stage) / "src", dest, STEPS, snap=True)
    (dest / "layouts" / "gallery-12.yaml").write_text(layout("gallery-12", 4, 3, 296, 184), encoding="utf-8")
    (dest / "layouts" / "gallery-6.yaml").write_text(layout("gallery-6", 3, 2, 400, 288), encoding="utf-8")
    for name, body in SPECS.items():
        (dest / "specs" / name).write_text(body, encoding="utf-8")
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "inputs: layouts gallery-12 and gallery-6, specs gallery-a and gallery-b")
    guide = str(dest / "guidelines.yaml")
    if bp(["apply", str(dest / "specs" / "gallery-a.yaml"), str(dest / "specs" / "gallery-b.yaml"),
           "--report", str(dest), "--guidelines", guide, "--set", "page.max_visuals=20"]) != 0:
        sys.exit(1)
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "blueprint: apply specs/gallery-a.yaml and gallery-b.yaml")
    (dest / "financial.SemanticModel" / ".pbi").mkdir(exist_ok=True)
    shutil.copy2(cache, dest / "financial.SemanticModel" / ".pbi" / "cache.abf")
    print(f"data cache copied from {cache}\nProbe ready: {dest}")
