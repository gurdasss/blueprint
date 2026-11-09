"""Build the Desktop probe for a hierarchy built in the model (probe 16).

Usage:
    python scripts/probe_user_hierarchy.py <dest folder>

Probe 13 showed how a visual binds Desktop's automatic date hierarchy (`HierarchyLevel` over a
`PropertyVariationSource`). A hierarchy the user builds in the Data pane is presumably bound
differently, and the reader skips it. This records the hierarchy in TMDL, a visual bound to the
whole hierarchy, and a visual bound to one level of it. Uses fixture 02 (table Sales: Region,
Country, Amount; measure Total Amount). All content is invented.
"""

import sys
from pathlib import Path

from _probe import make_probe

ROOT = Path(__file__).resolve().parent.parent

STEPS = """\
# Probe 16: a hierarchy built in the model

Open `Fixture.pbip` in Power BI Desktop. After each step: **Ctrl+S**, then in WSL:

```bash
cd /mnt/c/Users/satwa/blueprint-probes/16-user-hierarchy
bash snap.sh "<step>"
```

| # | In Power BI Desktop | Then run |
|---|---|---|
| 1 | Don't change anything. **Ctrl+S**. | `bash snap.sh "01 open and save"` |
| 2 | In the **Data** pane, expand **Sales**. Right-click **Country** → **Create hierarchy**. Right-click the new **Country Hierarchy** → **Rename**, and call it **Geography**. Then right-click **Region** → **Add to hierarchy** → **Geography**. Check that Geography now lists **Country**, then **Region**. | `bash snap.sh "02 create hierarchy Geography"` |
| 3 | Add a new page and rename it **Hierarchy**. Click empty canvas, pick **Clustered column chart**, don't move or resize it. **X-axis** = drag **Geography** itself (the hierarchy, not one level). **Y-axis** = Total Amount. Write down what the X-axis well shows and whether drill arrows appear. | `bash snap.sh "03 column by Geography"` |
| 4 | Click empty canvas, pick **Table**, don't move or resize it. Expand **Geography** in the Data pane and drag only its **Region** level into **Columns**, then add **Total Amount**. Write down what the Columns well shows (for example "Region" or "Geography Region"). | `bash snap.sh "04 table by one level"` |

Then close Desktop and tell Claude "probe 16 done", with what you wrote down in steps 2-4.
"""

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(make_probe(ROOT / "fixtures" / "02-card-and-chart", Path(sys.argv[1]), STEPS, snap=True))
