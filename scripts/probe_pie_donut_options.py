"""Build the Desktop probe for `labels` and `legend` on a pie and a donut chart (UNRUN).

Usage:
    python unverified-probes/pie-donut-options/probe.py <dest folder> <data cache .abf>

**This probe has never been opened in Desktop.** Nothing in it may be cited as evidence, and no
contract may gain an option because of what it predicts. See `unverified-probes/README.md`.

Why it is core: `pie` and `donut` are the last two chart types in the core with **no options at
all**. They were promoted (probes 08, 11, 22-24) for their *bindings*; the option parity probe 35
ran before promoting the area and stacked charts never covered them, so a spec can bind a pie and
then has to leave its legend and its labels to Desktop. After this probe and the scatter/map one,
every chart type in the core takes the same two options and nothing else is owed:

    pie (pieChart)       labels ✗   legend position ✗   legend off ✗
    donut (donutChart)   labels ✗   legend position ✗   legend off ✗

The **bindings** are written by `bp apply` from the shipped contracts (probes 09 and 24 already
had Desktop accept them), so only the option objects are candidates, as in probe 35. Each page is
a full matrix for one type: a control with no objects, `labels` forced on and off, a legend moved
right and top, and a hidden legend. These two types are the ones where the control matters most,
because a pie's detail labels are **on** by Desktop's default, unlike every bar and line chart
probed so far.

PREDICTIONS (written before the probe is opened):

 P1  `objects.legend[0].properties.position = 'Right'` moves the **pie**'s legend right, and
     `'Top'` to the top: the same object as the seven cartesian chart types (probes 23, 32, 35).
     A pie's legend lists its Category values rather than its measures, but it is the same legend
     control, so this is the most likely prediction here.
 P2  `objects.legend[0].properties.show = false` hides the **pie**'s legend.
 P3  P1 and P2 hold identically on the **donut**: the two types differ only in `visualType`
     (`pieChart` / `donutChart`), as probe 22 found for their bindings.
 P4  `objects.labels[0].properties.show = false` **hides** the detail labels on both, and `true`
     shows them. The interesting half: I expect the **control to already show labels**, because
     Desktop turns detail labels on by default for pie and donut. If so, these two types need a
     contract option with **both** values — `labels: {"on": "true", "off": "false"}` — unlike
     `column`, which ships only `"on"` because its default is off (probe 23).
 P5  The least sure: that the object is called `labels` at all. Desktop's pane calls these
     "Detail labels", and the property may live under a different object name. If writing
     `labels` changes nothing on either chart, the control and both variants will look the same,
     and that is the result: `labels` stays off the pie and donut contracts and only `legend` is
     added.
 P6  Desktop's default, from the two controls: a legend at the theme's default position (bottom,
     as probe 35's control showed) and detail labels shown.
 P7  The save keeps every object exactly as written, changing only what any save changes:
     `$schema` 2.13.0 -> 2.14.0, Desktop's condition-less auto `filterConfig`, `pages.json`
     `activePageName`.
 P8  No visual errors, and the Category legend keeps drilling: nothing here touches the query.

If they hold: `pie` and `donut` gain `legend` (the four positions plus `off`, exactly as `column`
declares them) and `labels` with whichever values the control proves are needed, citing this
probe; then an acceptance probe builds the same pages from specs **with the options set**, the
way probe 33 followed probe 32.

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

PROBE = "37"
GUIDE = ROOT / "guidelines" / "example.yaml"
SLOTS = '{category: "Sales[Country]", value: "[Total Amount]"}'

# The six cells of the matrix, written on both types: spec id suffix -> (title, visual.objects).
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
              for prefix in ("pie", "dn")
              for sid, _, spec in CELLS if spec is not None}


def page(name: str, title: str, vtype: str, prefix: str) -> str:
    rows = "".join(f'  - {{type: {vtype}, id: {prefix}-{sid}, title: "{label}", slots: {SLOTS}}}\n'
                   for sid, label, _ in CELLS)
    return f'page: {name}\nlayout: grid-2x3\nvisuals:\n  - {{type: header, title: "{title}"}}\n{rows}'


SPECS = {
    "pie-options.yaml": page("Pie Options", "Pie: legend and detail label candidates",
                             "pie", "pie"),
    "donut-options.yaml": page("Donut Options", "Donut: legend and detail label candidates",
                               "donut", "dn"),
}

STEPS = f"""\
# Probe {PROBE}: legend and detail labels on a pie and a donut chart

`bp apply` built both pages from the shipped contracts, so every binding is Blueprint's own
output (probes 09 and 24 verified those). The probe then wrote **candidate option objects** on ten
of the twelve visuals: `labels` forced on and off, a legend moved Right and Top, and a hidden
legend — once per type. The first visual on each page is a control with no objects at all.

Claude opens the report through the bridge and captures both pages; you only:

1. Click **Refresh now** on the banner (or **Home -> Refresh**), then **Ctrl+S**.

Never click inside a visual and don't open a field's menu. Tell Claude when it is saved, and for
each page say:

- whether the **control** shows labels on its slices, and where its legend sits (this is the
  type's default, and the pie's default is the one the contract hangs on);
- whether "labels show = false" really removed the slice labels, and whether "labels show = true"
  differs from the control at all;
- whether the Right and Top legends moved, and whether "legend show = false" has no legend.

What it settles: whether `pie` and `donut` take the same `labels` and `legend` options the other
core chart types ship, and whether their `labels` needs an `"off"` value because Desktop's
default is on.
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

    specs = dest / "specs"
    specs.mkdir()
    for name, body in SPECS.items():
        (specs / name).write_text(body, encoding="utf-8")
    if bp(["apply", str(specs), "--report", str(dest), "--guidelines", str(GUIDE)]) != 0:
        sys.exit(1)
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "blueprint: apply specs/ (six pies, six donuts)")

    print("\n".join(patch_objects(dest / "Fixture.Report")))
    if bp(["manifest", "--report", str(dest), "--guidelines", str(GUIDE)]) != 0:
        sys.exit(1)
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "probe: candidate labels and legend objects on both types")

    shutil.copy2(cache, dest / "Fixture.SemanticModel" / ".pbi" / "cache.abf")
    print(f"data cache copied from {cache}\nProbe ready: {dest}")
