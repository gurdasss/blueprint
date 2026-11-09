# fixtures/

Synthetic PBIP projects, **built from scratch in Power BI Desktop**, committed so the tests (and
anyone who clones the repo) run against genuine Desktop output. All content is invented: the
`Sales` table, its four rows and the `Total Amount` measure were typed in by hand.

| Fixture | Contents | Exercises |
|---|---|---|
| `01-blank-report` | a new report with one empty 1920×1080 page | reader, page creation, registry update |
| `02-card-and-chart` | page "Overview": a `cardVisual` bound to `[Total Amount]` with title "Total", and a `clusteredColumnChart` with a Country → Region drill-down on the X axis and `[Total Amount]` on Y. Both are off-grid (dragged by hand). Model: `Sales(Country, Region, Amount)`. | slots, bindings, `fmt`, `check`, idempotence |

## How they were made

Power BI Desktop **2.159.1231.0 (October 2026)**, 2026-11-09, following
`scripts/probe_apply.py` (probe 04). Each fixture is the probe's git tree at one step, exported
unchanged with `git archive`. Files are byte-identical to what Desktop saved:

- `01-blank-report`: step 01 (*File → New*, saved as `.pbip` named "Fixture").
- `02-card-and-chart`: step 12, the final state (after adding, renaming, reordering and deleting
  pages; entering data; adding, moving and titling the card; adding the chart; and pasting and
  deleting a card).

The full step-by-step diff is in `docs/probes/04-apply-from-scratch.diff`.

To rebuild against a newer Desktop, run `python scripts/probe_apply.py <dir>`, follow its
STEPS.md, then `git -C <dir> archive <step commit> -- . ':(exclude)STEPS.md' ':(exclude)snap.sh'
| tar -x -C fixtures/<name>`.

## What's included and why

- `Fixture.Report/StaticResources/SharedResources/BaseThemes/Fluent2-CY26SU10.json` is
  Microsoft's built-in base theme. Desktop copies it into every new report, and it's kept so
  the fixtures are exactly what Desktop produced.
- `.gitignore` is the one Desktop writes into a new project.
- `.pbi/localSettings.json` and `.pbi/cache.abf` are per-user and not committed.
- `definition/cultures/en-IN.tmdl` is named after the Desktop locale used to build them.

**Don't edit these by hand.** If a test needs a variation, copy a fixture into `tmp_path` and change
the copy, or use `tests/builders.py`.
