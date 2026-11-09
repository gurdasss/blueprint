"""Build the Desktop probe for model hierarchies on bar, pie and line charts (probe 18).

Usage:
    python scripts/probe_bar_pie_hierarchy.py <dest folder>

Probe 16 verified a hierarchy built in the model on a column chart's X-axis and in a table, and
specs may bind one only there. This records the same for a clustered bar chart's Y-axis, a pie's
Legend and (optional) a line chart's X-axis. The Geography hierarchy is added to fixture 02's
Sales.tmdl as Desktop wrote it in probe 16, so the user doesn't have to rebuild it. All content
is invented.
"""

import sys
from pathlib import Path

from _probe import git, make_probe
from probe_apply_hierarchy import HIERARCHY

ROOT = Path(__file__).resolve().parent.parent

STEPS = """\
# Probe 18: the Geography hierarchy on bar, pie and line charts

The model already has the hierarchy **Geography** (Country, then Region) under Sales, as you built
it in probe 16. Open `Fixture.pbip` in Power BI Desktop. After each step: **Ctrl+S**, then in WSL:

```bash
cd /mnt/c/Users/satwa/blueprint-probes/18-bar-pie-hierarchy
bash snap.sh "<step>"
```

For each new visual: click empty canvas first, and don't move or resize it. Drag **Geography**
itself (the hierarchy), not one of its levels.

| # | In Power BI Desktop | Then run |
|---|---|---|
| 1 | Don't change anything. **Ctrl+S**. | `bash snap.sh "01 open and save"` |
| 2 | Add a new page and rename it **Hierarchy**. Add a **Clustered bar chart**: **Y-axis** = Geography, **X-axis** = Total Amount. Note whether drill arrows appear. | `bash snap.sh "02 bar by Geography"` |
| 3 | Add a **Pie chart**: **Legend** = Geography, **Values** = Total Amount. Note whether drill arrows appear. | `bash snap.sh "03 pie by Geography"` |
| 4 | *(Optional.)* Add a **Line chart**: **X-axis** = Geography, **Y-axis** = Total Amount. Note whether drill arrows appear. | `bash snap.sh "04 line by Geography"` |

Then close Desktop and tell Claude "probe 18 done", with what each well showed and whether each
chart could drill down.
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
    print(f"Probe ready: {dest}")
