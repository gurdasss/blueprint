"""Build the Desktop probe for `labels` and `legend` on a scatter chart and a map (UNRUN).

Usage:
    python unverified-probes/scatter-map-options/probe.py <dest folder> <data cache .abf>

**This probe has never been opened in Desktop.** Nothing in it may be cited as evidence, and no
contract may gain an option because of what it predicts. See `unverified-probes/README.md`.

Why it is core: `labels` and `legend` are options every other chart type in the core carries, and
the unevenness is an accident of which probe covered which type — the same accident probe 31
fixed for `bar`/`line` and probe 35 for `area` and the stacked charts. `scatter` and `map` came in
with probes 34 and 36 and have **no options at all**, so a spec can bind them and then has to
leave every legend to Desktop. Both sample reports position or hide a legend on these types.

    scatter (scatterChart)   labels ✗   legend position ✗   legend off ✗
    map (map)                labels ✗   legend position ✗   legend off ✗

The **bindings** are written by `bp apply` from the shipped contracts (probe 36 already had
Desktop accept them), so only the option objects are candidates, as in probe 35. Each page is a
full matrix for one type: a control with no objects, `labels` forced on and off, a legend moved
right and top, and a hidden legend. The control is what settles each type's **default**, which is
the part no existing evidence covers.

PREDICTIONS (written before the probe is opened):

 P1  `objects.legend[0].properties.position = 'Right'` moves the **scatter**'s legend to the
     right, and `'Top'` to the top. A scatter is a cartesian chart like the seven that already
     take this object, so this is the most likely of the lot.
 P2  `objects.legend[0].properties.show = false` hides the **scatter**'s legend, as it does on
     the clustered column, bar and line (probe 32) and the area and stacked charts (probe 35).
 P3  `objects.labels[0].properties.show = true` shows data labels on the **scatter** — the point
     labels Desktop calls "Data labels" — and `false` hides them. Less sure than P1/P2: a
     scatter's labels are per point, not per bar, and Desktop may keep them under a different
     object (`categoryLabels` is the other candidate; if `labels` does nothing, the control and
     both labels variants will look identical and that is the result).
 P4  The **map**'s legend takes the same `legend` object: `'Right'` and `'Top'` move it, `show =
     false` hides it. **The least sure prediction here.** A map is not a cartesian chart, it
     renders through a different control, and its legend may well be `objects.legend` with other
     property names — or not be a formatting object at all.
 P5  `objects.labels[0].properties.show` does nothing visible on the **map**: a bubble map's text
     is Desktop's "Category labels", which I expect to be a different object. Writing it is how
     we find out, and a no-op is a finding: it keeps `labels` off the map contract.
 P6  Desktop's default, from the two controls: the scatter shows a legend (because `Series` is
     bound) and no data labels; the map shows a legend and no labels. If a control turns out to
     show labels by default, then `labels` on that type needs **both** `"on"` and `"off"` values
     in its contract, not just `"on"` as the charts have.
 P7  The save keeps every object exactly as written, changing only what any save changes:
     `$schema` 2.13.0 -> 2.14.0, Desktop's condition-less auto `filterConfig`, `pages.json`
     `activePageName`, and `"active": true` added to each scatter's `X` projection (probe 36).
 P8  No visual errors. The **maps** draw only if "Map and filled map visuals" is on in this
     Desktop (File > Options and settings > Options > Global > Security); a disabled map is a
     result about the install, not about what was written (probes 34, 36).

If they hold: `scatter` and `map` gain `labels` and the whole `legend` option (the four positions
plus `off`, exactly as `column` declares them), citing this probe, and the acceptance half is a
second probe that builds the same pages from specs **with those options set**, the way probe 33
followed probe 32. A prediction that fails simply leaves that cell out of the contract.

All content is invented.
"""

import copy
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

# scripts/ is not an importable package, so it goes on sys.path above, not in pyproject.
from _probe import git, make_probe

from blueprint.cli import main as bp
from blueprint.pbir import jsonfmt

PROBE = "38"
GUIDE = ROOT / "guidelines" / "example.yaml"
MEASURE = ("\tmeasure 'Target Amount' = 600\r\n\t\tformatString: 0\r\n"  # as scripts/demo.sh
           "\t\tlineageTag: 9ab090f9-bd7f-43c4-82be-86470a46784b\r\n\r\n")

SCATTER = ('{category: "Sales[Country]", legend: "Sales[Region]", '
           'x: "[Total Amount]", y: "[Target Amount]"}')
MAP = '{category: "Sales[Country]", legend: "Sales[Region]", size: "[Total Amount]"}'

# The six cells of the matrix, written on every type: spec id suffix -> (title, visual.objects).
# `None` is the control, which is what settles the type's default.
CELLS = [
    ("control", "Control: no objects", None),
    ("labels-on", "labels show = true", {"labels": "show:true"}),
    ("labels-off", "labels show = false", {"labels": "show:false"}),
    ("legend-right", "legend position = Right", {"legend": "position:'Right'"}),
    ("legend-top", "legend position = Top", {"legend": "position:'Top'"}),
    ("legend-off", "legend show = false", {"legend": "show:false"}),
]


def objects(spec: dict[str, str]) -> dict:
    """``{"legend": "position:'Right'"}`` -> the PBIR `objects` shape (probes 23, 32, 35)."""
    out = {}
    for name, cell in spec.items():
        prop, _, value = cell.partition(":")
        out[name] = [{"properties": {prop: {"expr": {"Literal": {"Value": value}}}}}]
    return out


CANDIDATES = {f"{prefix}-{sid}": objects(spec)
              for prefix in ("sc", "map")
              for sid, _, spec in CELLS if spec is not None}


def page(name: str, title: str, vtype: str, prefix: str, slots: str) -> str:
    rows = "".join(f'  - {{type: {vtype}, id: {prefix}-{sid}, title: "{label}", slots: {slots}}}\n'
                   for sid, label, _ in CELLS)
    return f'page: {name}\nlayout: grid-2x3\nvisuals:\n  - {{type: header, title: "{title}"}}\n{rows}'


SPECS = {
    "scatter-options.yaml": page("Scatter Options", "Scatter: legend and labels candidates",
                                 "scatter", "sc", SCATTER),
    "map-options.yaml": page("Map Options", "Map: legend and labels candidates (needs map "
                             "visuals enabled)", "map", "map", MAP),
}

STEPS = f"""\
# Probe {PROBE}: legend and data labels on a scatter chart and a map

`bp apply` built both pages from the shipped contracts, so every binding is Blueprint's own
output (probe 36 verified those). The probe then wrote **candidate option objects** on ten of the
twelve visuals: `labels` forced on and off, a legend moved Right and Top, and a hidden legend —
once per type. The first visual on each page is a control with no objects at all.

Claude opens the report through the bridge and captures both pages; you only:

1. Click **Refresh now** on the banner (or **Home -> Refresh**), then **Ctrl+S**.

Never click inside a visual and don't open a field's menu. Tell Claude when it is saved, and for
each page say:

- where the legend sits on the **control**, and whether the control shows labels on its points
  or bubbles (this is the type's default, which no probe has recorded);
- whether "labels show = true" and "labels show = false" differ from the control at all;
- whether the Right and Top legends really moved, and whether "legend show = false" has no
  legend.

If the **maps** show "Map and filled map visuals are disabled", that is this Desktop's security
setting (File > Options and settings > Options > Global > Security), not the file: say so, switch
it on if you're willing, and restart Desktop (probe 34 needed a restart).

What it settles: whether `scatter` and `map` take the same `labels` and `legend` options the
other seven core chart types already ship, and what each type shows by default.
"""


def patch_objects(report: Path) -> list[str]:
    """Write each candidate's `objects` onto the visual whose `blueprint.visual` id matches."""
    changed = []
    for f in sorted(report.glob("definition/pages/*/visuals/*/visual.json")):
        doc = jsonfmt.load(f)
        sid = next((a["value"] for a in doc.get("annotations", [])
                    if a.get("name") == "blueprint.visual"), None)
        if sid not in CANDIDATES:
            continue
        body = doc["visual"]
        body["objects"] = {**body.get("objects", {}), **copy.deepcopy(CANDIDATES[sid])}
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
    git(dest, "commit", "-q", "-m",
        "model: add measure Target Amount (as Desktop wrote it in probe 20)")

    specs = dest / "specs"
    specs.mkdir()
    for name, body in SPECS.items():
        (specs / name).write_text(body, encoding="utf-8")
    if bp(["apply", str(specs), "--report", str(dest), "--guidelines", str(GUIDE)]) != 0:
        sys.exit(1)
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "blueprint: apply specs/ (six scatters, six maps)")

    print("\n".join(patch_objects(dest / "Fixture.Report")))
    if bp(["manifest", "--report", str(dest), "--guidelines", str(GUIDE)]) != 0:
        sys.exit(1)
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "probe: candidate labels and legend objects on both types")

    shutil.copy2(cache, dest / "Fixture.SemanticModel" / ".pbi" / "cache.abf")
    print(f"data cache copied from {cache}\nProbe ready: {dest}")
