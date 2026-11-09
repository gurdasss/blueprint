"""Build the Desktop probe for `bp apply` slicer, matrix and two-measure charts (probe 21).

Usage:
    python scripts/probe_apply_slicer_matrix.py <dest folder>

Probe 20 recorded Desktop's queries for a two-field slicer, a matrix (Rows, Columns, two Values)
and column, bar and line charts with two measures, and Blueprint now writes exactly those. This
checks Desktop accepts them as written. `Target Amount` is added to fixture 02's Sales.tmdl as
Desktop wrote it in probe 20, then one spec is applied. The charts list Total Amount before Target
Amount (the order the user added them in probe 20, whose file has Target first): whether Desktop
keeps or reorders them on save settles the order question. All content is invented.
"""

import sys
from pathlib import Path

from _probe import git, make_probe

from blueprint.cli import main as bp

ROOT = Path(__file__).resolve().parent.parent

# As Desktop wrote it in probe 20 (docs/probes/20-slicer-matrix-measures.diff).
MEASURE = ("\tmeasure 'Target Amount' = 600\r\n\t\tformatString: 0\r\n"
           "\t\tlineageTag: 5fd299b6-2d0f-425d-9751-158c2ab18a47\r\n\r\n")

SPEC = """\
page: Slicer & Matrix
layout: grid-2x3
visuals:
  - type: header
    title: Slicer & Matrix
  - type: slicer
    title: Country & Region
    slots: {field: ["Sales[Country]", "Sales[Region]"]}
  - type: matrix
    title: Matrix
    slots: {rows: "Sales[Country]", columns: "Sales[Region]", values: ["[Total Amount]", "[Target Amount]"]}
  - type: column
    title: Column, two measures
    slots: {category: "Sales[Country]", value: ["[Total Amount]", "[Target Amount]"]}
  - type: bar
    title: Bar, two measures
    slots: {category: "Sales[Country]", value: ["[Total Amount]", "[Target Amount]"]}
  - type: line
    title: Line, two measures
    slots: {category: "Sales[Country]", value: ["[Total Amount]", "[Target Amount]"]}
"""

STEPS = """\
# Probe 21: does Desktop accept Blueprint's slicer, matrix and two-measure charts?

The model has the measure **Target Amount** (600). Blueprint added the page **Slicer & Matrix**
(spec in `specs/`): a slicer on Country and Region, a matrix (Rows Country, Columns Region,
Values Total Amount and Target Amount), and column, bar and line charts by Country with both
measures. After each step: **Ctrl+S**, then in WSL:

```bash
cd {wsl_dest}
bash snap.sh "<step>"
```

**Run `bash snap.sh` after every save**: each step must be its own commit.
Never click a value inside the slicer (a selection is saved into the file).

| # | In Power BI Desktop | Then run |
|---|---|---|
| 1 | Open **Fixture.pbip**. Note any error or warning dialog. On **Slicer & Matrix**: is every visual drawn, with its title? Note what the slicer, the matrix and each chart show (for the charts: the legend's entries, in order). Don't change anything. **Ctrl+S**. | `bash snap.sh "01 open and save"` |
| 2 | Click each visual and note, in order, what its wells show (slicer **Field**; matrix **Rows**, **Columns**, **Values**; charts' axis wells). Don't change anything. **Ctrl+S**. | `bash snap.sh "02 wells looked at"` |

Then close Desktop and tell Claude "probe 21 done", with what you saw.
"""

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    dest = Path(sys.argv[1])
    make_probe(ROOT / "fixtures" / "02-card-and-chart", dest,
               STEPS.format(wsl_dest=dest.resolve()), snap=True)
    tmdl = dest / "Fixture.SemanticModel" / "definition" / "tables" / "Sales.tmdl"
    text = tmdl.read_bytes().decode()
    anchor = "\tcolumn Country"
    if anchor not in text:
        sys.exit(f"{tmdl}: no {anchor!r} line to insert the measure before")
    tmdl.write_bytes(text.replace(anchor, MEASURE + anchor, 1).encode())
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "model: add measure Target Amount (as Desktop wrote it in probe 20)")

    specs = dest / "specs"
    specs.mkdir()
    (specs / "slicer-matrix.yaml").write_text(SPEC, encoding="utf-8")
    code = bp(["apply", str(specs / "slicer-matrix.yaml"), "--report", str(dest),
               "--guidelines", str(ROOT / "guidelines" / "example.yaml")])
    if code != 0:
        sys.exit(code)
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "blueprint: apply specs/slicer-matrix.yaml")
    print(f"Probe ready: {dest}")
