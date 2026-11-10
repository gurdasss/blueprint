"""Build the Desktop probe for README Q14: do annotations survive a Desktop save?

Usage:
    python scripts/probe_annotations.py <source PBIP folder> <dest folder>

Copies the project to <dest> and makes it a git repo with two commits:

1. "baseline": the untouched copy.
2. "blueprint": annotations added at report, page and visual level, a per-report
   .blueprint.yaml (spacing.grid 16, extensions.max_resize 0.25), and `bp fmt` applied.

Then open <dest>/*.pbip in Power BI Desktop, follow the steps the script prints, and
inspect `git status` / `git diff` to see exactly what Desktop changed.

Annotation targets assume the Retail Analysis sample's object names. Change TARGETS for
another report.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from blueprint.cli import main as bp
from blueprint.pbir import jsonfmt

PROBE = "blueprint.probe"
TARGETS = {
    # (relative to <name>.Report/definition, annotations to add)
    "report.json": [(PROBE, "report-level")],
    "pages/ReportSection3/page.json": [(PROBE, "page-level")],
    # Overview scatter: off-grid and marked ignore -> fmt must leave it alone.
    "pages/ReportSection3/visuals/VisualContainer6/visual.json": [
        ("blueprint.ignore", "true"), (PROBE, "ignored-visual")],
    # Overview column chart: fmt moves it; Desktop should not touch it.
    "pages/ReportSection3/visuals/VisualContainer4/visual.json": [(PROBE, "untouched-by-desktop")],
    # New Stores line chart: the user moves it in Desktop -> Desktop rewrites this file.
    "pages/ReportSection4/visuals/VisualContainer1/visual.json": [(PROBE, "edited-in-desktop")],
}
BLUEPRINT_YAML = "spacing:\n  grid: 16\nextensions:\n  max_resize: 0.25\n"


def git(dest: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(dest), *args], check=True, stdout=subprocess.DEVNULL)


def main(src: Path, dest: Path) -> int:
    if dest.exists():
        sys.exit(f"{dest} already exists; remove it first")
    shutil.copytree(src, dest)
    git(dest, "init", "-q")
    # Keep the diff honest when the folder lives on a Windows drive (/mnt/c).
    git(dest, "config", "core.autocrlf", "false")
    git(dest, "config", "core.filemode", "false")
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "baseline")

    [report] = dest.glob("*.Report")
    for rel, notes in TARGETS.items():
        path = report / "definition" / rel
        doc = jsonfmt.load(path)
        doc.setdefault("annotations", []).extend({"name": n, "value": v} for n, v in notes)
        path.write_bytes(jsonfmt.dump_bytes(doc))
    (report / ".blueprint.yaml").write_text(BLUEPRINT_YAML, encoding="utf-8")
    code = bp(["fmt", "--report", str(report)])
    if code != 0:
        return code
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "blueprint: annotations + .blueprint.yaml + bp fmt (grid 16)")
    print(f"\nProbe ready: {dest}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    sys.exit(main(Path(sys.argv[1]), Path(sys.argv[2])))
