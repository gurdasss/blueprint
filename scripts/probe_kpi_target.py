"""Build the Desktop probe for the KPI's Target well (probe 10).

Usage:
    python scripts/probe_kpi_target.py <dest folder>

Probe 08 verified the KPI's Value (`Indicator`) and Trend axis (`TrendLine`) roles but left
Target unbound, because fixture 02's model has no target measure. Here the user adds one in
Desktop, binds it, and then swaps it for a plain column. This records the Target role's name,
the shape of the new measure in TMDL, and whether Target accepts a column (and if so, how
Desktop stores the implicit aggregation). Uses fixture 02 (table Sales: Region, Country, Amount;
measure Total Amount, which totals 500). All content is invented.
"""

import sys
from pathlib import Path

from _probe import make_probe

ROOT = Path(__file__).resolve().parent.parent

STEPS = """\
# Probe 10: the KPI's Target well

Open `Fixture.pbip` in Power BI Desktop. After each step: **Ctrl+S**, then in WSL:

```bash
cd /mnt/c/Users/satwa/blueprint-probes/10-kpi-target
bash snap.sh "<step>"
```

| # | In Power BI Desktop | Then run |
|---|---|---|
| 1 | Don't change anything. **Ctrl+S**. | `bash snap.sh "01 open and save"` |
| 2 | In the **Data** pane, click the table **Sales**. Then **Home → New measure** and type exactly `Target Amount = 600`, then press **Enter**. Check that **Target Amount** appears under **Sales**. | `bash snap.sh "02 new measure"` |
| 3 | Add a new page and rename it **KPI**. On it, click empty canvas, pick **KPI**, and don't move or resize it. Wells: **Value** = Total Amount, **Trend axis** = Country, **Target** = Target Amount. | `bash snap.sh "03 kpi with target"` |
| 4 | On that KPI, remove **Target Amount** from **Target** (the **x** on the field) and drag the column **Amount** into **Target** instead. If Desktop refuses, write that down and skip the snap. | `bash snap.sh "04 target as column"` |

Then close Desktop and tell Claude "probe 10 done", with:
- what the KPI showed in step 3 (the value, the goal and whether it was red or green), and
- what Desktop showed in the **Target** well in step 4 (for example "Sum of Amount"), or that it refused.
"""

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(make_probe(ROOT / "fixtures" / "02-card-and-chart", Path(sys.argv[1]), STEPS, snap=True))
