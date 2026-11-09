"""Build the Desktop probe for `bp apply` output (probe 05).

Usage:
    python scripts/probe_apply_output.py <dest folder>

Copies fixtures/02-card-and-chart into a git repo ("baseline"), runs
`bp apply examples/sales-overview.yaml` on it ("blueprint: apply"), and writes STEPS.md and
snap.sh. The user opens the result in Desktop and saves. The diffs then show whether Desktop
accepts Blueprint-created pages and visuals as written (derived 20-hex ids, minimal visuals,
README Q4) and what it adds or rewrites.
"""

import sys
from pathlib import Path

from _probe import git, make_probe

from blueprint.cli import main as bp

ROOT = Path(__file__).resolve().parent.parent

STEPS = """\
# Probe 05: does Desktop accept what `bp apply` wrote?

The report has a new page, **Sales Overview**, created by Blueprint: a header textbox, a card
with title "Total" bound to [Total Amount], and a column chart "Sales by Geography" with a
Country → Region drill-down. After each step: **Ctrl+S**, then in WSL:

```bash
cd /mnt/c/Users/satwa/blueprint-probes/05-apply-output
bash snap.sh "<step>"
```

| # | In Power BI Desktop | Then run |
|---|---|---|
| 1 | Open **Fixture.pbip**. Go to the **Sales Overview** page. Note anything odd: an error or warning dialog, a missing or broken visual, the header text, the card's value (should be **500**), whether the chart shows bars, and whether its drill-down buttons work (try drilling into a country, then back up). Don't change anything. **Ctrl+S**. | `bash snap.sh "01 open and save"` |
| 2 | On **Sales Overview**, drag the **card** a little and make it slightly smaller. | `bash snap.sh "02 drag card"` |

Then close Desktop and tell Claude "probe 05 done", with what you saw in step 1.
"""

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    dest = Path(sys.argv[1])
    make_probe(ROOT / "fixtures" / "02-card-and-chart", dest, STEPS, snap=True)
    code = bp(["apply", str(ROOT / "examples" / "sales-overview.yaml"), "--report", str(dest),
               "--guidelines", str(ROOT / "guidelines" / "example.yaml")])
    if code != 0:
        sys.exit(code)
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "blueprint: apply examples/sales-overview.yaml")
    print(f"Probe ready: {dest}")
