"""Build the Desktop probe for visual-level aggregation and per-visual data formats (probe 29).

Usage:
    python scripts/probe_aggregate_format.py <dest folder>

Two open items block `docs/plan.md` step 5, where a page spec says more about a field than
which field it is. Both need Desktop's own output, not a guess:

- **Aggregation.** `reader` already reads an implicit aggregate of a column
  (`{"Aggregation": {"Expression": {"Column": …}, "Function": N}}`, probe 10) and knows
  `Function` 0 Sum, 1 Average, 5 Count (probe 13). The codes for **distinct count**, **min** and
  **max** have never been seen, and probe 13 showed the UI's "Count" on a text column is 5, so the
  enum can't be inferred from the names. Probe 13 also showed Desktop keeps a field's **stale
  `queryRef`** after the aggregation changes, so this probe needs aggregations chosen on fresh
  fields to see what Desktop writes from scratch (`queryRef`, `nativeQueryRef`, and whether the
  well's display name is stored at all).

- **Data format.** The vendored Microsoft schema (visualConfiguration 2.8.0) carries a
  per-projection `"format"`: "format string scoped to the visual". Nothing has verified that
  Desktop writes it there, what a format string looks like for the common cases, or whether the
  Format pane writes it per projection or into `visual.objects` instead. Step 5's `format:` key
  depends on the answer, so the probe asks Desktop rather than the schema.

Uses fixture 02 (table Sales: Region, Country, Amount; measure Total Amount, which totals 500).
All content is invented. Nothing here is applied by Blueprint: every change is the user's, in the
UI, so the diff is Desktop's own shape.
"""

import sys
from pathlib import Path

from _probe import make_probe

ROOT = Path(__file__).resolve().parent.parent

STEPS = """\
# Probe 29: visual-level aggregation, and a per-visual data format

Open `Fixture.pbip` in Power BI Desktop. After each step: **Ctrl+S**, then in WSL:

```bash
cd /mnt/c/Users/satwa/blueprint-probes/29-aggregate-format
bash snap.sh "<step>"
```

Each aggregation goes on a **fresh field** (drag the column in again), never by changing the one
before it: probe 13 showed Desktop keeps the old `queryRef` when an aggregation is changed in
place, which is exactly what we must not record as the shape to write.

| # | In Power BI Desktop | Then run |
|---|---|---|
| 1 | Don't change anything. **Ctrl+S**. | `bash snap.sh "01 open and save"` |
| 2 | Add a page, rename it **Agg**. Add a **Table** visual, don't move or resize it. Drag **Region** into **Columns**, then drag **Amount** into **Columns**. Leave Amount as it comes (Desktop should show *Sum of Amount*). | `bash snap.sh "02 table sum"` |
| 3 | Drag **Amount** into **Columns** again (a second copy). On that new one, open its menu (the **v**) and choose **Average**. | `bash snap.sh "03 average"` |
| 4 | Drag **Amount** in again; on the new copy choose **Count**. | `bash snap.sh "04 count"` |
| 5 | Drag **Amount** in again; on the new copy choose **Count (Distinct)**. | `bash snap.sh "05 distinct count"` |
| 6 | Drag **Amount** in again; on the new copy choose **Minimum**. | `bash snap.sh "06 minimum"` |
| 7 | Drag **Amount** in again; on the new copy choose **Maximum**. | `bash snap.sh "07 maximum"` |
| 8 | Drag the text column **Country** into **Columns**; on it choose **Count (Distinct)** (a distinct count of text, to see whether the code differs by data type). | `bash snap.sh "08 distinct count of text"` |
| 9 | Add a **Card** visual to the same page (don't move or resize it). Well: **Fields** = **Total Amount**. | `bash snap.sh "09 card plain"` |
| 10 | With that card selected, open **Format your visual → Callout value** and set **Display units** to **None** and **Value decimal places** to **2**. | `bash snap.sh "10 card decimals"` |
| 11 | In the **Data** pane, click the measure **Total Amount**, then on the ribbon's **Measure tools** set **Format** to **Currency** (`$ English (United States)`). This is a *model* format, for contrast with step 10's visual format. | `bash snap.sh "11 measure currency"` |
| 12 | On the **Agg** page's table, open the **Sum of Amount** field's menu and look for a per-field format option (in some builds: **Format**, or **Cell elements**). If there is one, set it to a currency format. If there is none, skip the snap and say so. | `bash snap.sh "12 per-field format"` |

Then close Desktop and tell Claude "probe 29 done", with:
- what each aggregated field was **called in the well** (for example "Sum of Amount",
  "Count (Distinct) of Amount"), in step order;
- whether step 12 offered a per-field format at all, and what you set;
- anything Desktop refused or renamed on its own.

What the diff is expected to settle:
- the `Function` code for distinct count, min and max, and whether a distinct count of a text
  column differs from one of a number;
- the `queryRef` / `nativeQueryRef` Desktop writes for a freshly aggregated field;
- whether a data format lands on the projection (`"format"`, per the schema), in
  `visual.objects`, or only in TMDL as the measure's `formatString`.
"""

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(make_probe(ROOT / "fixtures" / "02-card-and-chart", Path(sys.argv[1]), STEPS, snap=True))
