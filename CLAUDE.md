# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

Blueprint (`bp` CLI) is a pre-alpha Python tool that generates and aligns Power BI PBIP/PBIR report layouts from YAML page specs and a guidelines file. `README.md` is the design doc, and most of its structure isn't built yet. Built so far: `pbir/jsonfmt`, `pbir/schemas`, `pbir/reader`, `model`, and `bp inspect`. Roadmap: v0.1 `inspect`/`fmt` → v0.2 `check` → v0.3 `apply` (no bindings) → v0.4 typed slot bindings.

## Commands

Environment: WSL2 Ubuntu, Python 3.12, venv at `.venv/`.

```bash
source .venv/bin/activate
pip install -e ".[dev]"
pytest                                   # all tests
pytest tests/test_reader.py::test_sample_report   # one test
ruff check .
bp inspect --report samples/retail-analysis       # accepts .Report dir, .pbip, or a parent dir
python scripts/vendor_schemas.py <$schema URL>    # vendor a schema + its $refs into blueprint/pbir/schemas/
```

## Architecture

- **Only `blueprint/pbir/` knows the on-disk format.** `pbir/reader.py` builds `model.Report/Page/Visual`. Every model object carries an opaque `source` (a `reader.Document` holding the parsed JSON). The writer will patch those documents in place rather than regenerate them, so properties Blueprint doesn't model survive untouched.
- **`pbir/jsonfmt.py` is the only way to read or write PBIR JSON.** It reproduces Desktop's output byte for byte (CRLF, 2-space indent, no trailing newline, raw non-ASCII) and keeps each float's original text via `RawFloat`. Using the stdlib `json` to write will change every file.
- **`pbir/schemas.py`** validates against the vendored Microsoft schemas. Desktop writes minor versions that haven't been published yet (the sample has visualContainer 2.14.0, newest published is 2.13.0). So resolution picks the nearest vendored version with the same major and swaps the `$schema` const. A different major version is unknown.
- **`pbir/schema.md` is the source of truth for format facts.** Each fact is marked verified (and how) or open. Don't write code that relies on an open item. Settle it with a Desktop probe and record the result first.
- **Blueprint's own metadata goes in `annotations`** (e.g. `blueprint.ignore`). Desktop ignores annotations, and the schemas reject unknown keys.
- Commands live in `blueprint/commands/`, one module each. `cli.py` only parses arguments. Mutating commands will return a Plan (file ops + warnings) that `--dry-run` prints and the writer applies atomically.

## Design rules (from README; load-bearing)

- Deterministic, byte-identical output. No LLM, randomness or timestamps in the generation path, apart from the manifest's `generated_at`. `bp fmt` must be idempotent.
- Refuse rather than surprise. Never move content between pages or reflow layouts. Honour `blueprint.ignore`. Refuse PBIR-Legacy, and refuse unknown schema major versions unless `--force-schema` is passed.
- Config over code. Guidelines YAML never contains conditionals; branching logic is a named policy in `policies.py`. Guideline layers, from lowest to highest priority: `blueprint/defaults.yaml`, then `guidelines/<name>.yaml`, then `<report>/.blueprint.yaml`, then CLI flags.
- No premature abstraction (`create_page()` and `create_visual()` stay separate).

## Test data

- `samples/` holds real reports for format study. It is gitignored (except its README). Tests reach it through the `retail_report` fixture in `tests/conftest.py`, which skips when it's missing.
- `tests/builders.py` builds minimal synthetic PBIR reports in `tmp_path`, so the core tests don't depend on samples. `fixtures/` (committed, built from scratch) is planned.
- Never commit real report files, client measure or table names, or data. `visual.json` and bookmark files can contain data values from the model.
