"""Build the Desktop probe that resolves what `ThemeDataColor.ColorId` and `Percent` mean (probe 47).

Usage:
    python scripts/probe_colorid.py <dest folder> <probe 46 folder>

schema.md has had this open since probe 02: a `ThemeDataColor {ColorId, Percent}` is a reference to
a theme colour, but the commonly cited mapping (0 background, 1 foreground, n >= 2 dataColors[n-2])
and the shade formula for `Percent` were never verified. Probe 03 only found that "1st column,
1st row" of the picker gave `ColorId 0, Percent -0.1` and said not to infer positions from it.
The base theme itself uses `ColorId 0` and `ColorId 2` (shaded -0.2/-0.4/-0.6) in 24 places.

The base is probe 46's final report: its theme gives every structural key its own loud hex
(foreground #1F2A33, background #F7F4EC, foregroundNeutralSecondary #FF2D95, ...Tertiary #9B30FF,
...Light #FF6A00, backgroundLight #4639FF, backgroundNeutral #3BFFD0, backgroundDark #8A5A2B), the
data colours start #0B6E75 #E8A33D #C2452D #5B7DB1 #7A9E3B, so a colour Desktop resolves can be
traced to exactly one key. Blueprint builds one page, **Swatches**, of 14 cards (each titled with the
picker cell to choose for its container background). The user picks the cells in Desktop's OWN
colour picker, so Desktop writes the `ThemeDataColor` shape itself (no candidate shape is
hand-written), and one save gives all 14. The saved JSON gives (ColorId, Percent) per cell and the
capture, sampled in solid card fill, gives the resolved colour.

PREDICTIONS (written before the probe is opened):

 C1  The picker's "Theme colors" grid has 8 columns (the first eight theme colours) and rows of
     shades: a base row and lighter/darker rows (Office-style: lighter 80/60/40%, darker 25/50%).
     The user reports the real layout; where it differs, cards that have no such cell are skipped.
 C2  Column -> `ColorId` runs 0, 1, 2, ... left to right with `Percent` 0 in the base row, and the
     base-row colours are: ColorId 0 = `background` (#F7F4EC), 1 = `foreground` (#1F2A33), then
     two more structural/neutral colours, then the data colours. This is the Office-style
     lt1, dk1, lt2, dk2, accent order. Low confidence on columns 3 and 4: either
     (`backgroundLight` #4639FF, `foregroundNeutralSecondary` #FF2D95) or (`backgroundNeutral`
     #3BFFD0, `foregroundNeutralTertiary` #9B30FF). The base theme's `ColorId 2` shaded -0.2,
     -0.4, -0.6 for button fills (a darkened grey) fits a light key in column 3.
 C3  `Percent` is signed: lighter > 0, darker < 0 (schema.md), rows lighter-to-darker run
     +0.8, +0.6, +0.4, then -0.25, -0.5 (or the equivalent shade steps).
 C4  Probe 03's "1st column, 1st row gave ColorId 0, Percent -0.1" is explained by the grid layout
     (the first row is not the base row, or its base cell is a -0.1 shade): it is read off the
     saved JSON here, not assumed.
 C5  The resolved colour of a shade follows an HSL or RGB tint/shade of the base colour. Which
     formula is settled by comparing the sampled fill against the base hex (e.g. -0.5 of
     #F7F4EC), not predicted exactly.
 C6  The saved shape is `visualContainerObjects.background[0].properties.color.solid.color.expr
     .ThemeDataColor {ColorId, Percent}`, with `show`/`transparency` beside it (unknown: read it).
 C7  Desktop keeps the theme file byte for byte; the only files that change are the 14 cards'
     `visual.json` and `pages.json` `activePageName`.

 RESULT OF THE PICKER STEP (recorded after the user's picks; C1-C7 above are NOT all kept):
 the picker's grid is 10 columns x 6 rows of **data colours only** (hover: "#7A9E3B, Theme color 5,
 20% lighter"); no background/foreground swatch. Saved: R1 C1 = "Theme color 2, 40% lighter"
 -> `ColorId 3, Percent 0.4`; R1 C2 = "Theme color 7, 20% lighter" -> `ColorId 8, Percent 0.2`,
 both in `objects.fillCustom[].properties.fillColor`, selector `{id: default}` (the card's own fill,
 not the container background). Drawn: #F1C88B and #FEAB85, exactly the data colours tinted
 toward white by c + (255 - c) * p. So ColorId n = dataColors[n - 2] (the cited mapping) and a
 positive Percent is lighter. Hover for "Theme color 2, 50% darker" read #74521F = c * (1 - p).

FOLLOW-UP PREDICTIONS (written before the candidate below is applied; the picker can't reach
ColorId 0 and 1, so these numbers are hand-written into the shape Desktop wrote, with a reload):

 F1  ColorId 0 resolves to the theme's `background` (#F7F4EC), so ColorId 0 / Percent -0.5 draws
     #7C7A76 (each channel halved). Alternative: a fixed white (#FFFFFF) or black.
 F2  ColorId 1 resolves to `foreground` (#1F2A33).  Alternative: a fixed black.
 F3  ColorId 2 is dataColors[0] (#0B6E75) and ColorId 11 is dataColors[9] (#DFBFBF).
 F4  ColorId 12, beyond the picker's 10 columns, is dataColors[10] (#4AC5BB): the reference is
     an index into the whole data-colour list, not into what the picker shows.
 F5  A negative Percent darkens by c * (1 + p): ColorId 3 / Percent -0.5 draws #74521F, the
     value Desktop's own hover showed for "Theme color 2, 50% darker".
 F6  ColorId 0 / Percent 0.5 draws #FBFAF5 and ColorId 1 / Percent 0.5 draws #8F9599 (c + (255 - c) * .5)
     if F1 and F2 hold.

RESULT OF THE FOLLOW-UP (sampled card fills): F1 and F2 WRONG: ColorId 0 is a fixed white
(#FFFFFF; at Percent -0.5 #808080) and ColorId 1 a fixed black (#000000; at 0.5 #808080), NOT the
theme's background/foreground. F3 held for ColorId 2 (#0B6E75). F5 held (#74521F; Desktop rounds
half up). F3 failed for ColorId 11 and F4 for ColorId 12: both drew the card's default fill
(#F7F4EC), so they did not resolve. Second follow-up, written before it is applied:

 F7  The resolvable range ends before 11. ColorId 9 (= Theme color 8, #A66999) and ColorId 10 (=
     Theme color 9, #3599B8) resolve; ColorId 11 (Theme color 10, #DFBFBF) does not again.
     (Alternative: all three resolve and the first two follow-ups failed for another reason.)

All content is the demo's financial sample.
"""

import shutil
import sys
import tempfile
from pathlib import Path

from _probe import git, make_probe

from blueprint.cli import main as bp

COLS = 7
CELL_W, CELL_H, GAP = 160, 240, 16

# (title, where in the picker's "Theme colors" grid)
CARDS = [(f"R1 C{c}", f"row 1, column {c}") for c in range(1, 9)]
CARDS += [(f"C1 R{r}", f"column 1, row {r}") for r in range(2, 7)]
CARDS += [("C3 R4", "column 3, row 4")]


def layout() -> str:
    lines = ["# Probe 47: a header and one region per picker cell to try (7 columns, grid 8, margin 24).",
             "name: swatches", "canvas: { width: 1280, height: 720 }", "regions:",
             "  - { role: header, x: 24, y: 24, w: 1232, h: 64 }"]
    for i in range(len(CARDS)):
        x = 24 + (i % COLS) * (CELL_W + GAP)
        y = 104 + (i // COLS) * (CELL_H + GAP)
        lines.append(f"  - {{ role: main, x: {x}, y: {y}, w: {CELL_W}, h: {CELL_H} }}")
    return "\n".join(lines) + "\n"


def spec() -> str:
    out = ["# Probe 47: one card per colour-picker cell; the user sets each card's background by hand.",
           "page: Swatches", "layout: swatches", "visuals:", "  - type: header", "    title: Swatches"]
    for title, _ in CARDS:
        out += ["  - type: card", f"    title: \"{title}\"",
                "    slots: { value: { field: \"financials[Sales]\", aggregate: sum } }"]
    return "\n".join(out) + "\n"


STEPS = """\
# Probe 47: what do ThemeDataColor ColorId and Percent mean?

Blueprint built the page **Swatches**: 14 cards, each titled with the colour-picker cell to try
("R1 C3" = row 1, column 3; "C1 R4" = column 1, row 4). Claude opens the report and captures it
first. You only:

1. Open **Swatches**. Select the card **R1 C1**. **Format your visual -> General -> Effects ->
   Background**. Click the **Color** swatch: the picker opens with a **Theme colors** grid.
   **Tell Claude how many columns and rows that grid has** (and what hovering a swatch shows, if it
   shows a name).
2. Choose the cell the card's title names (columns count from the left, rows from the top of the
   Theme colors grid, base colour row = row 1). Do the same for every card. Don't use the
   "Recent colors" or "Custom" rows. If the grid has no such cell, skip that card and say so.
3. Don't change anything else (no transparency, no other formatting). **Ctrl+S** once all are done.

Tell Claude when it is saved, with the grid's layout.
"""

# (card title, ColorId, Percent) written by hand into the shape Desktop saved for a picked cell
FOLLOW_UP_2 = [("C1 R5", 9, 0), ("C1 R6", 10, 0), ("C3 R4", 11, 0)]
FOLLOW_UP = [("R1 C3", 0, -0.5), ("R1 C4", 1, 0), ("R1 C5", 2, 0), ("R1 C6", 11, 0), ("R1 C7", 12, 0),
             ("R1 C8", 3, -0.5), ("C1 R2", 0, 0), ("C1 R3", 1, 0.5), ("C1 R4", 0, 0.5)]


def candidate(dest: Path, follow_up: list | None = None) -> None:
    """Hand-write the follow-up ThemeDataColor values, keeping Desktop's bytes everywhere else."""
    from blueprint.pbir import jsonfmt

    wanted = {t: (cid, pct) for t, cid, pct in (follow_up or FOLLOW_UP)}
    done = set()
    for f in sorted(dest.glob("financial.Report/definition/pages/*/visuals/*/visual.json")):
        doc = jsonfmt.load(f)
        title = (((doc["visual"].get("visualContainerObjects") or {}).get("title") or [{}])[0]
                 .get("properties", {}).get("text", {}).get("expr", {}).get("Literal", {}).get("Value"))
        key = title.strip("'") if isinstance(title, str) else None
        if key not in wanted or key in done:
            continue
        cid, pct = wanted[key]
        doc["visual"].setdefault("objects", {})["fillCustom"] = [{
            "properties": {"fillColor": {"solid": {"color": {"expr": {"ThemeDataColor": {
                "ColorId": cid, "Percent": pct}}}}}},
            "selector": {"id": "default"}}]
        f.write_bytes(jsonfmt.dump_bytes(doc))
        done.add(key)
    missing = set(wanted) - done
    if missing:
        sys.exit(f"no card titled {sorted(missing)}")
    print(f"wrote {len(done)} ThemeDataColor fills by hand")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] in ("candidate", "candidate2"):
        candidate(Path(sys.argv[2]), FOLLOW_UP_2 if sys.argv[1] == "candidate2" else None)
        sys.exit(0)
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
    (dest / "layouts" / "swatches.yaml").write_text(layout(), encoding="utf-8")
    (dest / "specs" / "swatches.yaml").write_text(spec(), encoding="utf-8")
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "inputs: layouts/swatches.yaml and specs/swatches.yaml")
    if bp(["apply", str(dest / "specs" / "swatches.yaml"), "--report", str(dest),
           "--guidelines", str(dest / "guidelines.yaml"), "--set", "page.max_visuals=20"]) != 0:
        sys.exit(1)
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "blueprint: apply specs/swatches.yaml")
    (dest / "financial.SemanticModel" / ".pbi").mkdir(exist_ok=True)
    shutil.copy2(cache, dest / "financial.SemanticModel" / ".pbi" / "cache.abf")
    print(f"data cache copied from {cache}\nProbe ready: {dest}")
