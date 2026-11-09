"""Build the Desktop probe for `bp apply` output with pie, table and KPI visuals (probe 09).

Usage:
    python scripts/probe_apply_types.py <dest folder>

Probe 05 confirmed Desktop accepts Blueprint's card and column chart as written. This does the
same for the types added from probe 08: it copies fixtures/02-card-and-chart into a git repo
("baseline") and runs `bp apply examples/sales-mix.yaml` on it ("blueprint: apply"). The user
opens the result in Desktop and saves, and the diff shows what Desktop rewrites, if anything.
"""

import sys
from pathlib import Path

from _probe import git, make_probe

from blueprint.cli import main as bp

ROOT = Path(__file__).resolve().parent.parent

STEPS = """\
# Probe 09: does Desktop accept Blueprint's pie, table and KPI?

The report has a new page, **Sales Mix**, created by Blueprint: a KPI "Total by Country"
(value [Total Amount], trend axis Country), a pie chart "Share by Region" and a table "Detail"
(columns Country, Region, Total Amount). After each step: **Ctrl+S**, then in WSL:

```bash
cd /mnt/c/Users/satwa/blueprint-probes/09-apply-types
bash snap.sh "<step>"
```

| # | In Power BI Desktop | Then run |
|---|---|---|
| 1 | Open **Fixture.pbip** and go to the **Sales Mix** page. Note anything odd: an error or warning dialog, a missing or broken visual, a title that's missing. Check that the **KPI** shows a value and a trend line, the **pie** has one slice per region, and the **table** has the columns Country, Region and Total Amount in that order. Don't change anything. **Ctrl+S**. | `bash snap.sh "01 open and save"` |
| 2 | Click each of the three visuals once and look at its wells in the Visualizations pane. Note which field sits in which well. Don't change anything. **Ctrl+S**. | `bash snap.sh "02 inspect wells"` |

Then close Desktop and tell Claude "probe 09 done", with what you saw in steps 1 and 2.
"""

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    dest = Path(sys.argv[1])
    make_probe(ROOT / "fixtures" / "02-card-and-chart", dest, STEPS, snap=True)
    code = bp(["apply", str(ROOT / "examples" / "sales-mix.yaml"), "--report", str(dest),
               "--guidelines", str(ROOT / "guidelines" / "example.yaml")])
    if code != 0:
        sys.exit(code)
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "blueprint: apply examples/sales-mix.yaml")
    print(f"Probe ready: {dest}")
