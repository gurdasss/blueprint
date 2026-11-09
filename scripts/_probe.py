"""Shared setup for Desktop probes: copy a PBIP project into a fresh git repo with a STEPS.md.

The user follows STEPS.md in Power BI Desktop and saves. Every change then shows up as a plain
`git diff` against the "baseline" commit.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def git(dest: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(dest), *args], check=True, stdout=subprocess.DEVNULL)


def make_probe(src: Path, dest: Path, steps: str, *, snap: bool = False) -> int:
    if dest.exists():
        sys.exit(f"{dest} already exists; remove it first")
    shutil.copytree(src, dest)
    (dest / "STEPS.md").write_text(steps, encoding="utf-8")
    if snap:
        (dest / "snap.sh").write_bytes(SNAP.encode())  # LF endings: bash on WSL needs them
    git(dest, "init", "-q")
    # Keep the diff honest when the folder lives on a Windows drive (/mnt/c).
    git(dest, "config", "core.autocrlf", "false")
    git(dest, "config", "core.filemode", "false")
    git(dest, "config", "core.whitespace", "cr-at-eol")
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "baseline")
    print(f"Probe ready: {dest}\nInstructions: {dest / 'STEPS.md'}")
    return 0


def cli(doc: str, steps: str) -> None:
    if len(sys.argv) != 3:
        sys.exit(doc)
    sys.exit(make_probe(Path(sys.argv[1]), Path(sys.argv[2]), steps))


SNAP = """#!/usr/bin/env bash
# Commit the probe's current state as one step. Run from WSL after each Desktop save:
#   bash snap.sh "02 add page"
set -euo pipefail
cd "$(dirname "$0")"
git add -A
git commit -q -m "${1:?usage: bash snap.sh \\"<step message>\\"}"
git log --oneline -1
"""


def make_empty_probe(dest: Path, steps: str) -> int:
    """A probe the user builds from scratch in Desktop: an empty git repo plus STEPS.md and snap.sh."""
    if dest.exists():
        sys.exit(f"{dest} already exists; remove it first")
    dest.mkdir(parents=True)
    (dest / "STEPS.md").write_text(steps, encoding="utf-8")
    (dest / "snap.sh").write_bytes(SNAP.encode())  # LF endings: bash on WSL needs them
    git(dest, "init", "-q")
    git(dest, "config", "core.autocrlf", "false")
    git(dest, "config", "core.filemode", "false")
    git(dest, "config", "core.whitespace", "cr-at-eol")
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "00 empty probe (instructions only)")
    print(f"Probe ready: {dest}\nInstructions: {dest / 'STEPS.md'}")
    return 0
