"""Write a probe's evidence file (docs/probes/NN-name.diff) from its git repo.

Usage:
    python scripts/probe_evidence.py <probe folder> <evidence .diff>

One section per commit after the first ("baseline"): a `######## <commit message>` line, then
that commit's diff, byte for byte (CRLF kept). Desktop's local cache (`.pbi/`) and the probe's own
instructions (STEPS.md, snap.sh) are left out. The `#` lines at the top of an existing evidence
file (what the user saw, redactions) are kept.

Sections replay onto the probe's starting fixture with `git apply`, in order;
tests/test_probe_replay.py does exactly that, so the file must stay complete and exact.
"""

import subprocess
import sys
from pathlib import Path

EXCLUDE = (":!**/.pbi/**", ":!STEPS.md", ":!snap.sh")


def _git(repo: Path, *args: str) -> bytes:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True).stdout


def evidence(repo: Path, header: bytes) -> bytes:
    commits = _git(repo, "rev-list", "--reverse", "HEAD").decode().split()
    out = [header.rstrip(b"\n") + b"\n\n"] if header else []
    for commit in commits[1:]:
        subject = _git(repo, "log", "-1", "--format=%s", commit).strip()
        diff = _git(repo, "show", "--format=", "--binary", commit, "--", ".", *EXCLUDE)
        out.append(b"######## " + subject + b"\n\n" + diff + b"\n")
    return b"".join(out)


def _header(path: Path) -> bytes:
    if not path.exists():
        return b""
    lines = []
    for line in path.read_bytes().split(b"\n"):
        if not line.startswith(b"#") or line.startswith(b"######## "):
            break
        lines.append(line)
    return b"\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    repo, dest = Path(sys.argv[1]), Path(sys.argv[2])
    dest.write_bytes(evidence(repo, _header(dest)))
    print(f"wrote {dest}")
