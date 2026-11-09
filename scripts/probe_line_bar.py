"""Build the Desktop probe for line and bar charts (probe 12).

Usage:
    python scripts/probe_line_bar.py <dest folder>

`bp apply` may only ship a visual type whose PBIR shape a probe has verified. This records the
line chart's and clustered bar chart's visualType, query roles (including a bar drill-down and a
line Legend), default size and what Desktop adds, as probe 08 did for pie, table and KPI. Uses
fixture 02 (table Sales: Region, Country, Amount; measure Total Amount). All content is invented.
"""

import sys
from pathlib import Path

from _probe import make_probe

ROOT = Path(__file__).resolve().parent.parent

STEPS = """\
# Probe 12: line and bar charts

Open `Fixture.pbip` in Power BI Desktop. After each step: **Ctrl+S**, then in WSL:

```bash
cd /mnt/c/Users/satwa/blueprint-probes/12-line-bar
bash snap.sh "<step>"
```

Drag fields from the **Data** pane (table **Sales**). If Desktop names a well differently,
**write down the name it shows**.

| # | In Power BI Desktop | Then run |
|---|---|---|
| 1 | Don't change anything. **Ctrl+S**. | `bash snap.sh "01 open and save"` |
| 2 | Add a new page and rename it **Charts**. | `bash snap.sh "02 add page Charts"` |
| 3 | On **Charts**, click empty canvas, pick **Line chart**. Don't move or resize it. **X-axis** = Country, **Y-axis** = Total Amount. | `bash snap.sh "03 line"` |
| 4 | Click empty canvas, pick **Clustered bar chart** (horizontal bars; not *Stacked*). Don't move or resize it. **Y-axis**: add **Country**, then **Region** below it. **X-axis** = Total Amount. | `bash snap.sh "04 clustered bar"` |
| 5 | Select the **line chart** and drag **Region** into its **Legend** well. | `bash snap.sh "05 line legend"` |

Then close Desktop and tell Claude "probe 12 done", with:
- the well names Desktop showed for each chart,
- whether the bar chart showed drill arrows after step 4, and
- what the line chart looked like after step 5 (for example, one line per region).
"""

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(make_probe(ROOT / "fixtures" / "02-card-and-chart", Path(sys.argv[1]), STEPS, snap=True))
