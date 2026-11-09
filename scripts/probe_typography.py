"""Build the Desktop probe for typography (probe 03).

Usage:
    python scripts/probe_typography.py <source PBIP folder> <dest folder>

Answers what probe 02 left open: how font families (including weight faces like
"Segoe UI Semibold") are stored, whether default values are omitted, what the "Heading"
font token is, how textbox bold and italic are stored, the subtitle object, and where a
customised theme's text classes go.

Step targets assume the Retail Analysis sample. They avoid map visuals, which are
unavailable in some Desktop installs.
"""

from _probe import cli

STEPS = """\
# Probe 03: typography

Use exactly the values below; the diff is matched against them.
**One visual per step. Don't touch anything else.** If a font isn't in the list, pick the
closest one and write down what you picked.

## Phase 1: one save at the end

| # | Page | Visual | Change in the Format pane | Answers |
|---|---|---|---|---|
| 1 | **Overview** | column chart, top right ("Total Sales Variance…") | Title → font **Segoe UI Semibold**, size **14** | how a weight face is stored |
| 2 | **Overview** | scatter chart (bottom right) | Title → font **Arial** (leave the size alone) | a plain non-default family; is the size written too? |
| 3 | **Overview** | pie chart (top left) | Turn **Subtitle** on → text **Probe subtitle**, size **12** | the subtitle object |
| 4 | **Overview** | lower card in the middle ("Total Stores") | Callout value → font **DIN** | card value font family |
| 5 | **New Stores** | header text "New Stores Analysis" | select all text → **Arial**, size **20**, **Bold**, **Italic** | textbox weight and style |
| 6 | **District Monthly Sales** | header text (top left) | select all text → in the font list pick a **theme font** if one is offered at the top (e.g. "Heading" or "Body"); otherwise pick **Segoe UI** and note it | theme font tokens |
| 7 | **District Monthly Sales** | area chart (bottom left) | Title → on, text **Probe title**, font **Segoe UI**, size **12** | are values equal to the default omitted? |

Then **Save** and tell Claude "phase 1 done". Claude commits it before phase 2.

## Phase 2: customise the theme's text (after Claude has committed phase 1)

| # | Where | Change | Answers |
|---|---|---|---|
| 8 | View → Themes → **Customize current theme** → **Text** | **General**: font **Segoe UI**, size **11**. **Title**: font **Segoe UI Semibold**, size **16**. Click **Apply** | where a customised theme is saved, and its textClasses |

**Save** and tell Claude "phase 2 done".


## Phase 3: customise an embedded theme (after Claude has committed phase 2)

Phase 2's customisation didn't persist, because the report's custom theme has no file. This
time, switch to a built-in theme first so Desktop copies its file into the report.

| # | Where | Change | Answers |
|---|---|---|---|
| 9 | View → Themes | pick **Default** (or the first built-in theme if "Default" isn't listed; note which) | embed a theme file |
| 10 | View → Themes → **Customize current theme** → **Text** | **General**: **Segoe UI**, size **11**. **Title**: **Segoe UI Semibold**, size **16**. Click **Apply**. If an "Update" prompt appears, **don't click it**; note that it appeared | where customised text classes are saved |

**Save**, close Desktop and tell Claude "phase 3 done".

Note anything Desktop showed you (warnings, banners, a visual that changed by itself).
"""

if __name__ == "__main__":
    cli(__doc__, STEPS)
