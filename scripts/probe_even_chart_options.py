"""Build the Desktop probe that evens up the chart options before promotion (probe 35).

Usage:
    python scripts/probe_even_chart_options.py <dest folder> <data cache .abf>

`labels` and `legend` are verified unevenly across the charts still in the archive, purely by
which probe happened to cover which type — the same accident probe 31 fixed for the core three:

    area (areaChart)                 labels ✗   legend position ✗   legend off ✗
    stacked-column (columnChart)     labels ✓   legend position ✗   legend off ✗
    stacked-column-100               labels ✓   legend position ✓   legend off ✗
    stacked-bar (barChart)           labels ✓   legend position ✓   legend off ✗

(`legend: off`, i.e. `objects.legend[0].properties.show = false`, is probe 32 and was only ever
written on the core's clustered column, clustered bar and line.)

Promoting these four with those gaps would put the unevenness in the core, where `column`, `bar`
and `line` all behave alike. This probe closes the seven missing cells. The **bindings** are
written by `bp apply` from the archived contracts (so this is also an acceptance probe for them);
only the option objects are candidates. Every chart binds two measures, so a legend of measure
names exists and hiding it is visible.

PREDICTIONS (written before the probe is opened):

 P1  `objects.labels[0].properties.show = true` shows data labels on the **area** chart, on both
     series. The least sure of the seven: probe 23 verified this object on the column and the
     three stacked charts, never on an area chart, and an area chart's labels sit over filled
     regions.
 P2  `objects.legend[0].properties.position = 'Right'` moves the area chart's legend right.
 P3  `objects.legend[0].properties.show = false` hides the area chart's legend.
 P4  The same `position = 'Right'` moves the **stacked column**'s legend right (probe 23 moved it
     on the clustered column, the 100% stacked and the stacked bar — never on this one).
 P5  `show = false` hides the **stacked column**'s legend.
 P6  `show = false` hides the **100% stacked column**'s legend.
 P7  `show = false` hides the **stacked bar**'s legend.
 P8  The save keeps all seven as written, changing only what any save changes: `$schema`
     2.13.0 -> 2.14.0, Desktop's condition-less auto `filterConfig`, `pages.json`
     `activePageName`.

If they hold, the four contracts get `labels` and the full `legend` (positions plus `off`), and
all seven chart types in the core behave alike.

All content is invented.
"""

import shutil
import sys
from pathlib import Path

from _probe import git, make_probe
from probe_chart_variants import spec_id

from blueprint.cli import main as bp
from blueprint.pbir import jsonfmt

ROOT = Path(__file__).resolve().parent.parent
ARCHIVE = ROOT / "blueprint" / "visuals" / "archive"
MEASURE = ("\tmeasure 'Target Amount' = 600\r\n\t\tformatString: 0\r\n"  # as scripts/demo.sh
           "\t\tlineageTag: 9ab090f9-bd7f-43c4-82be-86470a46784b\r\n\r\n")

TWO = '{category: "Sales[Country]", value: ["[Total Amount]", "[Target Amount]"]}'


def lit(value: str) -> dict:
    return {"expr": {"Literal": {"Value": value}}}


# spec id -> the visual.objects to write (the cells no probe has covered)
CANDIDATES = {
    "area-labels": {"labels": [{"properties": {"show": lit("true")}}]},
    "area-right":  {"legend": [{"properties": {"position": lit("'Right'")}}]},
    "area-off":    {"legend": [{"properties": {"show": lit("false")}}]},
    "sc-right":    {"legend": [{"properties": {"position": lit("'Right'")}}]},
    "sc-off":      {"legend": [{"properties": {"show": lit("false")}}]},
    "s100-off":    {"legend": [{"properties": {"show": lit("false")}}]},
    "sbar-off":    {"legend": [{"properties": {"show": lit("false")}}]},
}

ROWS = [
    ("area-labels", "area", "Area data labels"),
    ("area-right", "area", "Area legend right"),
    ("area-off", "area", "Area legend off"),
    ("sc-right", "stacked-column", "Stacked column legend right"),
    ("sc-off", "stacked-column", "Stacked column legend off"),
    ("s100-off", "stacked-column-100", "100% stacked legend off"),
]
ROWS2 = [
    ("sbar-off", "stacked-bar", "Stacked bar legend off"),
    ("area-plain", "area", "Area, no options (the control)"),
]


def page(name: str, title: str, layout: str, rows: list[tuple[str, str, str]]) -> str:
    return (f"page: {name}\nlayout: {layout}\nvisuals:\n  - {{type: header, title: \"{title}\"}}\n"
            + "".join(f"  - {{type: {t}, id: {sid}, title: \"{label}\", slots: {TWO}}}\n"
                      for sid, t, label in rows))


SPECS = {
    "even-options.yaml": page("Even Options", "Options the archive never had", "grid-2x3", ROWS),
    "even-options-2.yaml": page("Even Options 2", "Stacked bar, and a control", "two-up", ROWS2),
}

STEPS = """\
# Probe 35: the chart options the archived charts were never probed for

`bp apply` built both pages from the archived contracts (so the bindings are Blueprint's own
output), and the probe then wrote seven candidate option objects: data labels and a legend
position and a hidden legend on the **area** chart, a legend position and a hidden legend on the
**stacked column**, and a hidden legend on the **100% stacked column** and the **stacked bar**.

Claude opens the report through the bridge and captures both pages; you only:

1. Click **Refresh now** on the banner (or **Home -> Refresh**), then **Ctrl+S**.

Never click inside a visual and don't open a field's menu. Tell Claude when it is saved, and say
whether anything looked wrong — in particular whether the area chart showed numbers on its two
series, and whether the four "legend off" charts really have no legend (the control on page 2
shows where a legend sits by default).

What it settles: whether these four chart types take the same `labels` and `legend` options the
core's column, bar and line already ship, so they can be promoted without carrying the gap in.
"""


def make_candidates(report: Path) -> list[str]:
    changed = []
    for f in sorted(report.glob("definition/pages/*/visuals/*/visual.json")):
        doc = jsonfmt.load(f)
        sid = spec_id(doc)
        if sid not in CANDIDATES:
            continue
        body = doc["visual"]
        body["objects"] = {**body.get("objects", {}), **CANDIDATES[sid]}
        f.write_bytes(jsonfmt.dump_bytes(doc))
        changed.append(f"{sid} ({body['visualType']}): objects {', '.join(CANDIDATES[sid])}")
    return changed


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
           "--guidelines", str(ROOT / "guidelines" / "example.yaml"),
           "--visuals", str(ARCHIVE)]) != 0:
        sys.exit(1)
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "blueprint: apply specs/ (area and the stacked charts)")

    print("\n".join(make_candidates(dest / "Fixture.Report")))
    if bp(["manifest", "--report", str(dest),
           "--guidelines", str(ROOT / "guidelines" / "example.yaml"),
           "--visuals", str(ARCHIVE)]) != 0:
        sys.exit(1)
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "probe: candidate labels and legend options on the four charts")

    shutil.copy2(cache, dest / "Fixture.SemanticModel" / ".pbi" / "cache.abf")
    print(f"data cache copied from {cache}\nProbe ready: {dest}")
