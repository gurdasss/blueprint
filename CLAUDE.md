# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

Blueprint (`bp` CLI) is a pre-alpha Python tool that generates and aligns Power BI PBIP/PBIR report layouts from YAML page specs and a guidelines file. `README.md` is the design doc, and most of its structure isn't built yet. Built so far: `pbir/jsonfmt`, `pbir/schemas`, `pbir/reader`, `pbir/writer`, `model`, `plan`, `guidelines`, `policies`, `grid`, `validate`, `pbir/formatting`, `bp inspect`, `bp fmt` and `bp check` (including the palette and typography rules). Foundation for `bp apply` (v0.3): `spec`, `slots` (+ `blueprint/visuals/*.yaml`), `layouts`, `pbir/ids`, `pbir/registry`. Still to come: visual templates/render, the writer's create path, the `apply` command, and a Desktop probe of Blueprint-created output. Roadmap: v0.1 `inspect`/`fmt` → v0.2 `check` → v0.3 `apply` (no bindings) → v0.4 typed slot bindings.

## Commands

Environment: WSL2 Ubuntu, Python 3.12, venv at `.venv/`.

```bash
source .venv/bin/activate
pip install -e ".[dev]"
pytest                                   # all tests
pytest tests/test_reader.py::test_sample_report   # one test
ruff check .
bp inspect --report samples/retail-analysis       # accepts .Report dir, .pbip, or a parent dir
bp fmt --report <copy> --dry-run                  # never run fmt on samples/ itself; copy it first
bp check --report samples/retail-analysis --guidelines guidelines/example.yaml   # exit 0 clean, 1 errors, 2 unreadable
python scripts/vendor_schemas.py <$schema URL>    # vendor a schema + its $refs into blueprint/pbir/schemas/
```

## Architecture

- **Only `blueprint/pbir/` knows the on-disk format.** `pbir/reader.py` builds `model.Report/Page/Visual`. Every model object carries an opaque `source` (a `reader.Document` holding the parsed JSON). The writer patches those documents in place rather than regenerate them, so properties Blueprint doesn't model survive untouched.
- **`pbir/jsonfmt.py` is the only way to read or write PBIR JSON.** It reproduces Desktop's output byte for byte (CRLF, 2-space indent, no trailing newline, raw non-ASCII) and keeps each float's original text via `RawFloat`. Using the stdlib `json` to write will change every file.
- **`pbir/schemas.py`** validates against the vendored Microsoft schemas. Desktop writes minor versions that haven't been published yet (the sample has visualContainer 2.14.0, newest published is 2.13.0). So resolution picks the nearest vendored version with the same major and swaps the `$schema` const. A different major version is unknown. Because a newer minor may add properties the older schema rejects, the writer blocks only on schema errors its own change introduces, and `check` downgrades errors on approximate matches to a per-file warning. When Microsoft publishes a newer schema, vendor it with `scripts/vendor_schemas.py`.
- **`pbir/schema.md` is the source of truth for format facts.** Each fact is marked verified (and how) or open. Don't write code that relies on an open item. Settle it with a Desktop probe and record the result first.
- **Blueprint's own metadata goes in `annotations`** (e.g. `blueprint.ignore`). The schemas reject unknown keys, and annotations are verified to survive Desktop saves, including on visuals Desktop rewrites (probe 01). Never write `pages.json` `activePageName`: Desktop changes it on every save.
- Commands live in `blueprint/commands/`, one module each. `cli.py` only parses arguments. A mutating command changes the model, calls `writer.plan_writes(report)` to get a `plan.Plan` (file writes + warnings), then either prints it (`--dry-run`) or calls `writer.apply`. The writer schema-validates every changed document, refuses files that changed on disk since they were read, writes temp files before renaming any of them into place, and keeps file permissions.
- The writer owns only `position.x/y/width/height` so far. To make Blueprint own another field, extend `writer._visual_write`. Never regenerate a whole document.
- `validate.py` holds the guideline rules (`bounds`, `grid`, `margin`, `overlap`, `page-size`, `density`), pure functions over the model. `bp check` adds `format` findings from `pbir/` (reader warnings plus `schemas.validate_documents`). Rule ids and exit codes are a CI contract, so don't rename them. Each rule's severity comes from `check.severity` in the guidelines.
- `grid.off_grid_edges` is the only definition of "on grid", used by both `fmt` and `check`. A test asserts that `check` passes everything `fmt` produces.
- `pbir/formatting.py` finds colours by **shape** (`solid.color.expr` anywhere, plus textbox `textStyle.color`), not by property name, and classifies each as `hex`, `theme` (`ThemeDataColor`) or `expression`. Themes resolve through `report.json` `resourcePackages` to `StaticResources/<package>/<path>`. A missing theme is data, not an error. Paths read from report files must never be followed out of the report folder (`_inside_report`).
- The `palette` rule's severity comes from `palette.enforce` (strict/warn/off), not `check.severity`. Theme references pass because the theme itself is checked. Textbox colours picked from the theme are stored as resolved hex, so approved shades go in `palette.extra`.
- Typography (`formatting.fonts_in`): roles are `title`/`subtitle` (`visualContainerObjects`), `callout` (a **card's** `labels` only; chart `labels` are data labels) and `textbox` runs. A font weight is part of the face name (`Segoe UI Semibold`), so guidelines use exact face names and `weight` is rejected. A value a visual doesn't write inherits from the theme and is never a violation. Built-in (`SharedResources`) themes may legitimately have no embedded file.
- A guideline key the docs describe but no code implements goes in `guidelines.NOT_IMPLEMENTED`, so `check` reports it as unchecked instead of passing silently. Only check what `schema.md` marks as verified.
- `grid.py` snaps each of a visual's four edges to the nearest grid line, rounding halves up. It skips `blueprint.ignore` visuals silently. It skips, with a warning, pages with no fixed size (`DeprecatedDynamic`) and grouped visuals (group-relative positioning is unverified).

## Design rules (from README; load-bearing)

- Deterministic, byte-identical output. No LLM, randomness or timestamps in the generation path, apart from the manifest's `generated_at`. `bp fmt` must be idempotent.
- Refuse rather than surprise. Never move content between pages or reflow layouts. Honour `blueprint.ignore`. Refuse PBIR-Legacy, and refuse unknown schema major versions unless `--force-schema` is passed.
- Config over code. Guidelines YAML never contains conditionals; branching logic is a named policy in `policies.py`. Guideline layers, from lowest to highest priority: `blueprint/defaults.yaml`, then `guidelines/<name>.yaml`, then `<report>/.blueprint.yaml`, then CLI flags.
- No premature abstraction (`create_page()` and `create_visual()` stay separate).

- **Specs → placement:** `spec.parse` returns typed `PageSpec`/`VisualSpec`/`FieldRef`. Field syntax: `Table[Column]` is a column and `[Name]` is a measure. Every problem is collected with its location. Visual types are YAML contracts in `blueprint/visuals/`. Only ship a type whose PBIR shape a probe has verified, and cite the probe in the YAML. `layouts.place` fills regions of the matching role in declaration order. Running out of regions is a `LayoutError`, never a reflow.
- `layouts.search_path` entries resolve relative to the guidelines file that declares them (`guidelines._anchor`), not the current directory.
- New object names come from `pbir/ids.py`: 20 hex characters derived from a stable key (never random), so output is deterministic. `pbir/registry.py` is the only code that changes `pages.json` `pageOrder`. The page folder and the registry must change together.

## Test data

- `docs/probes/` holds raw diffs from Desktop probes, which are the evidence cited in `schema.md`. Probes are built with `scripts/probe_*.py` on the Windows drive (`/mnt/c/...`). After the user opens and saves in Desktop, read the diff with `git -C <probe> diff`.
- `samples/` holds real reports for format study. It is gitignored (except its README). Tests reach it through the `retail_report` fixture in `tests/conftest.py`, which skips when it's missing.
- `fixtures/` holds committed PBIP projects built from scratch in Desktop (probe 04), byte-identical to Desktop output, with all content invented. Tests use them through `blank_fixture`/`card_chart_fixture` in `tests/conftest.py`. Never edit them by hand: copy one into `tmp_path` first. `fixtures/README.md` says how to rebuild them.
- `tests/builders.py` builds minimal synthetic PBIR reports in `tmp_path` for edge cases.
- Never commit real report files, client measure or table names, or data. `visual.json` and bookmark files can contain data values from the model.
