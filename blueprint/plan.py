"""A Plan is the complete set of file writes a mutating command intends to make.

Commands never touch the disk themselves: they change the in-memory model, ask the
writer for a Plan, and then either print it (``--dry-run``) or apply it. That keeps
dry runs accurate and makes all-or-nothing application possible.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class FileWrite:
    path: Path  # relative to the report folder
    before: bytes | None  # None: file is created
    after: bytes
    changes: tuple[str, ...] = ()  # human-readable summary lines


@dataclass
class Plan:
    root: Path
    writes: list[FileWrite] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def empty(self) -> bool:
        return not self.writes

    def render(self) -> str:
        lines = []
        for w in sorted(self.writes, key=lambda w: w.path.as_posix()):
            lines.append(f"{'A' if w.before is None else 'M'} {w.path.as_posix()}")
            lines.extend(f"    {c}" for c in w.changes)
        if not lines:
            lines.append("No changes.")
        if self.warnings:
            lines.append("")
            lines.append("Warnings:")
            lines.extend(f"  - {w}" for w in self.warnings)
        return "\n".join(lines)
