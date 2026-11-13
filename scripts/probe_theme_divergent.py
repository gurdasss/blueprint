"""Build the Desktop probe for divergent colours (probe 44): what do a theme's `minimum`, `center`
and `maximum` do?

Usage:
    python scripts/probe_theme_divergent.py <dest folder> <probe 43 folder>

Divergent colours are the theme keys `minimum`, `center`, `maximum` (Fluent2: #FCE4D6, #FAFAFA,
#D4EDFC; `null` #FF7F48 is the colour for missing values). They belong to conditional formatting's
colour scale. Nothing in Blueprint writes, checks or knows a conditional-formatting shape yet
(schema.md has zero), so this is a by-hand probe: a **candidate** theme (the three keys added to
probe 43's Blueprint-written `blueprint-theme.json` by a byte-exact text edit, `bp theme` is not
run: it would drop them) and the user building two gradients in Desktop.

The question that decides what a guideline key could promise: **where does Desktop store a
gradient's colours?**

PREDICTIONS (written before the probe is opened). Set A = minimum #6A00FF violet, center #00E5D8
aqua, maximum #FF5E00 orange. Set B (swapped in after the user's save) = minimum #FF00C8 hot pink,
center #B7FF00 lime, maximum #0030FF blue. Neither set contains a palette colour, a sentiment
colour or a Fluent2 divergent pastel.

 D1  Desktop opens the candidate with no error; the Customize-theme dialog shows the Divergent
     section with set A (Minimum, Center, Maximum).
 D2  A new gradient (Format -> Cell elements -> Background color -> fx -> Gradient) **pre-fills
     its swatches from the theme**: Lowest = #6A00FF, Highest = #FF5E00, and with "Add a middle
     color" ticked, Middle = #00E5D8. The user reads the three swatches before touching anything.
     (Alternative, if false: the dialog uses its own fixed defaults, and then theme
     minimum/center/maximum feed nothing in conditional formatting, so a guideline key for them
     would do nothing visible.)
 D3  Where the colours end up (the central question; one of these):
       (a) hex `Literal`s copied into the visual (`FillRule.linearGradient2|3` min/max colour),
           so existing rules keep set A after the theme becomes set B;      <- my prediction
       (b) a theme reference, so the same rules now draw set B after a reload;
       (c) no colour stored for the defaults, resolved at render: also draw set B.
     The theme-swap step tells (a) from (b)/(c); the saved JSON tells (b) from (c).
 D4  Two gradient shapes are stored differently: Sum of Sales (two colours) as `linearGradient2`
     and Sum of Profit (middle colour ticked) as `linearGradient3`, both under
     `objects.values[].properties.backColor` or similar with a `selector.data` `metadata`
     on the field. The property path is unknown: read it from the diff.
 D5  `null` (missing values) can't be observed: the sample data probably has no blanks. Not forced.
 D6  Desktop's save keeps `blueprint-theme.json` byte for byte, set A included, and writes no
     second theme file.
 D7  `bp check` treats the gradient as an uncounted "colour expression" and doesn't check it
     against the palette (its note: "colour expression(s) not checked").

Steps are in STEPS.md. Order matters: open and save, then the two gradients and save, then
Claude swaps the theme to set B and reloads, last the optional Customize look. A bridge `reload`
with unsaved Desktop edits would throw the user's formatting away, so Claude reloads only after
the gradients are on disk.

All content is invented (the demo's financial sample).
"""

import shutil
import sys
import tempfile
from pathlib import Path

from _probe import make_probe

THEME = "financial.Report/StaticResources/RegisteredResources/blueprint-theme.json"
ANCHOR = b'  "bad": "#B3124B",\r\n'
SET_A = {"minimum": "#6A00FF", "center": "#00E5D8", "maximum": "#FF5E00"}


def add_keys(path: Path, colours: dict[str, str]) -> None:
    """Insert the keys after `bad` as bytes: CRLF kept, no trailing newline added."""
    data = path.read_bytes()
    if data.count(ANCHOR) != 1:
        sys.exit(f"{path}: expected exactly one bad key to insert after")
    new = b"".join(f'  "{k}": "{v}",\r\n'.encode() for k, v in colours.items())
    path.write_bytes(data.replace(ANCHOR, ANCHOR + new))


STEPS = """\
# Probe 44: what do the theme's divergent colours (minimum, center, maximum) do?

The theme now has a **candidate** set A: Minimum #6A00FF (violet), Center #00E5D8 (aqua),
Maximum #FF5E00 (orange). Claude drives the order; you build two gradients by hand.

| # | In Power BI Desktop | Then |
|---|---|---|
| 1 | Open the report. Don't change anything. **View -> Themes -> Customize current theme**: find the **Divergent colors** section and tell Claude the three colours shown. **Cancel**. **Ctrl+S**. | Claude commits `open and save` |
| 2 | Go to **Revenue Detail**. Select the table, **Format your visual -> Cell elements**. Pick series **Sum of Sales**, turn **Background color** on, click **fx**. Format style **Gradient**. **Read out the Lowest and Highest swatch hex values before touching anything**, then **OK**. | |
| 3 | Same table, series **Sum of Profit**: Background color on, **fx**, Gradient, tick **Add a middle color**. **Read out Lowest, Middle and Highest** the same way, accept them, **OK**. **Ctrl+S**. | Claude commits `gradients saved` |

Don't pick or edit any colour yourself: if you do, we can't tell the theme's default from your
choice. Then tell Claude. Claude swaps the theme to set B, reloads and captures, to see whether
the saved gradients follow the theme.
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
    add_keys(dest / THEME, SET_A)
    (dest / "financial.SemanticModel" / ".pbi").mkdir(exist_ok=True)
    shutil.copy2(cache, dest / "financial.SemanticModel" / ".pbi" / "cache.abf")
    print("candidate theme: set A added after `bad` (commit it with snap.sh before opening)")
