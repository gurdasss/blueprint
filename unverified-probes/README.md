# Unverified probes

Probe scripts that have **never been opened in Power BI Desktop**. They are written, their
predictions are on record, and nothing more. Desktop runs on Windows; whichever machine you are
reading this on may not have it, which is why these sit here instead of in `scripts/`.

**Nothing in this folder is evidence.** A prediction is a guess with a reason, and the method in
`README.md` ("How the PBIP format is learned") only counts what Desktop did:

- no contract in `blueprint/visuals/` may gain a slot, an `accepts:` entry or an option because
  something here predicts it;
- no fact may be written into `blueprint/pbir/schema.md` from here;
- nothing here is cited in a commit message as a reason a feature works.

They are written up front for one reason: the prediction has to exist **before** Desktop answers,
or the probe just confirms whatever we see. Writing them while the evidence is out of reach is
the one part of the loop that doesn't need Desktop.

## What is here, and why these

Each probe is a folder with one `probe.py`, isolated: no shared state, no imports between them,
and any can be run without the others. They all close an **unevenness in a fact the core
already relies on** — not new surface. That is the whole list; see "Deliberately not probed".

| Folder | Settles | Why it is core |
|---|---|---|
| `scatter-map-options/` | `labels` and `legend` (positions and `off`) on `scatterChart` and `map`, and what each shows by default | The two newest types (probes 34, 36) have **no options at all**, while the other seven chart types all take these two. Both sample reports position or hide a legend on them. |
| `hierarchy-matrix-slicer/` | the shape Desktop writes for a **model hierarchy** in a matrix's Rows and a slicer's Field, and whether it accepts Blueprint's | Hierarchy binding is already core (probes 16-19) on `column`, `bar`, `line`, `pie` and `table`. `matrix` and `slicer` refuse it **only because no probe covered it**, and both contracts say so. A matrix and a slicer are where reports put a hierarchy. |

`pie-donut-options/` has run: it is **probe 37** (`scripts/probe_pie_donut_options.py`,
evidence `docs/probes/37-pie-donut-options.diff`), and pie and donut are no longer owed options.
After the two left, every chart type in the core takes the same two options, and every well that
takes a category takes a hierarchy. That is the point at which this folder should be empty.

## Running one, when you are at a Windows machine with Desktop

Same as any probe in `scripts/` (CLAUDE.md, "Test data"):

```bash
# from the repo, with the venv active
python unverified-probes/scatter-map-options/probe.py \
    /mnt/c/Users/<user>/blueprint-probes/38-scatter-map-options \
    /mnt/c/Users/<user>/blueprint-probes/_cache/demo-cache.abf
```

The second argument is a data cache (`cache.abf`) for the same model, so the fixture has data
without a refresh; `scripts/demo.sh` documents which one. Then open the `.pbip`, follow the
probe's `STEPS.md`, and `bash snap.sh "<step>"` after each save.

Numbering: each script has `PROBE = "NN"` at the top — set it to the next free probe number
(38 after probe 37 ran) before you run it, so `STEPS.md` names the right folder.

## When a probe has run

1. Record what Desktop did in `blueprint/pbir/schema.md`, under a dated **Verified** heading
   citing the script and the evidence file — including any prediction that **failed**, which is
   the more valuable half.
2. Write the evidence: `python scripts/probe_evidence.py <probe folder> docs/probes/NN-name.diff`
   (byte-exact; a hand-edited diff won't replay).
3. Move `probe.py` to `scripts/probe_<name>.py` and delete its folder here. A probe that has run
   is not an unverified probe.
4. Add the number to `REPLAYED` in `tests/test_probe_replay.py` (and to `ACCEPTANCE` if Desktop
   saved something Blueprint built). Mind the step-naming rule: a section title that starts with
   two digits is treated as a Desktop save.
5. Only then change the contracts, and cite the probe in the YAML comment.
6. A candidate shape says "Desktop takes this"; it takes an **acceptance probe**, built entirely
   by `bp apply` with the new contract, to say "Desktop takes what Blueprint writes". Both of the
   options probes here are the first half; the second half is a new probe (as 33 followed 32).

## Deliberately not probed

Not because they're uninteresting — because nothing has shown they are in the core 20%, and the
repo's rule is a **survey of real reports first** (counts of `queryState` roles and `objects`
keys per visual type, never field names or data; `samples/` is gitignored and absent on some
machines). That survey is how step 32's features were ranked, and it is what should gate any of
these:

- **Matrix row/column subtotals** (`table` has `totals`; the matrix equivalent is unprobed).
  Desktop's default is on, which is the common case, and an option a spec leaves out is left to
  Desktop — so this costs nothing today.
- **Axis titles and conditional formatting.** Zero uses in the step-32 survey.
- **`labels`/`legend` on the non-chart types** (`card`, `kpi`, `table`, `matrix`, `slicer`,
  `multi-row-card`): either meaningless or theme-level.
- **A map's Latitude/Longitude wells, a scatter's Play Axis, a pie's `details` as a list.**
- **Re-apply and rebinding on the newest types.** Already covered, not open: probe 36's evidence
  replays in `tests/test_probe_replay.py`, and
  `test_reapply_after_desktop_saved_changes_nothing` asserts a re-apply over Desktop's own save
  of the scatter, multi-row card and map changes nothing but the manifest.
