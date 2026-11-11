# Unverified probes

Probe scripts that have **never been opened in Power BI Desktop**: written, predictions on
record, nothing more. They sit here instead of in `scripts/` until Desktop has answered. Whether
Desktop is reachable depends on the machine — on the Windows host's WSL it is, through
`/mnt/c/.../blueprint-probes/` and `scripts/desktop.sh`.

**Nothing in this folder is evidence.** A prediction is a guess with a reason, and the method in
`README.md` ("How the PBIP format is learned") only counts what Desktop did:

- no contract in `blueprint/visuals/` may gain a slot, an `accepts:` entry or an option because
  something here predicts it;
- no fact may be written into `blueprint/pbir/schema.md` from here;
- nothing here is cited in a commit message as a reason a feature works.

They are written up front for one reason: the prediction has to exist **before** Desktop answers,
or the probe just confirms whatever we see. Writing them while the evidence is out of reach is
the one part of the loop that doesn't need Desktop.

## What is here: nothing, and that is the point

**All three have run** (2026-11-11), so this folder holds only these rules, for the next probe
that has to be written before Desktop is at hand:

| Was | Ran as | What it settled |
|---|---|---|
| `pie-donut-options/` | **probe 37** (`scripts/probe_pie_donut_options.py`, `docs/probes/37-pie-donut-options.diff`) | `pie` and `donut` take `labels` and `legend`; their default is labels **on** and a legend at the **right**, so `labels` there needs both values. P5 failed: the object really is `labels`. |
| `scatter-map-options/` | **probe 38** (`scripts/probe_scatter_map_options.py`, `docs/probes/38-scatter-map-options.diff`) | `scatter` and `map` take `legend`; Desktop **deletes** a `labels` object from both. Their default legend is at the **bottom**, so the default position is per type. P3 failed. |
| `hierarchy-matrix-slicer/` | **probe 39** (`scripts/probe_hierarchy_matrix_slicer.py`, `docs/probes/39-hierarchy-matrix-slicer.diff`) | Desktop writes a hierarchy in a matrix's Rows with the first level active and the deeper one an explicit `"active": false`, and in a slicer's Field with every level active — and it accepts Blueprint's own shape in both, unchanged. |

The contracts are **not** changed by any of them: each is the candidate half, and the second half
is an acceptance probe built entirely by `bp apply` (as 33 followed 32). Until that is decided,
`matrix` and `slicer` still refuse a hierarchy and the four chart types still take no options.

## Running one, when you are at a Windows machine with Desktop

Same as any probe in `scripts/` (CLAUDE.md, "Test data"):

```bash
# from the repo, with the venv active
python unverified-probes/<topic>/probe.py \
    /mnt/c/Users/<user>/blueprint-probes/40-<topic> \
    /mnt/c/Users/<user>/blueprint-probes/_cache/demo-cache.abf
```

The second argument is a data cache (`cache.abf`) for the same model, so the fixture has data
without a refresh; `scripts/demo.sh` documents which one. Then open the `.pbip`, follow the
probe's `STEPS.md`, and `bash snap.sh "<step>"` after each save.

Numbering: each script has `PROBE = "NN"` at the top — set it to the next free probe number
(40 after probe 39 ran) before you run it, so `STEPS.md` names the right folder.

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
