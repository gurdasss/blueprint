"""Build the Desktop probe for the scatter chart, the multi-row card and the map (probe 34).

Usage:
    python scripts/probe_map_scatter_card.py <dest folder> <data cache .abf>

These are the three visual types real reports use that **no contract covers**, so a spec can't
express those pages at all. A survey of the three sample reports (counts only, nothing from them
is kept) found: `map` 4, `multiRowCard` 6, `scatterChart` 3, and the wells each fills:

    map           Category (column, "active": true), Series (column, 3 of 4), Size (measure)
    scatterChart  Category (column, "active", 1-2 of them), Series (column), Size (measure),
                  X (measure, "active" in both files read), Y (measure)
    multiRowCard  Values — one measure in all 6, never more, no "active", no objects

The samples are PBIX conversions, so their `queryRef`s are Desktop's old `select`/`select1` and
their `active` flags may be drill view state. They are evidence of **which wells exist**, not of
what Desktop writes on a fresh field. This probe writes Blueprint's own shapes as **candidates**
(the probe 22/23/32 method) and lets Desktop draw them, then keep them through one save.

PREDICTIONS (written before the probe is opened):

 P1  `multiRowCard` with `Values` = one measure draws one row (card title + value). With **two**
     measures it draws both, stacked in well order. The samples never showed more than one, so
     this is the one I'd call even money.
 P2  `multiRowCard` with `Values` = a column **and** a measure draws too (it is a list of values,
     and `tableEx` takes the mix in one role). Less sure: Desktop may refuse a column here.
 P3  `scatterChart` with Category (column, `"active": true`), X (measure) and Y (measure) draws
     one point per country, X across and Y up, and is kept as written. I am writing **no**
     `"active"` on X, although both sample files carry it: a fresh field shouldn't need it, and
     if Desktop adds it on save, the save diff says so and the contract gets it (`Slot.active`).
 P4  Adding Series (column) and Size (measure) draws coloured, sized bubbles with a legend.
 P5  `scatterChart` with a Category drill list (Country, Region; first `active`) draws, as it does
     on a column chart (probe 28).
 P6  `map` is the one with an environment risk, not just a shape risk: the Bing map service needs
     internet, and the fixture's `Country` column has **no `dataCategory`** in TMDL, so Desktop
     must geocode "FR"/"UK" by column name alone. I predict it draws two bubbles sized by Total
     Amount; a blank map or "we couldn't find a location" is a result about this environment and
     the model, not about the shape, and would mean the map needs a `dataCategory` before it can
     ship.
 P7  The save keeps every `Category`/`Series`/`Size`/`X`/`Y`/`Values` projection as written, and
     changes only what any save changes: `$schema` 2.13.0 -> 2.14.0, Desktop's condition-less auto
     `filterConfig`, and `pages.json` `activePageName`.

Nothing ships from this probe alone: a drawn candidate says Desktop takes the shape, and an
acceptance probe (built by `bp apply`, as probes 24, 30 and 33 did) is what says Desktop takes
what Blueprint writes.

All content is invented.
"""

import shutil
import sys
from pathlib import Path

from _probe import git, make_probe
from probe_apply_hierarchy import HIERARCHY
from probe_chart_variants import REGION, spec_id

from blueprint.cli import main as bp
from blueprint.pbir import jsonfmt

ROOT = Path(__file__).resolve().parent.parent
MEASURE = ("\tmeasure 'Target Amount' = 600\r\n\t\tformatString: 0\r\n"  # as scripts/demo.sh
           "\t\tlineageTag: 9ab090f9-bd7f-43c4-82be-86470a46784b\r\n\r\n")


def column(name: str, active: bool | None = None) -> dict:
    out = {"field": {"Column": {"Expression": {"SourceRef": {"Entity": "Sales"}}, "Property": name}},
           "queryRef": f"Sales.{name}", "nativeQueryRef": name}
    return {**out, "active": active} if active is not None else out


def measure(name: str) -> dict:
    return {"field": {"Measure": {"Expression": {"SourceRef": {"Entity": "Sales"}}, "Property": name}},
            "queryRef": f"Sales.{name}", "nativeQueryRef": name}


COUNTRY, REGION_COL = column("Country", active=True), column("Region")
TOTAL, TARGET = measure("Total Amount"), measure("Target Amount")

# spec id -> (visualType, the whole queryState to write)
CANDIDATES = {
    # --- multiRowCard: the samples only ever showed one measure
    "mrc-one":    ("multiRowCard", {"Values": [TOTAL]}),
    "mrc-two":    ("multiRowCard", {"Values": [TOTAL, TARGET]}),
    "mrc-mixed":  ("multiRowCard", {"Values": [column("Country"), TOTAL]}),
    # --- scatterChart: minimal, full, and a drill-down category
    "sc-min":     ("scatterChart", {"Category": [COUNTRY], "X": [TOTAL], "Y": [TARGET]}),
    "sc-full":    ("scatterChart", {"Category": [COUNTRY], "Series": [REGION],
                                    "Size": [TOTAL], "X": [TOTAL], "Y": [TARGET]}),
    "sc-drill":   ("scatterChart", {"Category": [COUNTRY, column("Region", active=False)],
                                    "X": [TOTAL], "Y": [TARGET]}),
    # --- map: Bing-backed, so this one tests the environment as much as the shape
    "map-min":    ("map", {"Category": [COUNTRY], "Size": [TOTAL]}),
    "map-series": ("map", {"Category": [COUNTRY], "Series": [REGION], "Size": [TOTAL]}),
}

ONE = '{category: "Sales[Country]", value: "[Total Amount]"}'
SPECS = {
    "scatter-card.yaml": "page: Scatter And Card\nlayout: grid-2x3\nvisuals:\n"
    "  - {type: header, title: Scatter chart and multi-row card}\n"
    + "".join(f"  - {{type: column, id: {sid}, title: {title}, slots: {ONE}}}\n" for sid, title in [
        ("mrc-one", "Card one measure"), ("mrc-two", "Card two measures"),
        ("mrc-mixed", "Card column + measure"), ("sc-min", "Scatter minimal"),
        ("sc-full", "Scatter series + size"), ("sc-drill", "Scatter drill category")]),
    "map.yaml": "page: Map\nlayout: two-up\nvisuals:\n"
    "  - {type: header, title: Map (Bing; Country has no dataCategory)}\n"
    + "".join(f"  - {{type: column, id: {sid}, title: {title}, slots: {ONE}}}\n" for sid, title in [
        ("map-min", "Map category + size"), ("map-series", "Map with series")]),
}

STEPS = """\
# Probe 34: scatter chart, multi-row card and map

Blueprint built two pages of verified `column` charts and the probe then rewrote eight of them
into candidates: three `multiRowCard`, three `scatterChart`, two `map`. Claude opens the report
through the bridge and captures both pages; you only:

1. Click **Refresh now** on the banner (or **Home -> Refresh**), then **Ctrl+S**.

Never click inside a visual and don't open a field's menu: this probe is about what Desktop does
with what was written, untouched. Tell Claude when it is saved, and mention anything that looks
wrong — especially whether the **map** drew bubbles, drew nothing, or showed an error (it needs
the Bing map service, and the fixture's Country column has no geographic data category).

What it settles: whether Desktop draws each shape and keeps it through a save, whether a
multi-row card takes more than one field (and a column among them), and whether Desktop adds
`"active"` anywhere Blueprint didn't write it.
"""


def make_candidates(report: Path) -> list[str]:
    changed = []
    for f in sorted(report.glob("definition/pages/*/visuals/*/visual.json")):
        doc = jsonfmt.load(f)
        sid = spec_id(doc)
        if sid not in CANDIDATES:
            continue
        vtype, state = CANDIDATES[sid]
        body = doc["visual"]
        body["visualType"] = vtype
        # Desktop writes the roles alphabetically (probe 10), so Blueprint does too.
        body["query"]["queryState"] = {role: {"projections": [dict(p) for p in projections]}
                                       for role, projections in sorted(state.items())}
        body["query"].pop("sortDefinition", None)  # the sort was on fields these may not bind
        f.write_bytes(jsonfmt.dump_bytes(doc))
        changed.append(f"{sid} -> {vtype} {sorted(state)}")
    return changed


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    dest, cache = Path(sys.argv[1]), Path(sys.argv[2])
    make_probe(ROOT / "fixtures" / "02-card-and-chart", dest, STEPS, snap=True)
    tmdl = dest / "Fixture.SemanticModel" / "definition" / "tables" / "Sales.tmdl"
    text = tmdl.read_bytes().decode()
    text = text.replace("\tcolumn Country", MEASURE + "\tcolumn Country", 1)
    text = text.replace("\tpartition Sales = m", HIERARCHY + "\tpartition Sales = m", 1)
    tmdl.write_bytes(text.encode())
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "model: Target Amount and the Geography hierarchy (the demo's)")

    specs = dest / "specs"
    specs.mkdir()
    guide = str(ROOT / "guidelines" / "example.yaml")
    for name, body in SPECS.items():
        (specs / name).write_text(body, encoding="utf-8")
    if bp(["apply", str(specs), "--report", str(dest), "--guidelines", guide]) != 0:
        sys.exit(1)
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "blueprint: apply specs/ (verified column charts as the base)")

    print("\n".join(make_candidates(dest / "Fixture.Report")))
    if bp(["manifest", "--report", str(dest), "--guidelines", guide]) != 0:
        sys.exit(1)
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "probe: candidate multiRowCard, scatterChart and map visuals")

    shutil.copy2(cache, dest / "Fixture.SemanticModel" / ".pbi" / "cache.abf")
    print(f"data cache copied from {cache}\nProbe ready: {dest}")
