"""Build the Desktop probe that saves bp apply's chart variants and options (probe 24).

Usage:
    python scripts/probe_apply_variants.py <dest folder>

Probes 22 and 23 verified candidate shapes by Desktop drawing them, but an untouched open isn't
dirty, so Desktop never saved them. Here `bp apply` builds every shape they verified, from the
shipped contracts, on a fresh copy of fixture 02 with no data cache. The user clicks Refresh now
(which dirties the report) and saves, so Desktop's save diff shows what it keeps and adds.
`Target Amount` is added as in probe 20. All content is invented.
"""

import sys
from pathlib import Path

from _probe import git, make_probe
from probe_apply_slicer_matrix import MEASURE

from blueprint.cli import main as bp

ROOT = Path(__file__).resolve().parent.parent

C = '"Sales[Country]"'
DRILL = '["Sales[Country]", "Sales[Region]"]'
TWO = '["[Total Amount]", "[Target Amount]"]'
TOTAL = '"[Total Amount]"'

SPECS = {
    "saved-variants-1.yaml": f"""\
page: Saved Variants 1
layout: grid-2x3
visuals:
  - {{type: header, title: Saved Variants 1}}
  - {{type: stacked-column, title: Stacked column legend, slots: {{category: {C}, value: {TOTAL}, legend: "Sales[Region]"}}}}
  - {{type: stacked-column, title: Stacked column two measures labels, options: {{labels: on}}, slots: {{category: {C}, value: {TWO}}}}}
  - {{type: stacked-column-100, title: 100% stacked drill-down, slots: {{category: {DRILL}, value: {TOTAL}}}}}
  - {{type: stacked-column-100, title: 100% two measures labels legend top, options: {{labels: on, legend: top}}, slots: {{category: {C}, value: {TWO}}}}}
  - {{type: stacked-bar, title: Stacked bar drill-down, slots: {{category: {DRILL}, value: {TOTAL}}}}}
  - {{type: stacked-bar, title: Stacked bar two measures labels legend left, options: {{labels: on, legend: left}}, slots: {{category: {C}, value: {TWO}}}}}
""",
    "saved-variants-2.yaml": f"""\
page: Saved Variants 2
layout: grid-2x3
visuals:
  - {{type: header, title: Saved Variants 2}}
  - {{type: donut, title: Donut drill-down, slots: {{category: {DRILL}, value: {TOTAL}}}}}
  - {{type: donut, title: Donut details, slots: {{category: {C}, value: {TOTAL}, details: "Sales[Region]"}}}}
  - {{type: area, title: Area legend, slots: {{category: {C}, value: {TOTAL}, legend: "Sales[Region]"}}}}
  - {{type: area, title: Area two measures, slots: {{category: {C}, value: {TWO}}}}}
  - {{type: column, title: Column labels legend right, options: {{labels: on, legend: right}}, slots: {{category: {C}, value: {TWO}}}}}
  - {{type: slicer, title: Dropdown slicer, options: {{style: dropdown}}, slots: {{field: {C}}}}}
""",
}

STEPS = """\
# Probe 24: Desktop's save of bp apply's chart variants and options

Blueprint built **Saved Variants 1** and **Saved Variants 2**. Claude opens the report through the
bridge and commits each step; you only:

1. Click **Refresh now** on the banner, then **Ctrl+S**.

Never click a value inside a visual.
"""

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    dest = Path(sys.argv[1])
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
    git(dest, "commit", "-q", "-m", "blueprint: apply specs/ (saved-variants-1.yaml, saved-variants-2.yaml)")
    print(f"Probe ready: {dest}")
