"""Build the Desktop probe for the structural keys no static capture explained (probe 50).

Usage:
    python scripts/probe_hover.py <dest folder> <probe 48 folder>

Probes 46 and 48 mapped four structural keys to what they paint and found **zero** pixels of five
others on two pages holding every visual type Blueprint builds:

    foregroundNeutralLight #FF6A00   backgroundNeutral #3BFFD0   backgroundDark  #8A5A2B
    tableAccent            #0000FF   shapeStroke       #FF0000

Both probes said so only of *static* captures: hover, selection and focus states were never
looked at, because the Desktop bridge can only screenshot a report page and a hover does not
survive that. Probe 50 drives the real cursor and photographs the screen instead
(`scripts/hover_capture.ps1`), so a transient state can be measured like any other capture.
The base is probe 48's report unchanged: its theme already carries those five loud values
(hand-written in probe 46) and its two gallery pages already hold the elements to hover.
Nothing is written to the report; nothing is saved.

PREDICTIONS (written before the probe is opened; each colour is counted exact and within 6 per
channel, and the screen is 1536x864 where a bridge capture is 2834x1587, so a 1 px border may
survive only as a near match):

 P1  Hovering a **table or matrix row** draws a row highlight. `backgroundNeutral` #3BFFD0 is the
     likeliest key (its dialog label is "Secondary background"); `backgroundDark` #8A5A2B is the
     alternative. Medium confidence that any structural key appears at all: the highlight may be a
     fixed grey or a transparency of the data colour.
 P2  Hovering a **list slicer item** draws an item highlight, also `backgroundNeutral`.
 P3  Hovering a **chart bar, slice or point** shows a tooltip and dims the other series. Predicted:
     no structural colour on the mark itself; the tooltip is Desktop chrome drawn outside the
     report canvas and may use none of the theme either.
 P4  **`tableAccent` appears in none of these states.** Power BI's table and matrix **style presets**
     ("Bold header", "Alternating rows", ...) are what the name points at, and the gallery's
     tables use the default style. If P4 holds, the follow-up is a style preset, not a hover.
 P5  **`shapeStroke` appears nowhere**: it needs a shape, button or image visual, and Blueprint
     builds none of them (`slots.CORE_TYPES`), so nothing on these pages can draw it.
 P6  **Focus** (Tab to a visual) draws a focus ring. Predicted: a fixed colour, not a theme key;
     `foregroundNeutralLight` #FF6A00 is the only plausible candidate.
 P7  **Selection** (clicking a slicer item, then a chart bar) persists after the click, so it can
     be captured without holding the mouse. Predicted: the selected slicer row takes
     `backgroundNeutral`; unselected chart marks fade by transparency, using no structural key.
 P8  At least one of the five is still unexplained when the probe ends. Any key with zero pixels
     everywhere stays "not seen", never "unused": this probe adds hover, selection and focus to
     the states looked at, and still covers only the visual types Blueprint can build.

All content is the demo's financial sample.
"""

import shutil
import sys
import tempfile
from pathlib import Path

from _probe import make_probe

STEPS = """\
# Probe 50: what do the last five structural colours paint?

Nothing in the report changed: probe 48's pages and theme, whose `foregroundNeutralLight` (orange),
`backgroundNeutral` (aqua), `backgroundDark` (brown), `tableAccent` (blue) and `shapeStroke` (red)
are loud and so far unseen. Claude opens the report, then moves the mouse and photographs the
screen itself to catch hover, selection and focus states, and measures the pixels.

You only need to:

1. Leave the Power BI Desktop window **maximised and in front** while Claude works, and keep your
   hands off the mouse (Claude is driving it).
2. Tell Claude when the report is open and showing data.

Nothing is saved. If Claude asks you to click something later, it will say exactly what.
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
    (dest / "financial.SemanticModel" / ".pbi").mkdir(exist_ok=True)
    shutil.copy2(cache, dest / "financial.SemanticModel" / ".pbi" / "cache.abf")
    print(f"data cache copied from {cache}\nProbe ready: {dest}")
