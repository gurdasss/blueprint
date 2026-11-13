"""Build the Desktop probe for structural colours (probe 46): what do the theme's structural keys do?

Usage:
    python scripts/probe_theme_structural.py build <dest folder> <probe 45 folder>
    python scripts/probe_theme_structural.py candidate <dest folder>

Structural colours are the theme keys that are neither data colours, sentiment nor divergent:
`foreground`, `foregroundNeutralSecondary`, `foregroundNeutralTertiary`, `foregroundNeutralLight`,
`background`, `backgroundLight`, `backgroundNeutral`, `backgroundDark`, `tableAccent`,
`shapeStroke`, `disabledText` (and `hyperlink`, `visitedHyperlink`, left out: the report has no
links). Blueprint writes only `foreground` and `background` today (palette.text|background,
probes 03/06). By hand, as probe 42 and 44 were: `build` copies probe 45's final report (the
control: nothing added) and `candidate`, run only after the control captures exist, inserts the
keys after `maximum`, byte-exact, with `bp theme` not run (it would drop them). ColorId is NOT
probed here (probe 47): with these loud colours in the theme each swatch the user picks in
Desktop's own picker will be distinguishable then.

Fluent2's values (the base theme, for the readout): foregroundNeutralSecondary #616161,
foregroundNeutralTertiary #BDBDBD, foregroundNeutralLight #707070, backgroundLight #C8C6C4,
backgroundNeutral #C7C7C7, backgroundDark #E6E6E6, tableAccent #118DFF, shapeStroke #D1D1D1,
disabledText #B3B3B3. Candidate (each its own loud hex, none in this theme's palette, sentiment,
divergent set D or Fluent's structural defaults):

    foregroundNeutralSecondary #FF2D95 hot pink    foregroundNeutralTertiary #9B30FF purple
    foregroundNeutralLight     #FF6A00 orange      backgroundLight           #B6FF3B lime
    backgroundNeutral          #3BFFD0 aqua        backgroundDark            #8A5A2B brown
    tableAccent                #0000FF blue        shapeStroke               #FF0000 red
    disabledText               #808000 olive

PREDICTIONS (written before the probe is opened):

 S1  *Customize current theme* has a Structural section. Predicted labels, to be read exactly by the
     user: First-level elements (foreground), Second-level (foregroundNeutralSecondary), Third-level
     (foregroundNeutralTertiary), Background, Secondary background (backgroundLight), Table accent
     (tableAccent), perhaps a fourth level / tertiary background. Low confidence on which of
     backgroundNeutral, backgroundDark, foregroundNeutralLight, shapeStroke and disabledText appear
     at all. Any swatch showing a Fluent hex above is a key not set here: look it up in the list.
 S2  Where a key paints is judged against the control capture. Predictions: tableAccent colours
     the table's accent (header rule or grid line); foregroundNeutralSecondary the card label text
     (schema.md line 312: the base theme's card label fontColor); backgroundLight / backgroundNeutral
     / backgroundDark some fill or gridline. An element that doesn't change is "unchanged", not
     "ignores the key": `palette.text` was written into every textClass colour and `visualStyles`
     outrank `textClasses`, so a higher layer may pin it.
 S3  Existing visuals follow the theme with no `visual.json` change: a reload and a save change no
     visual file (unlike a conditional-format gradient, probe 44, which baked in hex).
 S4  Desktop keeps the theme byte for byte on a plain open and save.
 S5  (optional last step) The user changes one structural colour in the dialog and applies it:
     Desktop saves a new custom theme file (probe 03/42) and writes that key under the base theme's
     JSON name, so a guidelines key can use the theme's own names. It may write more or fewer
     keys than it was given.

All content is the demo's financial sample.
"""

import shutil
import sys
import tempfile
from pathlib import Path

from _probe import make_probe

THEME = "financial.Report/StaticResources/RegisteredResources/blueprint-theme.json"
ANCHOR = b'  "maximum": "#B2182B",\r\n'
CANDIDATE = {
    "foregroundNeutralSecondary": "#FF2D95", "foregroundNeutralTertiary": "#9B30FF",
    "foregroundNeutralLight": "#FF6A00", "backgroundLight": "#B6FF3B",
    "backgroundNeutral": "#3BFFD0", "backgroundDark": "#8A5A2B", "tableAccent": "#0000FF",
    "shapeStroke": "#FF0000", "disabledText": "#808000",
}

STEPS = """\
# Probe 46: what do the theme's structural colours do?

Claude takes control captures of every page first, then adds the candidate colours to the theme
and reloads. You only:

1. Open the report. Don't change anything. **Ctrl+S**.
2. **View -> Themes -> Customize current theme**. Find the **Structural colors** section and read
   out **every entry: its exact label and its hex**. Then **Cancel**.
3. *Optional, last (nothing can follow it):* change ONE structural colour there to a new bright
   colour you can name, **Apply**, **Ctrl+S**, and tell Claude which label you changed.
"""


def build(dest: Path, base: Path) -> None:
    cache = base / "financial.SemanticModel" / ".pbi" / "cache.abf"
    if not cache.is_file():
        sys.exit(f"no data cache at {cache}")
    with tempfile.TemporaryDirectory() as stage:
        shutil.copytree(base, stage + "/src",
                        ignore=shutil.ignore_patterns(".git", ".pbi", "STEPS.md", "snap.sh"))
        make_probe(Path(stage) / "src", dest, STEPS, snap=True)
    (dest / "financial.SemanticModel" / ".pbi").mkdir(exist_ok=True)
    shutil.copy2(cache, dest / "financial.SemanticModel" / ".pbi" / "cache.abf")
    print("control built: nothing added to the theme yet; capture every page, then run `candidate`")


def candidate(dest: Path) -> None:
    path = dest / THEME
    data = path.read_bytes()
    if data.count(ANCHOR) != 1:
        sys.exit(f"{path}: expected exactly one maximum key to insert after")
    new = b"".join(f'  "{k}": "{v}",\r\n'.encode() for k, v in CANDIDATE.items())
    path.write_bytes(data.replace(ANCHOR, ANCHOR + new))
    print("candidate keys added after `maximum` (commit with snap.sh, then reload)")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "build":
        build(Path(sys.argv[2]), Path(sys.argv[3]))
    elif len(sys.argv) == 3 and sys.argv[1] == "candidate":
        candidate(Path(sys.argv[2]))
    else:
        sys.exit(__doc__)
