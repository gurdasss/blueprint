"""Build the Desktop probe for field shapes the reader doesn't know yet (probe 13).

Usage:
    python scripts/probe_field_shapes.py <dest folder>

The reader understands measures, columns and Sum aggregations (probes 04, 10) and skips any other
projection field. This records two more families so they can be read, not dropped: a date column
used through Desktop's automatic date hierarchy (Year/Quarter/Month/Day), the same column used
plain, and the Average and Count aggregation codes. Fixture 02 has automatic date/time on
(`__PBI_TimeIntelligenceEnabled = 1`) but no date column, so the user adds a calculated one. All
content is invented.
"""

import sys
from pathlib import Path

from _probe import make_probe

ROOT = Path(__file__).resolve().parent.parent

STEPS = """\
# Probe 13: date hierarchy and other aggregations

Open `Fixture.pbip` in Power BI Desktop. After each step: **Ctrl+S**, then in WSL:

```bash
cd /mnt/c/Users/satwa/blueprint-probes/13-field-shapes
bash snap.sh "<step>"
```

| # | In Power BI Desktop | Then run |
|---|---|---|
| 1 | Don't change anything. **Ctrl+S**. | `bash snap.sh "01 open and save"` |
| 2 | In the **Data** pane, click the table **Sales**. Then **Table tools → New column** and type exactly `Order Date = DATE(2026, LEN(Sales[Region]), 1)`, then press **Enter**. Check that **Order Date** appears under Sales, and write down whether it can be expanded into **Date Hierarchy** (Year, Quarter, Month, Day). | `bash snap.sh "02 new date column"` |
| 3 | Add a new page and rename it **Fields**. Click empty canvas, pick **Line chart**, don't move or resize it. **X-axis** = Order Date (drag the field itself, not one level of it), **Y-axis** = Total Amount. Write down what the X-axis well shows. | `bash snap.sh "03 line by date hierarchy"` |
| 4 | In the line chart's **X-axis** well, open the little arrow on the Order Date field and choose **Order Date** (instead of *Date Hierarchy*). | `bash snap.sh "04 line by plain date"` |
| 5 | Click empty canvas, pick **Table**, don't move or resize it. **Columns**: add **Country**, then **Amount**, then **Region**. Then open the arrow on **Sum of Amount** and choose **Average**, and open the arrow on **Region** and choose **Count**. | `bash snap.sh "05 table average and count"` |

Then close Desktop and tell Claude "probe 13 done", with:
- whether Order Date had a Date Hierarchy (step 2) and what the X-axis well showed (step 3),
- the names the table's columns showed in step 5 (for example "Average of Amount", "Count of Region").
"""

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(make_probe(ROOT / "fixtures" / "02-card-and-chart", Path(sys.argv[1]), STEPS, snap=True))
