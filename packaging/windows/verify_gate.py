"""Compare the frozen exe's gate run with the pip-installed `bp` run (see gate.sh).

    python packaging/windows/verify_gate.py <exe out dir> <reference out dir>

Passes only if
  * the exe's `describe` lists exactly the visual contracts in blueprint/visuals/ (the data
    files made it into the bundle and resolve from it),
  * every command's stdout, stderr and exit code match the reference byte for byte, and
  * the report the exe wrote is byte-identical to the one the reference wrote, and
  * `bp mcp` answered every request of each recorded client session (both protocol eras):
    all seven tools listed and each one called successfully, with the reference's exit codes,
    `describe` listing every visual type, and a missing report coming back as a tool error.
Run it from the repository root, after gate.sh has run both ways.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

COMMANDS = ["version", "describe", "describe-report", "apply", "reapply", "check", "inspect",
            "init", "describe-model"]
MCP_MODES = ["legacy", "auto"]  # the sessions record_mcp_sessions.py records
SESSIONS = Path(__file__).resolve().parent


def replies(path: Path) -> dict[int, dict]:
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        msg = json.loads(line)
        if "id" in msg:
            out[msg["id"]] = msg
    return out


def mcp_problems(mode: str, exe_dir: Path, ref_dir: Path, types: list[str],
                 tools: list[str], version: str) -> list[str]:
    """The exe's replies to a recorded session. The requests are read back from the session
    file (record_mcp_sessions.py): the handshake, tools/list, then one call per tool and a call
    on a missing report, which must be a tool error. Exit codes must match the reference's."""
    where = f"mcp {mode}"
    requests = {m["id"]: m for m in map(json.loads, (SESSIONS / f"mcp-session-{mode}.jsonl")
                                        .read_text(encoding="utf-8").splitlines()) if "id" in m}
    try:
        got, ref = replies(exe_dir / f"mcp-{mode}.out"), replies(ref_dir / f"mcp-{mode}.out")
    except (OSError, ValueError) as exc:
        err = (exe_dir / f"mcp-{mode}.err").read_text(errors="replace")[-300:]
        return [f"{where}: no usable replies ({exc}); stderr: {err}"]
    if sorted(got) != sorted(requests):
        return [f"{where}: replies to requests {sorted(got)}, expected {sorted(requests)}"]
    errors = [f"{where}: request {i} failed: {m['error']}" for i, m in got.items() if "error" in m]
    if errors:
        return errors

    problems = []
    called = set()
    for rid, req in sorted(requests.items()):
        result = got[rid]["result"]
        if req["method"] in ("initialize", "server/discover"):
            info = result.get("serverInfo")
            if req["method"] == "initialize" and (info or {}).get("name") != "blueprint":
                problems.append(f"{where}: serverInfo {info}")
            if info is not None and info.get("version") != version:
                problems.append(f"{where}: server version {info.get('version')} != {version}")
        elif req["method"] == "tools/list":
            listed = sorted(t["name"] for t in result["tools"])
            if listed != tools:
                problems.append(f"{where}: tools {listed} != {tools}")
            if result["tools"] != ref[rid]["result"]["tools"]:
                problems.append(f"{where}: tools/list differs from the reference")
        elif req["method"] == "tools/call":
            name, args = req["params"]["name"], req["params"]["arguments"]
            label = f"{where}: {name} (request {rid})"
            if args.get("report") == "no-such-report":
                if not result.get("isError") or "bp: error" not in result["content"][0]["text"]:
                    problems.append(f"{label}: a missing report was not a tool error")
                continue
            sc = result.get("structuredContent") or {}
            ok = {0, 1} if name == "check" else {0}
            if result.get("isError") or sc.get("exit_code") not in ok:
                problems.append(f"{label}: failed: {str(result)[:300]}")
                continue
            if sc["exit_code"] != (ref[rid]["result"].get("structuredContent") or {}).get("exit_code"):
                problems.append(f"{label}: exit {sc['exit_code']} differs from the reference")
            out = json.loads(sc["stdout"]) if name == "describe" else {}
            if "types" in out and sorted(out["types"]) != types:
                problems.append(f"{label}: visual types differ from blueprint/visuals")
            if args.get("section") and list(out) != args["section"]:
                problems.append(f"{label}: --section {args['section']} returned {list(out)}")
            called.add(name)
    if called != set(tools):
        problems.append(f"{where}: tools never called successfully: {sorted(set(tools) - called)}")
    print(f"{where}: {len(got)}/{len(requests)} replies; tools answered: {', '.join(sorted(called))}")
    return problems


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

    from blueprint import cli  # the installed package: the tools are its subcommands but mcp
    sub = next(a for a in cli.build_parser()._actions if a.__class__.__name__ == "_SubParsersAction")
    tools = sorted(set(sub.choices) - {"mcp"})
    version = (exe_dir / "version.out").read_text().split()[-1]
    for mode in MCP_MODES:
        problems += mcp_problems(mode, exe_dir, ref_dir, expected, tools, version)

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
