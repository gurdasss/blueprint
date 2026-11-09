"""Build the Desktop probe for the new card visual's fonts (probe 07).

Usage:
    python scripts/probe_card_fonts.py <dest folder>

Desktop's current card is `cardVisual` (probe 04). Its formatting objects differ from the legacy
`card`: the base theme styles `value` (the callout), `label` (the caption) and `referenceLabel*`,
each entry tagged `"$id": "default"`. This probe shows how Desktop stores those font settings in
visual.json, and which theme default the value follows, so typography and theme rules can cover
the card. Uses fixture 02, whose Overview page has a cardVisual titled "Total".
"""

import sys
from pathlib import Path

from _probe import make_probe

ROOT = Path(__file__).resolve().parent.parent

STEPS = """\
# Probe 07: the new card's fonts (cardVisual)

Page **Overview**, the card titled **Total** (it shows 500). After each step: **Ctrl+S**, then in WSL:

```bash
cd /mnt/c/Users/satwa/blueprint-probes/07-card-fonts
bash snap.sh "<step>"
```

| # | In Power BI Desktop (select the card → Format visual) | Then run |
|---|---|---|
| 1 | Don't change anything. Open **Callout value** (it may be called *Value* or *Values*) and **write down** the font, size and colour it shows. Also open the **Label** (category label) section and write down its size. **Ctrl+S**. | `bash snap.sh "01 open and save (read defaults)"` |
| 2 | **Callout value**: font **Arial**, size **28**, **Bold** on, colour custom **#E15759**. | `bash snap.sh "02 callout value font"` |
| 3 | **Label** (category label): size **14**. | `bash snap.sh "03 label size"` |
| 4 | **Title** (under General / Title): size **16**. | `bash snap.sh "04 title size"` |

Then close Desktop and tell Claude "probe 07 done", with the defaults you wrote down in step 1
and the exact section names Desktop used.
"""

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(make_probe(ROOT / "fixtures" / "02-card-and-chart", Path(sys.argv[1]), STEPS, snap=True))
