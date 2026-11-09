"""Build the Desktop probe for a pie chart's Legend drill-down and Details well (probe 11).

Usage:
    python scripts/probe_pie_legend.py <dest folder>

Probe 08 verified a pie with one Legend column (role `Category`). This records whether several
Legend columns form an ordered drill-down like the column chart's (probe 04), whether Desktop
writes drill state into visual.json when the user drills, and which role the Details well uses.
Uses fixture 02 (table Sales: Region, Country, Amount; measure Total Amount). All content is
invented.
"""

import sys
from pathlib import Path

from _probe import make_probe

ROOT = Path(__file__).resolve().parent.parent

STEPS = """\
# Probe 11: pie chart Legend drill-down and Details

Open `Fixture.pbip` in Power BI Desktop. After each step: **Ctrl+S**, then in WSL:

```bash
cd /mnt/c/Users/satwa/blueprint-probes/11-pie-legend
bash snap.sh "<step>"
```

| # | In Power BI Desktop | Then run |
|---|---|---|
| 1 | Don't change anything. **Ctrl+S**. | `bash snap.sh "01 open and save"` |
| 2 | Add a new page and rename it **Pie**. Click empty canvas, pick **Pie chart**, don't move or resize it. **Legend**: add **Country**, then **Region** below it. **Values** = Total Amount. Write down whether Desktop accepted the second Legend field and whether drill arrows appeared on the visual. | `bash snap.sh "02 pie legend country region"` |
| 3 | If drill arrows appeared: turn on **drill down** (the single down arrow), click one slice so the pie shows that country's regions. Leave it drilled in. If no arrows appeared, write that down and skip this snap. | `bash snap.sh "03 drilled into a country"` |
| 4 | Drill back up (the up arrow). Then in **Legend** remove **Region** (the **x** on the field), and drag **Region** into **Details** instead. | `bash snap.sh "04 region in details"` |

Then close Desktop and tell Claude "probe 11 done", with:
- whether step 2 accepted two Legend fields and showed drill arrows,
- what the pie showed in step 3 (and step 4: how the slices looked with Region in Details), and
- the exact well names Desktop showed for the pie.
"""

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(make_probe(ROOT / "fixtures" / "02-card-and-chart", Path(sys.argv[1]), STEPS, snap=True))
