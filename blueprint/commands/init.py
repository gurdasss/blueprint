"""`bp init`: write a starter set of the files Blueprint reads, to edit rather than write.

Copies ``blueprint/starter/``: a guidelines file with every core key (the template's), the
layouts it finds through ``layouts.search_path``, and a page spec in ``pages/``. Specs get a
folder of their own because ``bp apply <folder>`` reads every ``*.yaml`` in it as a spec.

Guidelines and layouts stay files the client owns: the starter set is only ever copied out,
never read in place, so nothing is used that the client hasn't got a copy of. Nothing is
overwritten: if any target exists, nothing is written.

The starter files are copies of ``template/`` and ``guidelines/layouts/``
(``tests/test_init.py`` keeps them byte-identical).
"""

from __future__ import annotations

import argparse
from pathlib import Path

STARTER_DIR = Path(__file__).resolve().parent.parent / "starter"


class InitError(Exception):
    pass


def starter_files() -> list[Path]:
    """The starter files, relative to ``STARTER_DIR``, in a stable order."""
    return sorted(p.relative_to(STARTER_DIR) for p in STARTER_DIR.rglob("*.yaml"))


def run(args: argparse.Namespace) -> int:
    target = Path(args.dir)
    files = starter_files()
    if not files:
        raise InitError(f"no starter files found in {STARTER_DIR} (a broken install?)")
    existing = [f for f in files if (target / f).exists()]
    if existing:
        raise InitError(f"{target}: would overwrite {', '.join(f.as_posix() for f in existing)}; "
                        "nothing was written. Use an empty folder, or move these files away")
    for rel in files:
        (target / rel).parent.mkdir(parents=True, exist_ok=True)
        (target / rel).write_bytes((STARTER_DIR / rel).read_bytes())

    layouts = [f for f in files if f.parts[0] == "layouts"]
    print(f"Wrote {len(files)} starter file(s) in {target}:")
    print("  guidelines.yaml      your standards: canvas, spacing, page rules, palette, typography,")
    print("                       layouts. Every key is commented; edit the values")
    print(f"  layouts/             {len(layouts)} layouts, found by guidelines.yaml's layouts.search_path")
    print("  pages/overview.yaml  a page spec. Its field names are invented: replace them")
    print("Next:")
    print("  1. bp describe --report <your report> --guidelines guidelines.yaml")
    print("     lists the visual types, layouts and your model's real field names")
    print("  2. edit pages/overview.yaml (add a file per page), then:")
    print("     bp apply pages --report <your report> --guidelines guidelines.yaml --dry-run")
    print("Tip: run `git init` in your report's folder first, so every change bp makes can be undone.")
    return 0
