"""Build the Desktop probe for `bp apply` output bound to a model hierarchy (probe 17).

Usage:
    python scripts/probe_apply_hierarchy.py <dest folder>

Probe 16 recorded how Desktop binds a hierarchy built in the model, and Blueprint now writes the
same queries for `Sales[Geography]` in a column chart's category and a table's columns. This
checks that Desktop accepts them as written, as probe 09 did for pie, table and KPI. The
Geography hierarchy is added to fixture 02's Sales.tmdl exactly as Desktop wrote it in probe 16,
then `bp apply` runs. All content is invented.
"""

import sys
from pathlib import Path

from _probe import git, make_probe

from blueprint.cli import main as bp

ROOT = Path(__file__).resolve().parent.parent

# docs/probes/16-user-hierarchy.diff, step 02: what Desktop wrote into Sales.tmdl
HIERARCHY = (
    "\thierarchy Geography\r\n"
    "\t\tlineageTag: 1c532aa5-8b4d-4377-a0d9-2f88cbfd471d\r\n"
    "\r\n"
    "\t\tlevel Country\r\n"
    "\t\t\tlineageTag: 96a8fc60-b3a4-4c8d-ba60-fb8924982fbf\r\n"
    "\t\t\tcolumn: Country\r\n"
    "\r\n"
    "\t\tlevel Region\r\n"
    "\t\t\tlineageTag: 10795807-315b-45b3-ab90-5d16ec8ee6e2\r\n"
    "\t\t\tcolumn: Region\r\n"
    "\r\n"
)

SPEC = """\
page: Geography
layout: standard-4-up
visuals:
  - type: column
    title: By Geography
    slots: {category: "Sales[Geography]", value: "[Total Amount]"}
  - type: table
    title: Geography Detail
    slots: {columns: ["Sales[Geography]", "[Total Amount]"]}
"""

STEPS = """\
# Probe 17: does Desktop accept Blueprint's charts bound to a hierarchy?

The model has the hierarchy **Geography** (Country, then Region) under Sales, as you built it in
probe 16. Blueprint added a page **Geography** (spec in `specs/geography.yaml`): a column chart
"By Geography" with Geography on its X-axis, and a table "Geography Detail" with Geography and
Total Amount. After each step: **Ctrl+S**, then in WSL:

```bash
cd /mnt/c/Users/satwa/blueprint-probes/17-apply-hierarchy
bash snap.sh "<step>"
```

| # | In Power BI Desktop | Then run |
|---|---|---|
| 1 | Open **Fixture.pbip**, go to **Geography**. Note any error or warning dialog. Is each visual drawn, with its title? Does the column chart show **UK** and **FR**, and the table the columns Country, Region and Total Amount? Click each visual and note what its wells show (for example "Geography" with Country and Region under it). Don't change anything. **Ctrl+S**. | `bash snap.sh "01 open and save"` |
| 2 | On **By Geography**, turn on drill down, click **UK** so it shows UK's regions, then drill back up. **Ctrl+S**. | `bash snap.sh "02 drill and back"` |

Then close Desktop and tell Claude "probe 17 done", with what you saw.
"""

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    dest = Path(sys.argv[1])
    make_probe(ROOT / "fixtures" / "02-card-and-chart", dest, STEPS, snap=True)

    tmdl = dest / "Fixture.SemanticModel" / "definition" / "tables" / "Sales.tmdl"
    text = tmdl.read_bytes().decode()
    anchor = "\tpartition Sales = m"
    if anchor not in text:
        sys.exit(f"{tmdl}: no {anchor!r} line to insert the hierarchy before")
    tmdl.write_bytes(text.replace(anchor, HIERARCHY + anchor, 1).encode())
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "model: add hierarchy Geography (as Desktop wrote it in probe 16)")

    spec = dest / "specs" / "geography.yaml"
    spec.parent.mkdir()
    spec.write_text(SPEC, encoding="utf-8")
    code = bp(["apply", str(spec), "--report", str(dest), "--guidelines", str(ROOT / "guidelines" / "example.yaml")])
    if code != 0:
        sys.exit(code)
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "blueprint: apply specs/geography.yaml")
    print(f"Probe ready: {dest}")
