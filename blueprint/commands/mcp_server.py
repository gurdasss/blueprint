"""`bp mcp`: serve every bp command as an MCP tool over stdio.

Each tool runs the CLI itself (``cli.main``) with the argv its arguments spell, and returns what
the CLI would have printed: ``{exit_code, stdout, stderr, argv}``. So a tool does exactly what the
command does, and the exit-code contract carries over: 0 is success, 1 is ``check`` reporting
findings (a normal result, not a failure), and 2 (unreadable input, a refused write) is returned
as a tool error with the CLI's message so the model can correct the call.

Every flag of every command is a tool parameter named after the flag's argparse ``dest``, with the
flag's own help text, except those in ``EXCLUDED``. ``tests/test_mcp_server.py`` walks the parser
and fails if a flag is neither, so a new flag can't be silently missing from the server.

Needs the optional ``mcp`` extra (``pip install blueprint-pbi[mcp]``): ``cli.py`` imports this
module only when ``bp mcp`` runs, so a plain install never imports ``mcp``. Written against
mcp 2.3.0 (``mcp.server.mcpserver.MCPServer``; mcp 2.x removed ``FastMCP``).
"""

from __future__ import annotations

import argparse
import contextlib
import io
import threading
import traceback
from pathlib import Path
from typing import Annotated, Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from blueprint import __version__, cli, slots

# argparse dests that are deliberately not tool parameters, and why.
EXCLUDED = {
    "json": "always passed where a command has it: a tool's caller is a program",
    "github": "GitHub Actions annotations; for CI, not for an agent",
    "grid": "retired; the CLI refuses it and names --set spacing.grid",
    "help": "argparse's own",
}

# Parameters that are file or folder paths: made absolute before the CLI sees them, because the
# server's working directory is wherever the client started it, not the user's shell.
PATH_PARAMS = {"report", "guidelines", "visuals", "spec", "dir"}

# Parameters a tool requires although the CLI defaults them, and why. The CLI's `bp init`
# writes into the current folder, but a server's working directory is whatever the client
# started it in, so a tool call must say where.
REQUIRED_IN_MCP = {"init": {"dir"}}

INSTRUCTIONS = """\
Blueprint builds and checks Power BI PBIP/PBIR report pages from YAML page specs and a
guidelines file. Typical flow: `describe` (with `report`) to learn the visual types, slots,
layouts and model fields a spec can use; write a page spec YAML file; `apply` it (`dry_run`
first to see the planned writes); then `check` the report against the guidelines. Every tool
runs the matching `bp` command and returns its exit code and output. Paths may be relative to
the server's working directory; prefer absolute paths. `guidelines` defaults to
$BLUEPRINT_GUIDELINES. If the report is open in Power BI Desktop, the user must accept
'Apply external changes' after a write."""

# The CLI writes to the process-wide sys.stdout/sys.stderr, and the server runs synchronous tools
# in worker threads (mcp 2.3.0, func_metadata.call_fn: anyio.to_thread.run_sync), so calls are
# serialised to keep one call's output out of another's.
_LOCK = threading.Lock()


def _parser_actions() -> dict[str, dict[str, argparse.Action]]:
    """Each subcommand's argparse actions by dest. The one place the tools read the CLI's flags."""
    sub = next(a for a in cli.build_parser()._actions if isinstance(a, argparse._SubParsersAction))
    return {name: {a.dest: a for a in p._actions} for name, p in sub.choices.items()}


ACTIONS = _parser_actions()


def _help(command: str, dest: str) -> str:
    text = ACTIONS[command][dest].help or ""
    if dest in PATH_PARAMS:
        text += " (a path; relative paths resolve against the server's working directory)"
    if dest == "spec":
        text += (". A spec's identity is its file name (or its id: key), so pass the same file "
                 "again to update the page it built")
    return text


def _argv(command: str, values: dict[str, Any]) -> list[str]:
    """The bp argv for ``command`` with these tool arguments, built from the parser's own flags."""
    argv = [command]
    for dest, value in values.items():
        if value is None or value is False or value == []:
            continue
        action = ACTIONS[command][dest]
        if dest in PATH_PARAMS:
            value = ([str(Path(v).expanduser().absolute()) for v in value] if isinstance(value, list)
                     else str(Path(value).expanduser().absolute()))
        if not action.option_strings:  # positional (apply's spec)
            argv.extend(value if isinstance(value, list) else [value])
        elif value is True:
            argv.append(action.option_strings[0])
        else:
            for v in value if isinstance(value, list) else [value]:
                argv.extend([action.option_strings[0], str(v)])
    if "json" in ACTIONS[command]:
        argv.append("--json")
    return argv


def run_tool(command: str, values: dict[str, Any]) -> dict[str, Any]:
    """Run one bp command in-process and return its exit code and output."""
    argv = _argv(command, values)
    out, err = io.StringIO(), io.StringIO()
    with _LOCK:
        # The CLI loads contracts once per process; a server lives for a whole session, in which
        # the user may edit their own --visuals contracts. The core ones never change.
        slots.contracts.cache_clear()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = cli.main(argv)
            except SystemExit as exc:  # argparse rejected the arguments
                code = exc.code if isinstance(exc.code, int) else 2
            except Exception:  # noqa: BLE001 -- cli.main lets an unexpected error escape; the
                # server must outlive it, and the traceback goes back to the caller as stderr
                traceback.print_exc()
                code = 2
    result = {"exit_code": code, "stdout": out.getvalue(), "stderr": err.getvalue(), "argv": argv}
    if code not in (0, 1):
        raise ToolError(f"bp {' '.join(argv)} failed (exit {code}):\n{result['stderr']}"
                        + (f"\n{result['stdout']}" if result["stdout"] else ""))
    return result


def _p(command: str, dest: str, default: Any = None):
    """A tool parameter's pydantic Field, described by the CLI flag's own help text."""
    return Field(default=default, description=_help(command, dest))


READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=False)


def _writes(idempotent: bool) -> ToolAnnotations:
    return ToolAnnotations(read_only_hint=False, destructive_hint=True,
                           idempotent_hint=idempotent, open_world_hint=False)


Str = str | None
Strs = list[str] | None


def build_server() -> MCPServer:
    server = MCPServer(name="blueprint", version=__version__, instructions=INSTRUCTIONS)

    @server.tool(name="init", description=_sub_help("init") + ". Pass an absolute folder: the "
                 "server's working directory is not necessarily yours",
                 annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False,
                                             idempotent_hint=False, open_world_hint=False))
    def init(
        dir: Annotated[str, _p("init", "dir", ...)],  # named after the CLI's dest
    ) -> dict[str, Any]:
        return run_tool("init", locals())

    @server.tool(name="describe", description=_sub_help("describe"), annotations=READ_ONLY)
    def describe(
        report: Annotated[Str, _p("describe", "report")] = None,
        guidelines: Annotated[Str, _p("describe", "guidelines")] = None,
        overrides: Annotated[Strs, _p("describe", "overrides")] = None,
        visuals: Annotated[Strs, _p("describe", "visuals")] = None,
    ) -> dict[str, Any]:
        return run_tool("describe", locals())

    @server.tool(name="inspect", description=_sub_help("inspect"), annotations=READ_ONLY)
    def inspect(
        report: Annotated[str, _p("inspect", "report", ...)],
    ) -> dict[str, Any]:
        return run_tool("inspect", locals())

    @server.tool(name="check", description=_sub_help("check") + ". Exit 1 means findings were "
                 "reported (a normal result); read stdout", annotations=READ_ONLY)
    def check(
        report: Annotated[str, _p("check", "report", ...)],
        guidelines: Annotated[Str, _p("check", "guidelines")] = None,
        overrides: Annotated[Strs, _p("check", "overrides")] = None,
        visuals: Annotated[Strs, _p("check", "visuals")] = None,
        strict: Annotated[bool, _p("check", "strict", False)] = False,
    ) -> dict[str, Any]:
        return run_tool("check", locals())

    @server.tool(name="apply", description=_sub_help("apply"), annotations=_writes(True))
    def apply(
        spec: Annotated[list[str], _p("apply", "spec", ...)],
        report: Annotated[str, _p("apply", "report", ...)],
        guidelines: Annotated[Str, _p("apply", "guidelines")] = None,
        overrides: Annotated[Strs, _p("apply", "overrides")] = None,
        visuals: Annotated[Strs, _p("apply", "visuals")] = None,
        dry_run: Annotated[bool, _p("apply", "dry_run", False)] = False,
        force_schema: Annotated[bool, _p("apply", "force_schema", False)] = False,
        take_over: Annotated[bool, _p("apply", "take_over", False)] = False,
        overwrite_edits: Annotated[bool, _p("apply", "overwrite_edits", False)] = False,
    ) -> dict[str, Any]:
        return run_tool("apply", locals())

    @server.tool(name="fmt", description=_sub_help("fmt"), annotations=_writes(True))
    def fmt(
        report: Annotated[str, _p("fmt", "report", ...)],
        guidelines: Annotated[Str, _p("fmt", "guidelines")] = None,
        overrides: Annotated[Strs, _p("fmt", "overrides")] = None,
        visuals: Annotated[Strs, _p("fmt", "visuals")] = None,
        dry_run: Annotated[bool, _p("fmt", "dry_run", False)] = False,
        force_schema: Annotated[bool, _p("fmt", "force_schema", False)] = False,
    ) -> dict[str, Any]:
        return run_tool("fmt", locals())

    @server.tool(name="theme", description=_sub_help("theme"), annotations=_writes(False))
    def theme(
        report: Annotated[str, _p("theme", "report", ...)],
        guidelines: Annotated[Str, _p("theme", "guidelines")] = None,
        overrides: Annotated[Strs, _p("theme", "overrides")] = None,
        replace_theme: Annotated[bool, _p("theme", "replace_theme", False)] = False,
        dry_run: Annotated[bool, _p("theme", "dry_run", False)] = False,
        force_schema: Annotated[bool, _p("theme", "force_schema", False)] = False,
    ) -> dict[str, Any]:
        return run_tool("theme", locals())

    @server.tool(name="manifest", description=_sub_help("manifest"), annotations=_writes(False))
    def manifest(
        report: Annotated[str, _p("manifest", "report", ...)],
        guidelines: Annotated[Str, _p("manifest", "guidelines")] = None,
        overrides: Annotated[Strs, _p("manifest", "overrides")] = None,
        visuals: Annotated[Strs, _p("manifest", "visuals")] = None,
        dry_run: Annotated[bool, _p("manifest", "dry_run", False)] = False,
    ) -> dict[str, Any]:
        return run_tool("manifest", locals())

    return server


def _sub_help(command: str) -> str:
    """A subcommand's one-line help, as `bp --help` shows it."""
    sub = next(a for a in cli.build_parser()._actions if isinstance(a, argparse._SubParsersAction))
    return next(a.help for a in sub._choices_actions if a.dest == command)


def run(args: argparse.Namespace) -> int:
    build_server().run("stdio")
    return 0
