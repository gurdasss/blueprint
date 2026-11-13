"""Build the Desktop probe for Power BI's modern structural key names (probe 51).

Usage:
    python scripts/probe_modern_structural.py build <dest folder> <probe 49 folder>
    python scripts/probe_modern_structural.py candidate <dest folder>

Probes 46 and 48 mapped four structural keys and found five others
(`foregroundNeutralLight`, `backgroundNeutral`, `backgroundDark`, `tableAccent`, `shapeStroke`)
painting nothing; probe 50 ruled out hover, selection, focus, a table style preset, a shape and a
button as well. The hypothesis left over: Power BI's **modern** structural names
(`firstLevelElements`, `secondLevelElements`, `thirdLevelElements`, `fourthLevelElements`,
`secondaryBackground`) are what Desktop reads, and the names Blueprint writes are legacy aliases.
Probe 46 fits that: the dialog's Third-level is `backgroundLight` and Fourth-level is
`foregroundNeutralTertiary`, which is exactly the documented alias pairing.

The base is probe 49's report: its theme was written by `bp theme`, so it holds the four legacy
keys and nothing else structural, and its gallery pages have the three elements probes 48 and 49
measured. `candidate` **removes the four legacy keys and writes modern names instead**, byte-exact
(`bp theme` is not run: it would write the legacy names back). `foreground` is left alone, because
`bp theme` also pins every text class's colour, which would mask `firstLevelElements`.

    secondLevelElements  #0000D2   thirdLevelElements  #00FF00   fourthLevelElements #F000A5
    secondaryBackground  #00FF69   tableAccent         #5AFF5A

`disabledText` is deliberately **dropped and not replaced** (no modern alias is claimed for it), as
the control: if removal takes effect, the Filters pane edge goes back to Fluent2's #B3B3B3.

PREDICTIONS (written before the probe is opened; counted exact and within 6 per channel):

 N1  **Desktop reads the modern names.** The secondary grey text draws #0000D2 (~13.7k px, where
     probe 49 measured 13,681), the dropdown slicer's border #00FF00 (~721 px) and the multi-row
     card's accent bars #F000A5 (600 px), in the same places. If instead the modern names are
     ignored, all three fall back to Fluent2 (grey #616161 text, and the slicer border and card
     bars to their own defaults) and the new colours have zero pixels.
 N2  **Control:** dropping `disabledText` restores Fluent2's #B3B3B3 on the Filters pane edge
     (~3,144 px), and #8B008B (probe 49's value) falls to zero. This proves a removed key takes
     effect, so a zero in N1 would mean "not read" and not "not applied".
 N3  `secondaryBackground` #00FF69 paints nothing: it is the modern alias of `backgroundNeutral`,
     which probes 48 and 50 never saw.
 N4  `tableAccent` #5AFF5A paints nothing (its name is the same in both forms; probe 50 ruled it
     out even under a "Bold header" style preset).
 N5  *Customize current theme* shows Second-level #0000D2, Third-level #00FF00, Fourth-level
     #F000A5 and Secondary background #00FF69 if N1 holds.
 N6  **The one that decides Blueprint's key names:** when the user changes one structural colour in
     that dialog and saves, Desktop writes it under the **legacy** name (`backgroundLight` and so
     on), as it did in probe 46, even though this file used the modern name — Desktop canonicalises
     to the legacy form. Alternatives: it keeps the modern name (then `guidelines.STRUCTURAL`
     should write modern names), or it writes both.

All content is the demo's financial sample.
"""

import shutil
import sys
import tempfile
from pathlib import Path

from _probe import make_probe

THEME = "financial.Report/StaticResources/RegisteredResources/blueprint-theme.json"
# legacy key -> (modern name, new loud value); None: dropped and not replaced (the control)
SWAP = {
    "foregroundNeutralSecondary": ("secondLevelElements", "#0000D2"),
    "backgroundLight": ("thirdLevelElements", "#00FF00"),
    "foregroundNeutralTertiary": ("fourthLevelElements", "#F000A5"),
    "disabledText": None,
}
EXTRA = {"secondaryBackground": "#00FF69", "tableAccent": "#5AFF5A"}

STEPS = """\
# Probe 51: does Desktop read Power BI's modern structural key names?

The theme's four legacy structural keys were replaced by the modern names, with new colours:
**secondLevelElements #0000D2** (deep blue), **thirdLevelElements #00FF00** (green),
**fourthLevelElements #F000A5** (pink), plus **secondaryBackground #00FF69** and **tableAccent
#5AFF5A**. `disabledText` was dropped and not replaced. Claude captures and measures. You only:

1. Open **Gallery A**. Is the grey subtitle text now blue, the dropdown slicer's border green and
   the multi-row card's left bars pink? (Or did they go back to grey?) Don't click in a visual.
2. **View -> Themes -> Customize current theme**: read out all six **Structural colors** entries
   with their hex, then **Cancel**.
3. **Change Third-level** to a bright colour you can name, click **Apply**, then **Ctrl+S**, and
   tell Claude which colour you picked. (This is the question that decides which name Blueprint
   should write, so it is the last step: nothing can follow it.)
"""


def candidate(dest: Path) -> None:
    """Swap the legacy keys for modern ones, keeping Desktop's bytes everywhere else."""
    path = dest / THEME
    data = path.read_bytes()
    for legacy, repl in SWAP.items():
        hits = [line for line in data.split(b"\r\n") if line.strip().startswith(b'"%s"' % legacy.encode())]
        if len(hits) != 1:
            sys.exit(f"{path}: expected exactly one {legacy} line, found {len(hits)}")
        old = hits[0] + b"\r\n"
        if repl is None:
            data = data.replace(old, b"")
        else:
            name, value = repl
            data = data.replace(old, b'  "%s": "%s",\r\n' % (name.encode(), value.encode()))
    anchor = b'  "secondLevelElements": "#0000D2",\r\n'
    extra = b"".join(b'  "%s": "%s",\r\n' % (k.encode(), v.encode()) for k, v in EXTRA.items())
    data = data.replace(anchor, anchor + extra)
    path.write_bytes(data)
    print("modern structural names written (commit with snap.sh, then reload)")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "candidate":
        candidate(Path(sys.argv[2]))
        sys.exit(0)
    if len(sys.argv) != 4 or sys.argv[1] != "build":
        sys.exit(__doc__)
    dest, base = Path(sys.argv[2]), Path(sys.argv[3])
    cache = base / "financial.SemanticModel" / ".pbi" / "cache.abf"
    if not cache.is_file():
        sys.exit(f"no data cache at {cache}")
    with tempfile.TemporaryDirectory() as stage:
        shutil.copytree(base, stage + "/src",
                        ignore=shutil.ignore_patterns(".git", ".pbi", "STEPS.md", "snap.sh"))
        make_probe(Path(stage) / "src", dest, STEPS, snap=True)
    (dest / "financial.SemanticModel" / ".pbi").mkdir(exist_ok=True)
    shutil.copy2(cache, dest / "financial.SemanticModel" / ".pbi" / "cache.abf")
    print(f"data cache copied from {cache}\nProbe ready: {dest}")
