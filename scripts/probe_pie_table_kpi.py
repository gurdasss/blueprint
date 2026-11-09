"""Build the Desktop probe for three new visual types: pie, table and KPI (probe 08).

Usage:
    python scripts/probe_pie_table_kpi.py <dest folder>

`bp apply` may only ship a visual type whose PBIR shape a probe has verified (blueprint/visuals/).
This probe records, for each type, the visualType string, its query roles, how several fields in
one role are ordered, its default size, and what else Desktop adds (sort, filters), the way probe
04 did for the card and column chart. Uses fixture 02 (table Sales: columns Region, Country and
Amount; measure Total Amount). All content is invented.

The model has no date column and no target measure, so the KPI gets a value and a trend axis only.
A target would mean adding a measure or an implicit aggregation, which is a separate binding shape.
"""

import sys
from pathlib import Path

from _probe import make_probe

ROOT = Path(__file__).resolve().parent.parent

STEPS = """\
# Probe 08: pie, table and KPI

Open `Fixture.pbip` in Power BI Desktop. After each step: **Ctrl+S**, then in WSL:

```bash
cd /mnt/c/Users/satwa/blueprint-probes/08-pie-table-kpi
bash snap.sh "<step>"
```

Drag fields from the **Data** pane (table **Sales**) into the wells named below. If Desktop
names a well differently, **write down the name it shows**.

| # | In Power BI Desktop | Then run |
|---|---|---|
| 1 | Don't change anything. **Ctrl+S**. (Records what Desktop rewrites on a plain open and save.) | `bash snap.sh "01 open and save"` |
| 2 | Add a new page (**+** at the bottom). Rename it **Visuals**. | `bash snap.sh "02 add page Visuals"` |
| 3 | On **Visuals**, click empty canvas, then pick **Pie chart** in the Visualizations pane. Don't move or resize it. Wells: **Legend** = Region, **Values** = Total Amount. | `bash snap.sh "03 pie"` |
| 4 | Click empty canvas, pick **Table**. Don't move or resize it. **Columns**: add Region, then Country, then Total Amount, in that order. | `bash snap.sh "04 table"` |
| 5 | Click empty canvas, pick **KPI**. Don't move or resize it. **Value** = Total Amount, **Trend axis** = Country. Leave **Target** empty. | `bash snap.sh "05 kpi"` |
| 6 | Table: drag **Country** above **Region** in the **Columns** well (reorder only). | `bash snap.sh "06 table reorder"` |

Then close Desktop and tell Claude "probe 08 done", with:
- the well names Desktop showed for each visual (step 3 to 5), and
- anything that didn't go as described (for example, a visual Desktop placed on top of another).
"""

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(make_probe(ROOT / "fixtures" / "02-card-and-chart", Path(sys.argv[1]), STEPS, snap=True))
