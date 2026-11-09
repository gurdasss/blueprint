"""Build the Desktop probe for `bp apply` bar, pie and line charts on a model hierarchy (probe 19).

Usage:
    python scripts/probe_apply_hierarchy_charts.py <dest folder>

Probe 18 recorded Desktop's queries for the Geography hierarchy on bar, pie and line charts, and
Blueprint now writes exactly those for `Sales[Geography]`. This checks Desktop accepts them as
written, as probe 17 did for the column chart and table. Geography is added to fixture 02's
Sales.tmdl as Desktop wrote it in probe 16, then two specs are applied (the layout has two main
regions per page). All content is invented.
"""

import sys
from pathlib import Path

from _probe import git, make_probe
from probe_apply_hierarchy import HIERARCHY

from blueprint.cli import main as bp

ROOT = Path(__file__).resolve().parent.parent

SPECS = {
    "geo-bar-pie.yaml": """\
page: Geo Bar & Pie
layout: standard-4-up
visuals:
  - type: bar
    title: Bar by Geography
    slots: {category: "Sales[Geography]", value: "[Total Amount]"}
  - type: pie
    title: Pie by Geography
    slots: {category: "Sales[Geography]", value: "[Total Amount]"}
""",
    "geo-line.yaml": """\
page: Geo Line
layout: standard-4-up
visuals:
  - type: line
    title: Line by Geography
    slots: {category: "Sales[Geography]", value: "[Total Amount]"}
""",
}

STEPS = """\
# Probe 19: does Desktop accept Blueprint's bar, pie and line charts on a hierarchy?

The model has the hierarchy **Geography** (Country, then Region). Blueprint added two pages (specs
in `specs/`): **Geo Bar & Pie** with "Bar by Geography" and "Pie by Geography", and **Geo Line**
with "Line by Geography", each with Geography on its category axis or Legend. After each step:
**Ctrl+S**, then in WSL:

```bash
cd /mnt/c/Users/satwa/blueprint-probes/19-apply-hierarchy-charts
bash snap.sh "<step>"
```

| # | In Power BI Desktop | Then run |
|---|---|---|
| 1 | Open **Fixture.pbip**. Note any error or warning dialog. On both pages: is every chart drawn, with its title, showing **UK** and **FR**? Click each chart and note what its axis or Legend well shows. Don't change anything. **Ctrl+S**. | `bash snap.sh "01 open and save"` |
| 2 | On each of the three charts: turn on drill down, click **UK** to see its regions, then drill back up. **Ctrl+S**. | `bash snap.sh "02 drill and back"` |

Then close Desktop and tell Claude "probe 19 done", with what you saw.
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

    specs = dest / "specs"
    specs.mkdir()
    for name, body in SPECS.items():
        (specs / name).write_text(body, encoding="utf-8")
        code = bp(["apply", str(specs / name), "--report", str(dest),
                   "--guidelines", str(ROOT / "guidelines" / "example.yaml")])
        if code != 0:
            sys.exit(code)
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "blueprint: apply specs/geo-bar-pie.yaml and specs/geo-line.yaml")
    print(f"Probe ready: {dest}")
