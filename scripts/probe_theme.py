"""Build the Desktop probe for `bp theme` (probe 06).

Usage:
    python scripts/probe_theme.py <dest folder>

Copies fixtures/02-card-and-chart into a git repo ("baseline"), then runs the full alignment
sequence, `bp apply` + `bp fmt` + `bp theme` with guidelines/example.yaml, as one commit. The
user opens it in Desktop, looks, and saves. The diff shows whether Desktop accepts a
Blueprint-written theme file as written, and the user reports whether the report looks themed.
"""

import sys
from pathlib import Path

from _probe import git, make_probe

from blueprint.cli import main as bp

ROOT = Path(__file__).resolve().parent.parent
GUIDE = str(ROOT / "guidelines" / "example.yaml")

STEPS = """\
# Probe 06: does Desktop accept the theme `bp theme` wrote?

Blueprint ran `apply`, `fmt` and `theme` with the example guidelines. The report should now use
the custom theme **Example Corp Reporting Standard**: data colours starting with the steel
blue **#4E79A7**, then orange **#F28E2B**, red, teal and green; text colour **#333333**; and
visual titles in **Segoe UI Semibold, 18pt**.

| # | In Power BI Desktop | Then run |
|---|---|---|
| 1 | Open **Fixture.pbip**. Note any error, warning or banner. On **Sales Overview** and **Overview**: are the column bars **steel blue (#4E79A7)**? Are chart titles larger (18pt) and semibold? Don't change anything. **Ctrl+S**. | `bash snap.sh "01 open and save"` |
| 2 | **View → Themes → Customize current theme**. Note the theme **name** shown and the first few **theme colours**. Then click **Cancel** (don't apply). **Ctrl+S**. | `bash snap.sh "02 customize dialog (cancelled)"` |

Then close Desktop and tell Claude "probe 06 done", with what you saw.

```bash
cd /mnt/c/Users/satwa/blueprint-probes/06-theme
```
"""

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    dest = Path(sys.argv[1])
    make_probe(ROOT / "fixtures" / "02-card-and-chart", dest, STEPS, snap=True)
    for args in (["apply", str(ROOT / "examples" / "sales-overview.yaml")], ["fmt"], ["theme"]):
        code = bp([*args, "--report", str(dest), "--guidelines", GUIDE])
        if code != 0:
            sys.exit(code)
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "blueprint: apply + fmt + theme (example guidelines)")
    print(f"Probe ready: {dest}")
