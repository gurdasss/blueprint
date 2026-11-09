"""Build the Desktop probe for slicer, matrix and charts with several measures (probe 20).

Usage:
    python scripts/probe_slicer_matrix_measures.py <dest folder>

`bp apply` may only ship a visual type whose PBIR shape a probe has verified. This records:

- the slicer's visualType, its field role, a two-field (hierarchy) slicer, and how the
  Dropdown style is stored;
- the matrix's visualType and its Rows, Columns and Values roles, with two measures in Values;
- clustered column, clustered bar and line charts with two measures on the value axis (one
  query role holding two projections, or two roles?).

Like probe 10, the user first adds `Target Amount = 600` to Sales, so there's a second measure.
Uses fixture 02 (table Sales: Region, Country, Amount; measure Total Amount). All content is
invented. The user must not click slicer items: a selection is stored in the visual as data values.
"""

import sys
from pathlib import Path

from _probe import make_probe

ROOT = Path(__file__).resolve().parent.parent

STEPS = """\
# Probe 20: slicer, matrix, and charts with two measures

Open `Fixture.pbip` in Power BI Desktop. After each step: **Ctrl+S**, then in WSL:

```bash
cd {wsl_dest}
bash snap.sh "<step>"
```

Drag fields from the **Data** pane (table **Sales**). If Desktop names a well differently,
**write down the name it shows**. Don't move or resize any visual, and **never click a value
inside the slicer** (a selection would be saved into the file).

| # | In Power BI Desktop | Then run |
|---|---|---|
| 1 | Don't change anything. **Ctrl+S**. | `bash snap.sh "01 open and save"` |
| 2 | In the **Data** pane, click the table **Sales**. **Home → New measure**, type exactly `Target Amount = 600`, press **Enter**. Check **Target Amount** appears under **Sales**. | `bash snap.sh "02 new measure"` |
| 3 | Add a new page and rename it **Probe 20**. | `bash snap.sh "03 add page"` |
| 4 | On **Probe 20**, click empty canvas and pick the plain **Slicer** (the funnel-and-table icon; not *Button slicer* or *Text slicer*). **Field** = Country. | `bash snap.sh "04 slicer"` |
| 5 | On that slicer, drag **Region** into **Field** below Country. | `bash snap.sh "05 slicer two fields"` |
| 6 | Slicer **Format → Visual → Slicer settings → Options → Style** = **Dropdown**. | `bash snap.sh "06 slicer dropdown"` |
| 7 | Click empty canvas, pick **Matrix**. **Rows** = Country. **Values**: Total Amount, then Target Amount below it. | `bash snap.sh "07 matrix"` |
| 8 | On the matrix, **Columns** = Region. | `bash snap.sh "08 matrix columns"` |
| 9 | Click empty canvas, pick **Clustered column chart**. **X-axis** = Country. **Y-axis**: Total Amount, then Target Amount below it. | `bash snap.sh "09 column two measures"` |
| 10 | Click empty canvas, pick **Clustered bar chart**. **Y-axis** = Country. **X-axis**: Total Amount, then Target Amount below it. | `bash snap.sh "10 bar two measures"` |
| 11 | Click empty canvas, pick **Line chart**. **X-axis** = Country. **Y-axis**: Total Amount, then Target Amount below it. | `bash snap.sh "11 line two measures"` |

Visuals may land on top of each other; that's fine, leave them.

Then close Desktop and tell Claude "probe 20 done", with:
- the well names Desktop showed for the slicer and the matrix,
- what the slicer looked like after step 5 (expandable Country > Region?) and step 6,
- what the matrix looked like after step 8 (Region across the top, two values under each?), and
- whether each chart showed two series with a legend (Total Amount and Target Amount).
"""


def wsl_path(dest: Path) -> str:
    return str(dest.resolve())


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    dest = Path(sys.argv[1])
    sys.exit(make_probe(ROOT / "fixtures" / "02-card-and-chart", dest,
                        STEPS.format(wsl_dest=wsl_path(dest)), snap=True))
