"""Build the Desktop probe for theming the new card's text (probe 15).

Usage:
    python scripts/probe_card_theme.py <dest folder>

Two open items, one Desktop session:

- probe 07: does a custom theme's `textClasses.callout` (which `bp theme` writes from
  typography.callout) reach the new card's (cardVisual) value? The base theme points the value
  at that text class.
- card_label: can a custom theme set the card's Category label through
  `visualStyles.cardVisual["*"].label`, where the base theme sets its size (12)? And does a custom
  entry there merge with the base one (position, textClass, the card's outline) or replace it?

The script runs `bp theme` on a copy of fixture 02 with probe-only guidelines (callout Segoe UI
Light 32), commits, then adds a hand-written cardVisual label entry (Arial 14) to the theme file
and commits again. Both differ visibly from Desktop's defaults (value Segoe UI Semibold 21, label
Segoe UI 12; probe 07). All content is invented.
"""

import sys
from pathlib import Path

from _probe import git, make_probe

from blueprint.cli import main as bp
from blueprint.pbir import jsonfmt

ROOT = Path(__file__).resolve().parent.parent

GUIDELINES = """\
name: Probe 15
version: 1
typography:
  callout: { font: Segoe UI Light, size: 32 }
"""

# Written by hand: what bp theme would write for typography.card_label if Desktop honours it.
# The base theme's entry is [{"$id": "default", "position": "aboveValue", "fontSize": 12,
# "textClass": "label", "fontColor": …}]; this one sets only size and family, so the diff of what
# Desktop shows tells merge from replace.
CARD_LABEL = {"$id": "default", "fontSize": 14, "fontFamily": "'Arial', helvetica, arial, sans-serif"}

STEPS = """\
# Probe 15: theming the new card's value and label

Blueprint wrote a custom theme (**Probe 15**) and then a hand-made entry for the card's label was
added to it. Expected, if Desktop honours both, on the **Overview** page's card **Total**:

- **Callout value:** Segoe UI Light, 32 (Desktop's default: Segoe UI Semibold, 21)
- **Category label:** Arial, 14 (default: Segoe UI, 12)

After each step: **Ctrl+S**, then in WSL:

```bash
cd /mnt/c/Users/satwa/blueprint-probes/15-card-theme
bash snap.sh "<step>"
```

| # | In Power BI Desktop | Then run |
|---|---|---|
| 1 | Open **Fixture.pbip**, go to **Overview**. Note any error or warning dialog. Look at the card **Total**: does the value look thin and large, and the label look like Arial? Is the label still **above** the value, and does the card still have its thin grey **border**? Don't change anything. **Ctrl+S**. | `bash snap.sh "01 open and save"` |
| 2 | Select the card → **Format visual**. Write down the **font and size** shown under **Callout value**, and under **Category label**. Don't change anything. **Ctrl+S**. | `bash snap.sh "02 read format pane"` |
| 3 | Select the column chart and look at its axis labels: do they still look like before (Segoe UI, not Arial)? Don't change anything. **Ctrl+S**. | `bash snap.sh "03 chart unchanged"` |

Then close Desktop and tell Claude "probe 15 done", with what you saw in each step.
"""

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    dest = Path(sys.argv[1])
    make_probe(ROOT / "fixtures" / "02-card-and-chart", dest, STEPS, snap=True)
    guide = dest / "probe-guidelines.yaml"
    guide.write_text(GUIDELINES, encoding="utf-8")
    code = bp(["theme", "--report", str(dest), "--guidelines", str(guide)])
    if code != 0:
        sys.exit(code)
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "blueprint: theme (callout Segoe UI Light 32)")

    path = dest / "Fixture.Report" / "StaticResources" / "RegisteredResources" / "blueprint-theme.json"
    doc = jsonfmt.load(path)
    doc.setdefault("visualStyles", {})["cardVisual"] = {"*": {"label": [CARD_LABEL]}}
    path.write_bytes(jsonfmt.dump_bytes(doc))
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "probe: add visualStyles.cardVisual label (Arial 14) to the theme")
    print(f"Probe ready: {dest}")
