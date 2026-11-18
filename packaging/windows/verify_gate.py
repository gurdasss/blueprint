"""Compare the frozen exe's gate run with the pip-installed `bp` run (see gate.sh).

    python packaging/windows/verify_gate.py <exe out dir> <reference out dir>

Passes only if
  * the exe's `describe` lists exactly the visual contracts in blueprint/visuals/ (the data
    files made it into the bundle and resolve from it),
  * every command's stdout, stderr and exit code match the reference byte for byte, and
  * the report the exe wrote is byte-identical to the one the reference wrote.
Run it from the repository root, after gate.sh has run both ways.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

COMMANDS = ["version", "describe", "describe-report", "apply", "reapply", "check", "inspect"]


def tree(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in sorted(root.rglob("*")) if p.is_file()}


def main(exe_dir: Path, ref_dir: Path) -> int:
    problems: list[str] = []

    expected = sorted(p.stem for p in Path("blueprint/visuals").glob("*.yaml"))
    try:
        types = sorted(json.loads((exe_dir / "describe.out").read_text(encoding="utf-8"))["types"])
    except (ValueError, KeyError) as exc:
        types = []
        problems.append(f"exe describe printed no usable JSON ({exc}); "
                        f"stderr: {(exe_dir / 'describe.err').read_text(errors='replace')[-300:]}")
    print(f"exe describe: {len(types)} visual type(s): {', '.join(types)}")
    if not types:
        problems.append("describe lists no visual types: the contracts are missing from the bundle")
    elif types != expected:
        problems.append(f"describe types {types} != blueprint/visuals {expected}")

    for name in COMMANDS:
        for ext in ("code", "out", "err"):
            a, b = exe_dir / f"{name}.{ext}", ref_dir / f"{name}.{ext}"
            if a.read_bytes() != b.read_bytes():
                problems.append(f"{name}.{ext} differs from the reference")
        print(f"{name}: exit {(exe_dir / f'{name}.code').read_text().strip()}")

    got, want = tree(exe_dir / "work"), tree(ref_dir / "work")
    for path in sorted(set(got) | set(want)):
        if got.get(path) != want.get(path):
            problems.append(f"written file differs: {path}")
    print(f"work tree: {len(got)} file(s) compared")

    for p in problems:
        print(f"FAIL: {p}")
    print("GATE PASSED" if not problems else f"GATE FAILED ({len(problems)} problem(s))")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]), Path(sys.argv[2])))
