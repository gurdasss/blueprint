"""Build the Desktop probe for `bp apply` (probe 04): a report built from scratch.

Usage:
    python scripts/probe_apply.py <dest folder>

Creates an empty git repo with STEPS.md and snap.sh. The user builds a brand-new report in
Power BI Desktop, saving and running `bash snap.sh "<step>"` after each step, so every step is
its own commit. This answers README "Learning the PBIP format" Q1-Q11 and produces committable
fixtures: everything in it, data included, is invented.
"""

import sys
from pathlib import Path

from _probe import make_empty_probe

STEPS = """\
# Probe 04: building a report from scratch (for `bp apply`)

Everything here is invented, so the result can be committed as test fixtures.
Use the exact names below. **After each step: Ctrl+S, then in WSL run the snap command shown.**

```bash
cd /mnt/c/Users/satwa/blueprint-probes/04-apply
bash snap.sh "<step>"      # e.g. bash snap.sh "01 blank report"
```

If something doesn't match what's described (a dialog, a missing option, an error), write it
down and carry on. That's useful too.

| # | In Power BI Desktop | Then run |
|---|---|---|
| 1 | **File → New** (blank report). **File → Save as** → type **Power BI project (.pbip)** → save into this folder as **Fixture**. | `bash snap.sh "01 blank report"` |
| 2 | Add a page with the **+** at the bottom. | `bash snap.sh "02 add page"` |
| 3 | Rename the pages: "Page 1" → **Overview**, "Page 2" → **Detail** (double-click the tab). | `bash snap.sh "03 rename pages"` |
| 4 | Drag the **Detail** tab to the left of **Overview**. | `bash snap.sh "04 reorder pages"` |
| 5 | **Home → Enter data**. Table name **Sales**, columns **Country**, **Region**, **Amount**, rows: `UK, North, 100` / `UK, South, 200` / `FR, East, 150` / `FR, West, 50`. **Load**. Then select the Sales table → **New measure**: `Total Amount = SUM(Sales[Amount])`. | `bash snap.sh "05 data and measure"` |
| 6 | On **Overview**: add a **Card**, drag **Total Amount** into it. | `bash snap.sh "06 add card"` |
| 7 | Move the card to the top-left corner and make it a bit bigger. | `bash snap.sh "07 move and resize card"` |
| 8 | Card → Format → turn **Title** on, title text **Total**. | `bash snap.sh "08 card title"` |
| 9 | On **Overview**: add a **Clustered column chart**. X-axis: **Country**, then **Region** under it (a drill-down). Y-axis: **Total Amount**. | `bash snap.sh "09 column chart with drill-down"` |
| 10 | Select the card, **Ctrl+C**, **Ctrl+V** (a copy appears). | `bash snap.sh "10 paste card"` |
| 11 | Delete the pasted copy. | `bash snap.sh "11 delete visual"` |
| 12 | Delete the **Detail** page (right-click the tab → Delete page). | `bash snap.sh "12 delete page"` |

Then close Desktop and tell Claude "probe 04 done", plus anything you noticed.
"""

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(make_empty_probe(Path(sys.argv[1]), STEPS))
