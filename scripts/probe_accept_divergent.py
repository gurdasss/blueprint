"""Build the Desktop probe that saves what `bp theme` and `bp apply` wrote for divergent colours
and a table's `gradient:` (probe 45).

Usage:
    python scripts/probe_accept_divergent.py <dest folder> <probe 43 folder>

Probe 44 showed, with gradients built **by hand**, that a theme's `minimum`/`center`/`maximum` are
the defaults of a new gradient and that a saved gradient keeps hex literals in `objects.values[]`.
Blueprint now writes both from the guidelines (`palette.minimum|center|maximum`; a spec column
`{field: ..., aggregate: sum, gradient: 2|3}`), which is a different claim: that Desktop accepts
**what Blueprint wrote**. Same bar as probes 24, 30, 33 and 43. Nothing here is patched by hand.
The base is probe 43's final report (the financial demo PBIP; its Blueprint-written theme already
has the sentiment colours). Blueprint runs `bp theme` with `guidelines.yaml` (set C below) and
`bp apply` builds one page, **Gradients**: a table with Country, Segment, Sum of Sales (two-colour
gradient) and Sum of Profit (three-colour gradient), the same two shapes probe 44 saved by hand.

  Set C (first build)   minimum #8E0152 magenta, center #FFFFBF pale yellow, maximum #276419 green
  Set D (after the save) minimum #2166AC blue,   center #FDDBC7 peach,       maximum #B2182B red

PREDICTIONS (written before the probe is opened):

 E1  Desktop opens the report with no error. The Gradients table draws as probe 44's did: Sum of
     Sales runs magenta (lowest) to green (highest) with no yellow, Sum of Profit runs magenta
     through pale yellow to green. The Customize-theme dialog shows set C under Divergent colors.
 E2  Ctrl+S keeps both `objects.values` entries as Blueprint wrote them: the `FillRule` input,
     `linearGradient2` and `linearGradient3` (`min`, `mid`, `max`), the hex literals,
     `nullColoringStrategy asZero` and the selector. At most Desktop bumps a file's `$schema`
     2.13.0 -> 2.14.0, adds its usual filterConfig and rewrites `pages.json` `activePageName`;
     it drops or reorders nothing inside `values`. `blueprint-theme.json` is kept byte for byte.
 E3  Re-running `bp theme` and `bp apply` on the saved report with the same guidelines: No
     changes. `bp check`: 0 errors, 0 warnings, the note "2 colour expression(s) not checked".
 E4  After editing guidelines.yaml to set D, `bp apply` rewrites both gradients **in place** (two
     entries, not four; the note `gradient Sum(financials.Sales), Sum(financials.Profit)`) and
     `bp theme` rewrites the theme's three keys. Desktop, reloaded through the bridge, draws the
     table in set D (blue to red; peach in the middle of the profit column): the saved gradients
     follow because Blueprint rewrote them, not because the theme changed (probe 44).
 E5  After a Ctrl+S of that state, Desktop keeps set D as written and the diff touches only the
     colours Blueprint changed (and the theme file's three values).

All content is the demo's financial sample.
"""

import shutil
import sys
import tempfile
from pathlib import Path

from _probe import git, make_probe

from blueprint.cli import main as bp

ROOT = Path(__file__).resolve().parent.parent

DIVERGENT = """\
  minimum: "#8E0152"    # probe 45 set C: magenta
  center: "#FFFFBF"     # pale yellow
  maximum: "#276419"    # green
"""

SPEC = """\
# Probe 45: one table with both gradient shapes (two colours, and three with a middle colour).
page: Gradients
layout: solo-wide
visuals:
  - type: header
    title: Gradients
  - type: table
    id: gradients
    title: Sales and Profit by Country and Segment
    slots:
      columns:
        - "financials[Country]"
        - "financials[Segment]"
        - { field: "financials[Sales]", aggregate: sum, gradient: 2 }
        - { field: "financials[Profit]", aggregate: sum, gradient: 3 }
"""

STEPS = """\
# Probe 45: does Desktop keep the divergent colours and gradients Blueprint wrote?

Blueprint wrote the theme (`minimum` #8E0152 magenta, `center` #FFFFBF pale yellow, `maximum`
#276419 green, from `palette.minimum|center|maximum` in guidelines.yaml) and built the page
**Gradients**: a table whose Sum of Sales column has a two-colour gradient and Sum of Profit a
three-colour one. Claude opens the report through the bridge and captures it. You only:

1. When Desktop shows the report, look at the **Gradients** page: how do the two columns look?
   Don't click anything inside the table. Click **Refresh now** if it asks.
2. **View -> Themes -> Customize current theme**, find **Divergent colors**, tell Claude the three
   colours, then **Cancel**.
3. **Ctrl+S**.

Tell Claude when it is saved. Claude then re-runs Blueprint (same guidelines, then new colours),
reloads and captures; it asks for one more Ctrl+S at the end.
"""

if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    dest, base = Path(sys.argv[1]), Path(sys.argv[2])
    cache = base / "financial.SemanticModel" / ".pbi" / "cache.abf"
    if not cache.is_file():
        sys.exit(f"no data cache at {cache}")
    with tempfile.TemporaryDirectory() as stage:
        shutil.copytree(base, stage + "/src",
                        ignore=shutil.ignore_patterns(".git", ".pbi", "STEPS.md", "snap.sh"))
        make_probe(Path(stage) / "src", dest, STEPS, snap=True)

    guidelines = (dest / "guidelines.yaml").read_text(encoding="utf-8")
    marker = '  bad: "#B3124B"        # crimson\n'
    if marker not in guidelines:
        sys.exit("probe 43's guidelines.yaml changed: put the divergent colours after palette.bad by hand")
    (dest / "guidelines.yaml").write_text(guidelines.replace(marker, marker + DIVERGENT), encoding="utf-8")
    (dest / "specs" / "gradients.yaml").write_text(SPEC, encoding="utf-8")
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "inputs: guidelines.yaml (with set C divergent colours) and specs/gradients.yaml")

    guide = str(dest / "guidelines.yaml")
    if bp(["theme", "--report", str(dest), "--guidelines", guide]) != 0:
        sys.exit(1)
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "blueprint: theme with divergent colours")
    if bp(["apply", str(dest / "specs" / "gradients.yaml"), "--report", str(dest), "--guidelines", guide]) != 0:
        sys.exit(1)
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "blueprint: apply specs/gradients.yaml")

    (dest / "financial.SemanticModel" / ".pbi").mkdir(exist_ok=True)
    shutil.copy2(cache, dest / "financial.SemanticModel" / ".pbi" / "cache.abf")
    print(f"data cache copied from {cache}\nProbe ready: {dest}")
