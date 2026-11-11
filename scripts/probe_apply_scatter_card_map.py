"""Build the Desktop probe that saves `bp apply`'s scatter, multi-row card and map (probe 36).

Usage:
    python scripts/probe_apply_scatter_card_map.py <dest folder> <data cache .abf>

Probe 34 wrote these three shapes **by hand** as candidates and Desktop drew them. Blueprint now
has contracts for them, which is the other claim: that Desktop accepts **what Blueprint writes**.
That is the bar every shipped type cleared — probe 20's shapes then probe 21's acceptance, probes
22/23 then 24, probe 29 then 30, probe 32 then 33 — and nothing here is patched: every visual is
built by `bp apply` from a spec.

PREDICTIONS (written before the probe is opened):

 A1  Every visual draws exactly as its probe-34 candidate did: a multi-row card showing one
     measure, two measures side by side, and one row per country for a column beside a measure;
     a scatter minimal, one with Legend and Size, and one with a drill-down category; and two
     maps, bubbles per country sized by the measure, the Legend one split into segments. No
     Desktop error — except that the **maps** draw only if "Map and filled map visuals" is on in
     this Desktop (probe 34: off by default, and the message came back after a refresh even with
     the setting on, so it may need a restart). A disabled map is a result about the install,
     not about what Blueprint wrote.
 A2  A real refresh + Ctrl+S keeps every projection Blueprint wrote, with **one addition I am
     predicting on purpose**: Desktop adds `"active": true` to the scatter's `X` projection, as
     it did in probe 34. Blueprint deliberately doesn't write it (`active` marks a column's drill
     state and `X` takes a measure), so this confirms it is Desktop's to add and that leaving it
     out is safe. Otherwise only the usual: `$schema` 2.13.0 -> 2.14.0, condition-less auto
     `filterConfig`, `pages.json` `activePageName`.
 A3  Re-running the same specs on the saved report changes nothing but, at most, the manifest —
     in particular the `active` Desktop added is not fought over, because a re-apply rewrites the
     query only when the bindings changed.
 A4  `bp check` on the saved report reports no `format` findings: what Blueprint wrote validates
     against the vendored schemas, and the three new types don't break the reader's round-trip.

All content is invented.
"""

import shutil
import sys
from pathlib import Path

from _probe import git, make_probe

from blueprint.cli import main as bp

ROOT = Path(__file__).resolve().parent.parent
MEASURE = ("\tmeasure 'Target Amount' = 600\r\n\t\tformatString: 0\r\n"  # as scripts/demo.sh
           "\t\tlineageTag: 9ab090f9-bd7f-43c4-82be-86470a46784b\r\n\r\n")

SPECS = {
    "scatter-card.yaml": """\
page: Scatter And Card
layout: grid-2x3
visuals:
  - {type: header, title: "Scatter chart and multi-row card, built by bp apply"}
  - {type: multi-row-card, id: mrc-one, title: "Card one measure", slots: {fields: "[Total Amount]"}}
  - {type: multi-row-card, id: mrc-two, title: "Card two measures", slots: {fields: ["[Total Amount]", "[Target Amount]"]}}
  - {type: multi-row-card, id: mrc-mixed, title: "Card column and measure", slots: {fields: ["Sales[Country]", "[Total Amount]"]}}
  - {type: scatter, id: sc-min, title: "Scatter minimal", slots: {category: "Sales[Country]", x: "[Total Amount]", y: "[Target Amount]"}}
  - {type: scatter, id: sc-full, title: "Scatter legend and size", slots: {category: "Sales[Country]", legend: "Sales[Region]", size: "[Total Amount]", x: "[Total Amount]", y: "[Target Amount]"}}
  - {type: scatter, id: sc-drill, title: "Scatter drill category", slots: {category: ["Sales[Country]", "Sales[Region]"], x: "[Total Amount]", y: "[Target Amount]"}}
""",
    "map.yaml": """\
page: Map
layout: two-up
visuals:
  - {type: header, title: "Map (needs map visuals enabled in Desktop)"}
  - {type: map, id: map-min, title: "Map category and size", slots: {category: "Sales[Country]", size: "[Total Amount]"}}
  - {type: map, id: map-legend, title: "Map with a legend", slots: {category: "Sales[Country]", legend: "Sales[Region]", size: "[Total Amount]"}}
""",
}

STEPS = """\
# Probe 36: Desktop's save of bp apply's scatter, multi-row card and map

Blueprint built both pages from specs. **Nothing is patched by hand** — this probe is only about
whether Desktop accepts what `bp apply` writes for the three new types. Claude opens the report
through the bridge and captures the pages; you only:

1. Click **Refresh now** on the banner (or **Home -> Refresh**), then **Ctrl+S**.

Never click inside a visual and don't open a field's menu. Tell Claude when it is saved.

If the two maps show "Map and filled map visuals are disabled", that is this Desktop's security
setting (File > Options and settings > Options > Global > Security), not the file: say so and
Claude will record it. Everything else should draw.

What it settles: whether Desktop draws and keeps Blueprint's own scatter, multi-row card and map,
and whether it adds `"active": true` to the scatter's X projection as it did in probe 34.
"""

if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    dest, cache = Path(sys.argv[1]), Path(sys.argv[2])
    make_probe(ROOT / "fixtures" / "02-card-and-chart", dest, STEPS, snap=True)
    tmdl = dest / "Fixture.SemanticModel" / "definition" / "tables" / "Sales.tmdl"
    text = tmdl.read_bytes().decode()
    tmdl.write_bytes(text.replace("\tcolumn Country", MEASURE + "\tcolumn Country", 1).encode())
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "model: add measure Target Amount (as Desktop wrote it in probe 20)")

    specs = dest / "specs"
    specs.mkdir()
    for name, body in SPECS.items():
        (specs / name).write_text(body, encoding="utf-8")
    if bp(["apply", str(specs), "--report", str(dest),
           "--guidelines", str(ROOT / "guidelines" / "example.yaml")]) != 0:
        sys.exit(1)
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "blueprint: apply specs/ (scatter, multi-row card, map)")

    shutil.copy2(cache, dest / "Fixture.SemanticModel" / ".pbi" / "cache.abf")
    print(f"data cache copied from {cache}\nProbe ready: {dest}")
