"""Build the Desktop probe for a model hierarchy in a matrix's Rows and a slicer's Field (UNRUN).

Usage:
    python unverified-probes/hierarchy-matrix-slicer/probe.py <dest folder> <data cache .abf>

**This probe has never been opened in Desktop.** Nothing in it may be cited as evidence, and no
contract may accept a hierarchy because of what it predicts. See `unverified-probes/README.md`.

Why it is core: binding a hierarchy built in the model is already a core feature — probe 16
recorded the shape, probes 17-19 had Desktop accept Blueprint's own, and `column`, `bar`, `line`,
`pie` and `table` all take one. The two types that refuse it do so **only for lack of a probe**,
and both contracts say so in as many words:

    matrix.yaml  "Hierarchies built in the model weren't probed in a matrix, so they aren't accepted."
    slicer.yaml  "A hierarchy built in the model wasn't probed in a slicer, so it isn't accepted."

Those are the two places a report most often puts a hierarchy: a matrix drilled down the rows,
and a slicer the reader expands. A spec writer with a `Geography` or date hierarchy in the model
can use it on a chart and then gets a refusal on the matrix beside it, for no reason in the
format — so this closes a hole in a shipped feature rather than adding surface.

The probe makes **both** claims in one go, the way probe 35 did:

- **What Desktop writes** — you build a matrix and a slicer on the hierarchy by hand (steps 2-3),
  which is the authority on the shape, as probe 16 was for the column chart and table.
- **Whether Desktop takes Blueprint's shape** — `bp apply` builds a matrix and a slicer bound to
  the plain `Sales[Country]` column, and the probe then replaces those projections with the
  hierarchy-level projections **copied from Blueprint's own column chart** on the same page set
  (the control, a shape Desktop accepted in probe 17). Nothing here is hand-written JSON: the
  candidate is literally what `render` emits for a hierarchy, moved into the two wells.

The model gets `hierarchy Geography` (levels Country, then Region) exactly as Desktop wrote it in
probe 16, including its lineageTags.

PREDICTIONS (written before the probe is opened):

 P1  **Desktop's matrix** (step 2) writes one projection per level in `queryState.Rows`, each the
     same `HierarchyLevel` shape probe 16 recorded (`{"Hierarchy": {"Expression": {"SourceRef":
     {"Entity": "Sales"}}, "Hierarchy": "Geography"}}`, `"Level": "Country"` / `"Region"`,
     `queryRef` `Sales.Geography.Country`, `nativeQueryRef` `Geography Country`), in level order.
 P2  Only the **first level is `"active": true`** in Desktop's matrix Rows, as on a column
     chart's Category (probe 16). This is the one I am least sure of: a matrix shows row levels
     as an expandable hierarchy rather than a drill-down, so Desktop may mark **every** level
     active, the way it does in a slicer with two columns (probe 20). Whichever it writes is what
     `render` must write for the matrix, and the candidate below is built the other way on
     purpose so the diff shows it.
 P3  **Desktop's slicer** (step 3) writes both levels in `queryState.Values`, each `"active":
     true` — the shape probe 20 recorded for two plain columns in a slicer — plus its usual
     `expansionStates` view state once you expand a node.
 P4  **Desktop draws and keeps Blueprint's candidates** (the matrix and slicer on page
     "Hierarchy Candidates"): the matrix shows Country rows expandable to Region, the slicer
     shows Country with an expander. The save may add or move the `active` flags — a drill/expand
     state is Desktop's (probe 36's scatter `X`, probe 17's drill flags) — but must not rewrite
     the fields themselves.
 P5  The control column chart on page "Hierarchy Control" draws and drills as in probe 17: this
     page is only here to prove the model and the shape are sound if a candidate fails.
 P6  `bp check` on the saved report reports no `format` findings, and the reader reads every
     projection back (the reader already reads `hierarchy_level` fields, probe 16).
 P7  Otherwise only what any save changes: `$schema` 2.13.0 -> 2.14.0, condition-less auto
     `filterConfig`, `drillFilterOtherVisuals`, `pages.json` `activePageName`.

If they hold: `matrix.rows` (and `matrix.columns`, which is the same well type) and `slicer.field`
gain `hierarchy` in `accepts`, citing this probe; `render` writes the `active` flags the way
Desktop's own two visuals do (P2/P3 decide that), and an acceptance probe then builds a page of
matrices and slicers bound to `Sales[Geography]` straight from a spec, as probe 17 followed 16.

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

PROBE = "NN"  # set to the next free probe number when this is run
GUIDE = ROOT / "guidelines" / "example.yaml"

# `hierarchy Geography` as Desktop wrote it in probe 16 (docs/probes/16-user-hierarchy.diff),
# lineageTags and all, inserted where Desktop put it: after the last column, before the partition.
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

SPECS = {
    "hierarchy-candidates.yaml": """\
page: Hierarchy Candidates
layout: two-up
visuals:
  - {type: header, title: "Matrix and slicer, projections replaced with hierarchy levels"}
  - {type: matrix, id: mx-geography, title: "Matrix rows = Geography (candidate)",
     slots: {rows: "Sales[Country]", values: "[Total Amount]"}}
  - {type: slicer, id: sl-geography, title: "Slicer field = Geography (candidate)",
     slots: {field: "Sales[Country]"}}
""",
    "hierarchy-control.yaml": """\
page: Hierarchy Control
layout: one-up
visuals:
  - {type: header, title: "Control: a column chart on Geography, the shape probe 17 verified"}
  - {type: column, id: ctl-column, title: "Column by Geography",
     slots: {category: "Sales[Geography]", value: "[Total Amount]"}}
""",
}

STEPS = f"""\
# Probe {PROBE}: a model hierarchy in a matrix's Rows and a slicer's Field

The model has a hierarchy **Geography** (Country, then Region), written as Desktop wrote it in
probe 16. There are two Blueprint-built pages:

- **Hierarchy Candidates** — a matrix and a slicer that `bp apply` bound to the plain `Country`
  column, whose projections the probe then replaced with Geography's **hierarchy levels**, copied
  from Blueprint's own column chart. This is the half that asks whether Desktop takes
  Blueprint's shape in these two wells.
- **Hierarchy Control** — a column chart bound to `Sales[Geography]`, a shape Desktop already
  accepted (probe 17). If the candidates fail and this draws, the problem is the well, not the
  model.

Open `Fixture.pbip` in Power BI Desktop. After each step: **Ctrl+S**, then in WSL:

```bash
cd /mnt/c/Users/<user>/blueprint-probes/{PROBE}-hierarchy-matrix-slicer
bash snap.sh "<step>"
```

| # | In Power BI Desktop | Then run |
|---|---|---|
| 1 | Click **Refresh now** on the banner (or **Home -> Refresh**). Visit **Hierarchy Candidates** and **Hierarchy Control** so both draw. Don't click inside a visual. **Ctrl+S**. | `bash snap.sh "01 refresh and save"` |
| 2 | Add a new page, rename it **Desktop Matrix**. Click empty canvas, pick **Matrix**, don't move or resize it. Drag **Geography** itself (the hierarchy, not a level) into **Rows**, and **Total Amount** into **Values**. Write down what the Rows well shows and whether the rows have expand arrows. **Ctrl+S**. | `bash snap.sh "02 desktop matrix on Geography"` |
| 3 | On the same page, click empty canvas, pick **Slicer**, don't move or resize it. Drag **Geography** into **Field**. Expand one value, then write down what the Field well shows. **Ctrl+S**. | `bash snap.sh "03 desktop slicer on Geography"` |

Then tell Claude "probe {PROBE} done", with what you wrote down, and whether the candidate matrix
and slicer on page 1 drew — in particular whether the matrix's rows expanded from Country to
Region, and whether the slicer showed an expander.

What it settles: the shape Desktop writes for a model hierarchy in these two wells, which `active`
flags it marks, and whether it accepts Blueprint's own shape there — the one reason `matrix` and
`slicer` still refuse a hierarchy.
"""


def patch_hierarchy(report: Path) -> list[str]:
    """Replace the matrix's `Rows` and the slicer's `Values` with the control's Geography levels.

    The source is Blueprint's own column chart (`category: "Sales[Geography]"`), so the candidate
    is `render`'s output, not hand-written JSON. The slicer gets every level `"active": true`
    (probe 20's shape for two columns in a slicer); the matrix keeps the column chart's drill
    state (first level only), which prediction P2 is about.
    """
    docs = {}
    for f in sorted(report.glob("definition/pages/*/visuals/*/visual.json")):
        doc = jsonfmt.load(f)
        sid = next((a["value"] for a in doc.get("annotations", [])
                    if a.get("name") == "blueprint.visual"), None)
        if sid:
            docs[sid] = (f, doc)

    levels = docs["ctl-column"][1]["visual"]["query"]["queryState"]["Category"]["projections"]
    changed = []
    for sid, role, all_active in (("mx-geography", "Rows", False),
                                  ("sl-geography", "Values", True)):
        f, doc = docs[sid]
        projections = copy.deepcopy(levels)
        if all_active:
            for p in projections:
                p["active"] = True
        doc["visual"]["query"]["queryState"][role]["projections"] = projections
        f.write_bytes(jsonfmt.dump_bytes(doc))
        active = [i for i, p in enumerate(projections) if p.get("active")]
        changed.append(f"{sid} ({doc['visual']['visualType']}): {role} = "
                       f"{len(projections)} Geography levels, active {active}")
    return changed


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    dest, cache = Path(sys.argv[1]), Path(sys.argv[2])
    make_probe(ROOT / "fixtures" / "02-card-and-chart", dest, STEPS, snap=True)
    tmdl = dest / "Fixture.SemanticModel" / "definition" / "tables" / "Sales.tmdl"
    text = tmdl.read_bytes().decode()
    assert text.count("\tpartition Sales = m") == 1, "fixture 02 changed; re-anchor the insert"
    tmdl.write_bytes(text.replace("\tpartition Sales = m",
                                  HIERARCHY + "\tpartition Sales = m", 1).encode())
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m",
        "model: add hierarchy Geography (as Desktop wrote it in probe 16)")

    specs = dest / "specs"
    specs.mkdir()
    for name, body in SPECS.items():
        (specs / name).write_text(body, encoding="utf-8")
    if bp(["apply", str(specs), "--report", str(dest), "--guidelines", str(GUIDE)]) != 0:
        sys.exit(1)
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m",
        "blueprint: apply specs/ (matrix and slicer on a column, column chart on the hierarchy)")

    print("\n".join(patch_hierarchy(dest / "Fixture.Report")))
    if bp(["manifest", "--report", str(dest), "--guidelines", str(GUIDE)]) != 0:
        sys.exit(1)
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m",
        "probe: candidate Geography levels in the matrix's Rows and the slicer's Values")

    shutil.copy2(cache, dest / "Fixture.SemanticModel" / ".pbi" / "cache.abf")
    print(f"data cache copied from {cache}\nProbe ready: {dest}")
