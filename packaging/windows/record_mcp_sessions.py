"""Record what a real MCP client sends to `bp mcp`, for the exe gate to replay with no Python.

    python packaging/windows/record_mcp_sessions.py <gate inputs dir>

<gate inputs dir> holds guidelines/, sales-overview.yaml and report/ (see gate.sh). Each session
runs in a scratch copy of it, through `tee`, so the recording is the official SDK client's own
bytes, not a hand-written session. Writes mcp-session-<mode>.jsonl beside this script for both
of the SDK's connection modes: "legacy" (the `initialize` handshake that pre-2026-07-28 clients
send) and "auto" (the 2026-07-28 `server/discover` flow).

Each session calls every tool once, with relative paths (the gate replays it in its own work
dir), then `inspect` on a report that doesn't exist, which must come back as a tool error.
verify_gate.py reads the tool calls back out of these files. Re-run this when the mcp SDK or the
tool surface changes.
"""

from __future__ import annotations

import asyncio
import os
import shlex
import shutil
import sys
import tempfile
from pathlib import Path

from mcp import Client, StdioServerParameters

HERE = Path(__file__).resolve().parent
G = {"guidelines": "guidelines/example.yaml"}
CALLS = [
    ("describe", {"report": "report", **G}),
    ("inspect", {"report": "report"}),
    ("check", {"report": "report", **G}),
    ("apply", {"spec": ["sales-overview.yaml"], "report": "report", **G}),
    ("fmt", {"report": "report", **G}),
    ("theme", {"report": "report", **G, "dry_run": True}),
    ("manifest", {"report": "report", **G, "dry_run": True}),
    ("init", {"dir": "starter-{mode}"}),  # one folder per session: init never overwrites
    ("describe", {"report": "report", **G, "section": ["model"]}),
    ("inspect", {"report": "no-such-report"}),
]


async def record(mode: str, inputs: Path) -> None:
    out = HERE / f"mcp-session-{mode}.jsonl"
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "work"
        shutil.copytree(inputs, work)
        cmd = f"tee {shlex.quote(str(out))} | bp mcp"
        params = StdioServerParameters(command="bash", args=["-c", cmd], cwd=str(work),
                                       env={**os.environ, "SOURCE_DATE_EPOCH": "0"})
        async with Client(params, mode=mode) as client:
            await client.list_tools()
            for name, args in CALLS:
                args = {k: v.replace("{mode}", mode) if isinstance(v, str) else v
                        for k, v in args.items()}
                await client.call_tool(name, args)
    print(f"recorded {out.name}: {len(out.read_text().splitlines())} message(s)")


if __name__ == "__main__":
    for m in ("legacy", "auto"):
        asyncio.run(record(m, Path(sys.argv[1]).resolve()))
