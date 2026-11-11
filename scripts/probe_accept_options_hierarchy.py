"""Build the acceptance probe for probes 37-39's contract changes.

Usage:
    python scripts/probe_accept_options_hierarchy.py <dest folder> <data cache .abf>

Probes 37, 38 and 39 were candidate probes: the bindings came from `bp apply`, but the option
objects, and the hierarchy projections in the matrix and the slicer, were patched onto the files
afterwards. A candidate says "Desktop takes this shape"; only a probe built **entirely by
`bp apply`**, from specs, with the contracts that ship, says "Desktop takes what Blueprint
writes" (CLAUDE.md, "Test data"; probe 33 followed 32 this way, and 17 followed 16).

So nothing here is patched. Every page comes from a spec in `specs/`, every option is a spec
`options:` key, and every hierarchy is `Sales[Geography]` in a slot. If Desktop changes a cell,
that cell comes out of the contract.

It also closes the half probes 37 and 38 could not see. Each contract declares four legend
positions, but only some were ever drawn: `Top` on pie and donut, `Right` and `Top` on scatter
and map. The rest are the same property's other literals, as `area` and the stacked charts ship
them from probe 35's partial cells. Here every type gets all five values, so a position Desktop
refuses shows up as a changed file rather than as an assumption nobody tested.

Two of them cannot be judged by eye: `'Right'` is pie and donut's own default and `'Bottom'` is
scatter and map's (probes 37, 38). For those the result is what the **save** keeps, not what the
capture shows — probe 28 needed a theme defaulting to Top before `'Bottom'` could be seen at all.

PREDICTIONS (written before the probe is opened):

 P1  Desktop draws all four legend positions on **pie** and **donut**, and `legend: "off"` leaves
     no legend. `top` and `left` are visible moves; `right` matches their default and `bottom` is
     the one position no probe has seen on these two types, so it is the likeliest to surprise.
 P2  `labels: "off"` removes the detail labels on pie and donut, and `labels: "on"` shows them —
     the pair probe 37 verified, now written by `bp apply` from the contract's two values.
 P3  The same five legend values hold on **scatter** and **map**. `right` and `top` were drawn in
     probe 38; `bottom` matches their default and `left` is new on both.
 P4  A **matrix** with `rows: Sales[Geography]` and a **slicer** with `field: Sales[Geography]`,
     bound straight from the spec, draw as Desktop's own did in probe 39: the matrix expandable
     from Country to Region, the slicer showing Country with an expander. `render` writes the
     matrix's Rows with the first level active and the deeper one an explicit `false`, and the
     slicer's Field with every level active (`active_levels: all`), which is what Desktop wrote
     for its own two visuals.
 P5  The save keeps every option object and every projection exactly as written, changing only
     what any save changes: `$schema` 2.13.0 -> 2.14.0 on the files it rewrites, Desktop's
     condition-less auto `filterConfig`, `"active": true` on each scatter's `X` (probes 34, 36,
     38), `expansionStates` on anything expanded, and `pages.json` `activePageName`.
 P6  `bp check` on the saved report reports no `format` findings, and re-applying the same specs
     changes nothing but the manifest (the fingerprint matches what Desktop left).
 P7  No visual errors. The **maps** draw only if "Map and filled map visuals" is on in this
     Desktop (it was for probe 38); a disabled map is a result about the install, not the file.

If they hold, probes 37-39's features are done: candidate *and* acceptance, like every other
feature in the core. A cell that fails comes out of its contract before any of this merges.

All content is invented.
"""

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from _probe import git, make_probe

from blueprint.cli import main as bp

PROBE = "40"
GUIDE = ROOT / "guidelines" / "example.yaml"

# As scripts/demo.sh and probe 38 wrote it; `scatter` needs a second measure for its Y.
MEASURE = ("\tmeasure 'Target Amount' = 600\r\n\t\tformatString: 0\r\n"
           "\t\tlineageTag: 9ab090f9-bd7f-43c4-82be-86470a46784b\r\n\r\n")

# `hierarchy Geography` as Desktop wrote it in probe 16, as probe 39 inserted it.
HIERARCHY = (
    "\thierarchy Geography\r\n"
    "\t\tlineageTag: 1c532aa5-8b4d-4377-a0d9-2f88cbfd471d\r\n\r\n"
    "\t\tlevel Country\r\n"
    "\t\t\tlineageTag: 96a8fc60-b3a4-4c8d-ba60-fb8924982fbf\r\n"
    "\t\t\tcolumn: Country\r\n\r\n"
    "\t\tlevel Region\r\n"
    "\t\t\tlineageTag: 10795807-315b-45b3-ab90-5d16ec8ee6e2\r\n"
    "\t\t\tcolumn: Region\r\n\r\n"
)

# Six cells per chart page: all five legend values, and on pie/donut both labels values beside
# them, so one page covers every literal the contract declares.
LEGENDS = ["top", "bottom", "left", "right", "off"]


def chart_page(name: str, title: str, vtype: str, prefix: str, slots: str, labels: bool) -> str:
    rows = []
    for i, legend in enumerate(LEGENDS):
        opts = [f'legend: "{legend}"']
        if labels:
            opts.append(f'labels: "{"on" if i % 2 == 0 else "off"}"')
        rows.append(f'  - {{type: {vtype}, id: {prefix}-{legend}, '
                    f'title: "legend {legend}{", labels " + opts[1][9:-1] if labels else ""}", '
                    f'slots: {slots}, options: {{{", ".join(opts)}}}}}\n')
    # A sixth cell with no legend key at all: the contract leaves the default to Desktop, and on
    # pie/donut it also carries the labels value the five above used only once.
    last = f'  - {{type: {vtype}, id: {prefix}-plain, title: "no legend option", slots: {slots}'
    last += ', options: {labels: "off"}}\n' if labels else '}\n'
    return (f'page: {name}\nlayout: grid-2x3\nvisuals:\n'
            f'  - {{type: header, title: "{title}"}}\n' + "".join(rows) + last)


PIE = '{category: "Sales[Country]", value: "[Total Amount]"}'
SCATTER = ('{category: "Sales[Country]", legend: "Sales[Region]", '
           'x: "[Total Amount]", y: "[Target Amount]"}')
MAP = '{category: "Sales[Country]", legend: "Sales[Region]", size: "[Total Amount]"}'

SPECS = {
    "pie-accept.yaml": chart_page("Pie Accept", "Pie: every legend value and both labels values, "
                                  "written by bp apply", "pie", "pie", PIE, labels=True),
    "donut-accept.yaml": chart_page("Donut Accept", "Donut: every legend value and both labels "
                                    "values, written by bp apply", "donut", "dn", PIE, labels=True),
    "scatter-accept.yaml": chart_page("Scatter Accept", "Scatter: every legend value, written by "
                                      "bp apply", "scatter", "sc", SCATTER, labels=False),
    "map-accept.yaml": chart_page("Map Accept", "Map: every legend value (needs map visuals "
                                  "enabled)", "map", "map", MAP, labels=False),
    "hierarchy-accept.yaml": """\
page: Hierarchy Accept
layout: two-up
visuals:
  - {type: header, title: "Matrix rows and slicer field bound to the model hierarchy, from a spec"}
  - {type: matrix, id: mx-geography, title: "Matrix rows = Sales[Geography]",
     slots: {rows: "Sales[Geography]", values: "[Total Amount]"}}
  - {type: slicer, id: sl-geography, title: "Slicer field = Sales[Geography]",
     slots: {field: "Sales[Geography]"}}
""",
}

STEPS = f"""\
# Probe {PROBE}: Desktop accepts what `bp apply` writes for probes 37-39

Nothing here is patched. Every visual, every option and both hierarchies came from the specs in
`specs/`, through the contracts as they ship. That is the difference between this probe and 37,
38 and 39: those asked whether Desktop takes a shape, this asks whether it takes **Blueprint's**.

Five pages: **Pie Accept**, **Donut Accept**, **Scatter Accept**, **Map Accept** (each with all
five legend values, and on pie/donut both labels values), and **Hierarchy Accept** (a matrix and
a slicer on `Sales[Geography]`).

Claude opens the report through the bridge and captures the pages; you only:

1. Click **Refresh now** on the banner (or **Home -> Refresh**), visit each page so it draws,
   then **Ctrl+S**.

Never click inside a visual and don't open a field's menu — except on **Hierarchy Accept**, where
expanding a row and a slicer node is the point; do that last, and save again afterwards.

Two cells cannot be judged by eye, so don't worry about them: `legend right` on pie and donut and
`legend bottom` on scatter and map are each that type's own default. What settles those is
whether the save keeps the literal.

If the **maps** show "Map and filled map visuals are disabled", that is this Desktop's security
setting (File > Options and settings > Options > Global > Security), not the file.

What it settles: whether Desktop keeps, byte for byte, the options and hierarchy projections
`bp apply` writes from the contracts probes 37-39 licensed — the acceptance half those three
probes each called for.
"""


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    dest, cache = Path(sys.argv[1]), Path(sys.argv[2])
    make_probe(ROOT / "fixtures" / "02-card-and-chart", dest, STEPS, snap=True)

    tmdl = dest / "Fixture.SemanticModel" / "definition" / "tables" / "Sales.tmdl"
    text = tmdl.read_bytes().decode()
    assert text.count("\tcolumn Country") == 1, "fixture 02 changed; re-anchor the measure"
    assert text.count("\tpartition Sales = m") == 1, "fixture 02 changed; re-anchor the hierarchy"
    text = text.replace("\tcolumn Country", MEASURE + "\tcolumn Country", 1)
    text = text.replace("\tpartition Sales = m", HIERARCHY + "\tpartition Sales = m", 1)
    tmdl.write_bytes(text.encode())
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m",
        "model: add measure Target Amount and hierarchy Geography (as Desktop wrote them)")

    specs = dest / "specs"
    specs.mkdir()
    for name, body in SPECS.items():
        (specs / name).write_text(body, encoding="utf-8")
    if bp(["apply", str(specs), "--report", str(dest), "--guidelines", str(GUIDE)]) != 0:
        sys.exit(1)
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m",
        "blueprint: apply specs/ (every legend and labels value, and the hierarchy wells)")

    shutil.copy2(cache, dest / "Fixture.SemanticModel" / ".pbi" / "cache.abf")
    print(f"data cache copied from {cache}\nProbe ready: {dest}")
