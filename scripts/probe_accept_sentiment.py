"""Build the Desktop probe that saves what `bp theme` and `bp apply` wrote for sentiment colours (probe 43).

Usage:
    python scripts/probe_accept_sentiment.py <dest folder> <demo folder>

Probe 42 showed Desktop honours `good`/`neutral`/`bad` in a custom theme when they are written **by
hand**. Blueprint now writes them from `palette.good|neutral|bad` in the guidelines, which is a
different claim: that Desktop accepts **what Blueprint wrote**. Same bar as probes 21, 24, 30
and 33. Nothing here is patched by hand. The demo folder is the financial PBIP of probes 41 and 42
(`blueprint-demo`, its data cache is copied too). Blueprint runs `bp theme --replace-theme` with
`guidelines.yaml` (the demo's Harbour & Finch standard plus three sentiment colours, none of them
in the palette or Fluent2's pastels) and `bp apply` builds one page, **Sentiment**, with three
KPIs chosen so that each sentiment shows without flipping a direction:

    below goal   Sum of Sales vs Sum of Gross Sales   (as the demo's Sales Trio KPI: -4%)
    above goal   Sum of Gross Sales vs Sum of Sales
    level        Sum of Sales vs Sum of Sales         (the goal equals the value)

PREDICTIONS (written before the probe is opened):

 B1  Desktop opens the report with no error or banner about the theme. The two charts on the
     page use the guidelines' data colours.
 B2  The KPI below its goal draws bad `#B3124B` and the one above draws good `#2E9E4F`, each in
     its value, its "!" marker and its trend area. The pre-existing KPIs on the other pages
     (both below goal) draw `#B3124B` too.
 B3  The level KPI draws neutral `#F0C419`. This is the **least certain** prediction: the
     indicator may draw no sentiment colour at a 0% difference. Either result is recorded; if
     it isn't yellow, `neutral` stays unobserved on screen.
 B4  Ctrl+S: `blueprint-theme.json` is kept byte for byte, `report.json` still names it as the
     custom theme and Desktop writes no second theme file. No `visual.json` gains an `objects`
     entry for a colour. At most Desktop raises a file's `$schema` 2.13.0 -> 2.14.0, adds its
     usual condition-less auto `filterConfig` and rewrites `pages.json` `activePageName`.
 N1  (follow-up, written after B1-B4's save and before the next reload; B3 was wrong: the level
     KPI drew good, so neutral is still unseen.) A KPI with **no goal** (`specs/no-goal.yaml`, a
     page of its own because trio-focus has three KPI regions and apply never reflows) is the
     candidate for neutral. Prediction: its indicator draws neutral `#F0C419`. Low confidence:
     it may draw no sentiment colour (the theme's foreground) or good. If neither the no-goal
     KPI nor anything else here draws yellow, `neutral` is still open, and a waterfall's total
     bar is the next candidate (needs a contract and its own probe).
 B5  Re-running `bp theme` and `bp apply` on the saved report changes nothing but the manifest,
     and `bp check` with the same guidelines has no `palette` finding about the sentiment colours.

The demo's data is the Microsoft-style financial sample; nothing here is client data.
"""

import shutil
import sys
import tempfile
from pathlib import Path

from _probe import git, make_probe

from blueprint.cli import main as bp

ROOT = Path(__file__).resolve().parent.parent

SENTIMENT = """\
  good: "#2E9E4F"       # probe 43: green, not in the palette or Fluent2's pastel good
  neutral: "#F0C419"    # yellow
  bad: "#B3124B"        # crimson
"""

SPEC = """\
# Probe 43: one page of KPIs, one per sentiment, plus two charts so the data colours show.
page: Sentiment
layout: trio-focus
visuals:
  - type: header
    title: Sentiment Colours
  - type: kpi
    id: below-goal
    title: Below goal (bad)
    slots:
      value: { field: "financials[Sales]", aggregate: sum }
      trend: "financials[Date]"
      target: { field: "financials[Gross Sales]", aggregate: sum }
  - type: kpi
    id: above-goal
    title: Above goal (good)
    slots:
      value: { field: "financials[Gross Sales]", aggregate: sum }
      trend: "financials[Date]"
      target: { field: "financials[Sales]", aggregate: sum }
  - type: kpi
    id: level
    title: Level with goal (neutral)
    slots:
      value: { field: "financials[Sales]", aggregate: sum }
      trend: "financials[Date]"
      target: { field: "financials[Sales]", aggregate: sum }
  - type: column
    title: Sales by Country
    slots:
      category: "financials[Country]"
      value: { field: "financials[Sales]", aggregate: sum }
  - type: donut
    title: Sales Share by Segment
    slots:
      category: "financials[Segment]"
      value: { field: "financials[Sales]", aggregate: sum }
"""

STEPS = """\
# Probe 43: does Desktop keep the sentiment colours `bp theme` wrote?

Blueprint wrote the theme (`good` green #2E9E4F, `neutral` yellow #F0C419, `bad` crimson #B3124B,
from `palette.good|neutral|bad` in guidelines.yaml) and built the page **Sentiment** with three
KPIs: below its goal, above it, and level with it. Claude opens the report through the bridge and
captures the pages. You only:

1. When Desktop shows the report, look at the **Sentiment** page: what colour is each of the
   three KPIs? (Don't click anything inside a visual.) Click **Refresh now** if it asks.
2. **Ctrl+S**.

Tell Claude when it is saved and what you saw on the three KPIs. Claude then re-runs Blueprint on
the saved report and reads Desktop's diff.

What it settles: whether Desktop draws and keeps Blueprint's sentiment keys, and what a KPI whose
goal equals its value draws (neutral, or no colour).
"""

if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    dest, demo = Path(sys.argv[1]), Path(sys.argv[2])
    cache = demo / "financial.SemanticModel" / ".pbi" / "cache.abf"
    if not cache.is_file():
        sys.exit(f"no data cache at {cache}")
    with tempfile.TemporaryDirectory() as stage:
        # the demo's files without its own git history, Desktop's cache or local settings
        shutil.copytree(demo, stage + "/src", ignore=shutil.ignore_patterns(".git", ".pbi", "PROBE-42.md"))
        make_probe(Path(stage) / "src", dest, STEPS, snap=True)
    (dest / "layouts").mkdir(exist_ok=True)

    guidelines = (demo / "midnight-teal.yaml").read_text(encoding="utf-8")
    marker = '  text: "#1F2A33"         # ink\n'
    if marker not in guidelines:
        sys.exit("midnight-teal.yaml changed: put the sentiment colours after palette.text by hand")
    (dest / "guidelines.yaml").write_text(guidelines.replace(marker, marker + SENTIMENT), encoding="utf-8")
    (dest / "specs").mkdir()
    (dest / "specs" / "sentiment.yaml").write_text(SPEC, encoding="utf-8")
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "inputs: guidelines.yaml (with sentiment colours) and specs/sentiment.yaml")

    guide = str(dest / "guidelines.yaml")
    if bp(["theme", "--report", str(dest), "--guidelines", guide, "--replace-theme"]) != 0:
        sys.exit(1)
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "blueprint: theme with sentiment colours")
    if bp(["apply", str(dest / "specs"), "--report", str(dest), "--guidelines", guide]) != 0:
        sys.exit(1)
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "blueprint: apply specs/sentiment.yaml")

    (dest / "financial.SemanticModel" / ".pbi").mkdir(exist_ok=True)
    shutil.copy2(cache, dest / "financial.SemanticModel" / ".pbi" / "cache.abf")
    print(f"data cache copied from {cache}\nProbe ready: {dest}")
