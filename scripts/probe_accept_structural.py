"""Build the Desktop probe that saves what `bp theme` wrote for the structural colours (probe 49).

Usage:
    python scripts/probe_accept_structural.py <dest folder> <probe 48 folder>

Probe 46 showed Desktop keeps structural keys written **by hand** and shows six of them in
*Customize current theme*; probe 48 measured what each paints. Blueprint now writes four of them
from the guidelines (`palette.second_level|third_level|fourth_level|disabled_text` ->
`foregroundNeutralSecondary`, `backgroundLight`, `foregroundNeutralTertiary`, `disabledText`),
which is a different claim: that Desktop accepts **what Blueprint wrote**. Same bar as probes 24,
30, 33, 43 and 45. The base is probe 48's report: its two gallery pages were built by `bp apply`
and hold the elements probe 48 found (a dropdown slicer, a multi-row card, secondary text).

`bp theme --replace-theme` regenerates the whole theme from the guidelines, so this probe also
answers what happens to the five structural keys the guidelines have **no** key for
(`foregroundNeutralLight`, `backgroundNeutral`, `backgroundDark`, `tableAccent`, `shapeStroke`):
they were hand-written into probe 46's theme and Blueprint will not write them again.

Set E, four colours each at Chebyshev distance >= 59 from every colour used anywhere in this
theme so far (checked, including probe 46's own structural values, so a pixel proves Blueprint's
value and not the hand-written one):

    second_level  #00E5FF cyan        third_level   #FF00FF magenta
    fourth_level  #7CFC00 lawn green  disabled_text #8B008B dark magenta

PREDICTIONS (written before the probe is opened):

 K1  Desktop opens the report with no error or theme banner, and *Customize current theme* shows
     Second-level #00E5FF, Third-level #FF00FF and Fourth-level #7CFC00. First-level (#1F2A33) and
     Background (#F7F4EC) are unchanged. **Secondary background (`backgroundNeutral`) falls back to
     Fluent2's #C7C7C7**, because `bp theme` did not write it: the guidelines have no key for it.
 K2  On Gallery A the dropdown slicer's border draws #FF00FF, the multi-row card's accent bars
     #7CFC00, and every secondary grey text pixel #00E5FF, by exact pixel count, in the same
     places probe 48 measured. The Filters pane edge draws #8B008B.
 K3  Dropping the five unwritten keys changes nothing visible: probe 48 found zero pixels of them,
     so the capture differs from probe 48's only in the four colours above (plus anti-aliasing).
 K4  Ctrl+S keeps `blueprint-theme.json` byte for byte, writes no second theme file, and changes no
     `visual.json`: a theme colour is not stored in a visual (probes 42, 46). At most `pages.json`
     `activePageName` changes.
 K5  Re-running `bp theme` on the saved report: No changes. `bp check` has no `palette` finding
     about the structural colours.

All content is the demo's financial sample.
"""

import shutil
import sys
import tempfile
from pathlib import Path

from _probe import git, make_probe

from blueprint.cli import main as bp

SET_E = """\
  second_level: "#00E5FF"    # probe 49 set E: cyan
  third_level: "#FF00FF"     # magenta
  fourth_level: "#7CFC00"    # lawn green
  disabled_text: "#8B008B"   # dark magenta
"""

STEPS = """\
# Probe 49: does Desktop keep the structural colours `bp theme` wrote?

Blueprint regenerated the theme from guidelines.yaml with four structural colours: Second-level
**#00E5FF** (cyan), Third-level **#FF00FF** (magenta), Fourth-level **#7CFC00** (lawn green) and
disabledText **#8B008B** (dark magenta). Claude opens the report and captures both gallery pages.
You only:

1. Look at **Gallery A**: the dropdown slicer's border should be magenta, the multi-row card's left
   accent bars green, and the grey subtitle text cyan. Don't click inside a visual.
2. **View -> Themes -> Customize current theme**: read out the **Structural colors** entries (all
   six, with their hex), then **Cancel**.
3. **Ctrl+S**.

Tell Claude when it is saved, with what the dialog showed.
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
    marker = '  maximum: "#B2182B"    # red\n'
    if marker not in guidelines:
        sys.exit("probe 45's guidelines.yaml changed: put the structural colours after palette.maximum by hand")
    (dest / "guidelines.yaml").write_text(guidelines.replace(marker, marker + SET_E), encoding="utf-8")
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "inputs: guidelines.yaml with the four structural colours (set E)")

    if bp(["theme", "--report", str(dest), "--guidelines", str(dest / "guidelines.yaml"),
           "--replace-theme"]) != 0:
        sys.exit(1)
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "blueprint: theme with the structural colours")

    (dest / "financial.SemanticModel" / ".pbi").mkdir(exist_ok=True)
    shutil.copy2(cache, dest / "financial.SemanticModel" / ".pbi" / "cache.abf")
    print(f"data cache copied from {cache}\nProbe ready: {dest}")
