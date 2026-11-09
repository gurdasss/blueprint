"""Build the Desktop probe for palette / typography / title formatting (probe 02).

Usage:
    python scripts/probe_formatting.py <source PBIP folder> <dest folder>

Copies the project to <dest> as a git repo with one "baseline" commit and writes
<dest>/STEPS.md. The user makes each formatting change in Power BI Desktop and saves.
Each step targets a different visual (or the page, or the theme), so every change in
`git diff` can be traced back to the step that made it.

Step targets assume the Retail Analysis sample. They're described by page and visual,
not by internal ID, so they can be found in Desktop.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

STEPS = """\
# Probe 02: formatting (palette, typography, titles)

Use exactly the values below; the diff is matched against them.
**Do each step on its own visual. Don't touch anything else.**
"Custom colour" means *More colors…* and typing the hex. "Theme colour" means clicking a
swatch in the colour picker's theme grid.

## Phase 1: one save at the end

| # | Page | Visual | Change in the Format pane | Answers |
|---|---|---|---|---|
| 1 | **New Stores** | the *lower* of the two column charts on the right (single series) | Columns → Color → custom **#E15759** | how a hex data colour is stored |
| 2 | **Overview** | pie chart (top left) | Slices → pick ONE slice → **theme colour, 3rd column, 2nd row** (a lighter shade) | theme-colour references + per-category selectors |
| 3 | **Overview** | column chart, top right ("Total Sales Variance by FiscalMonth…") | Title → font **Segoe UI**, size **18**, **Bold** on, colour custom **#333333** | title typography encoding |
| 4 | **Overview** | the upper card in the middle ("New Stores") | Callout value → font size **28**, colour **theme colour, 1st column, 1st row** | card value font + theme colour |
| 5 | **Overview** | the page itself (click empty canvas) | Canvas background → colour custom **#F3F2F1**, transparency **0%** | page background |
| 6 | **Overview** | header textbox top-left ("Store Sales Overview") | select all the text → font colour **theme colour, 5th column, 1st row** | theme colours inside textbox text |
| 7 | **Overview** | map (bottom left) | General → Effects → Background → colour custom **#FAFAFA** | visual container background |

Then **Save** and tell Claude "phase 1 done". Claude commits the result before phase 2,
so the theme change shows up as its own diff.

## Phase 2: theme (after Claude has committed phase 1)

| # | Where | Change | Answers |
|---|---|---|---|
| 8 | View → Themes | pick the built-in theme **"Classic"** | where the theme lives, and what changes when it switches |

**Save**, close Desktop and tell Claude "phase 2 done".

Note anything Desktop showed you (warnings, banners, a visual that changed by itself).
"""


def git(dest: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(dest), *args], check=True, stdout=subprocess.DEVNULL)


def main(src: Path, dest: Path) -> int:
    if dest.exists():
        sys.exit(f"{dest} already exists; remove it first")
    shutil.copytree(src, dest)
    (dest / "STEPS.md").write_text(STEPS, encoding="utf-8")
    git(dest, "init", "-q")
    git(dest, "config", "core.autocrlf", "false")
    git(dest, "config", "core.filemode", "false")
    git(dest, "config", "core.whitespace", "cr-at-eol")
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "baseline")
    print(f"Probe ready: {dest}\nInstructions: {dest / 'STEPS.md'}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    sys.exit(main(Path(sys.argv[1]), Path(sys.argv[2])))
