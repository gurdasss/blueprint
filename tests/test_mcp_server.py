"""`bp mcp`: every CLI command as an MCP tool, doing exactly what the command does."""

from __future__ import annotations

import asyncio
import json
import shutil
import sys
from pathlib import Path

import pytest

mcp = pytest.importorskip("mcp")  # the optional extra; `dev` installs it

from mcp import Client, StdioServerParameters

from blueprint import cli
from blueprint.commands import mcp_server

ROOT = Path(__file__).resolve().parent.parent
GUIDELINES = ROOT / "guidelines" / "example.yaml"
SPEC = ROOT / "examples" / "sales-overview.yaml"
CORE_TYPES = sorted(p.stem for p in (ROOT / "blueprint" / "visuals").glob("*.yaml"))


def _subcommands() -> dict:
    return mcp_server.ACTIONS


def _session(steps):
    """Run ``steps(client)`` against an in-process server and return its result."""
    async def go():
        async with Client(mcp_server.build_server()) as client:
            return await steps(client)
    return asyncio.run(go())


def _tools() -> dict:
    async def steps(client):
        return {t.name: t for t in (await client.list_tools()).tools}
    return _session(steps)


# --- the tool surface is the CLI's ---------------------------------------------------------

def test_every_command_but_mcp_is_a_tool():
    assert sorted(_tools()) == sorted(set(_subcommands()) - {"mcp"})


def test_every_flag_is_a_tool_parameter_or_deliberately_excluded():
    """The sweep: a flag added to the CLI and not to the server fails here, by name."""
    tools = _tools()
    for command, actions in _subcommands().items():
        if command == "mcp":
            assert set(actions) == {"help"}
            continue
        expected = set(actions) - set(mcp_server.EXCLUDED)
        params = set(tools[command].input_schema["properties"])
        assert params == expected, (command, sorted(expected ^ params))


def test_required_parameters_match_the_cli():
    tools = _tools()
    for command, actions in _subcommands().items():
        if command == "mcp":
            continue
        required = {d for d, a in actions.items()
                    if d not in mcp_server.EXCLUDED and (a.required or not a.option_strings)}
        assert set(tools[command].input_schema.get("required", [])) == required, command


def test_parameters_carry_the_cli_help_text():
    props = _tools()["apply"].input_schema["properties"]
    assert props["overwrite_edits"]["description"] == _subcommands()["apply"]["overwrite_edits"].help
    assert "file name" in props["spec"]["description"]  # spec identity, so a re-apply updates


def test_read_only_tools_are_marked_read_only():
    tools = _tools()
    assert {n for n, t in tools.items() if t.annotations.read_only_hint} == {
        "describe", "inspect", "check"}


# --- a tool does what the CLI does, byte for byte --------------------------------------------

def _tree(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*"))
            if p.is_file()}


STEPS = [
    ("describe", {"report": "{report}", "guidelines": "{guidelines}"}),
    ("inspect", {"report": "{report}"}),
    ("check", {"report": "{report}", "guidelines": "{guidelines}"}),
    ("apply", {"spec": ["{spec}"], "report": "{report}", "guidelines": "{guidelines}",
               "dry_run": True}),
    ("apply", {"spec": ["{spec}"], "report": "{report}", "guidelines": "{guidelines}"}),
    ("apply", {"spec": ["{spec}"], "report": "{report}", "guidelines": "{guidelines}"}),
    ("fmt", {"report": "{report}", "guidelines": "{guidelines}", "dry_run": True}),
    ("fmt", {"report": "{report}", "guidelines": "{guidelines}"}),
    ("theme", {"report": "{report}", "guidelines": "{guidelines}"}),
    ("manifest", {"report": "{report}", "guidelines": "{guidelines}",
                  "overrides": ["spacing.grid=8"]}),
    ("check", {"report": "{report}", "guidelines": "{guidelines}", "strict": True}),
]


def _fill(args: dict, report: Path, spec: Path) -> dict:
    subs = {"{report}": str(report), "{guidelines}": str(GUIDELINES), "{spec}": str(spec)}
    return {k: ([subs.get(x, x) for x in v] if isinstance(v, list) else subs.get(v, v))
            for k, v in args.items()}


def test_each_tool_matches_the_cli_byte_for_byte(card_chart_fixture, tmp_path, capsys,
                                                 monkeypatch):
    """Run the same sequence through the tools and through `cli.main`, on the same path (the
    report is rebuilt between the two runs): stdout, stderr, exit codes and every file written
    must be identical."""
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "0")
    report, spec = tmp_path / "report", tmp_path / SPEC.name
    shutil.copy(SPEC, spec)

    shutil.copytree(card_chart_fixture.parent, report)
    async def steps(client):
        out = []
        for name, args in STEPS:
            r = await client.call_tool(name, _fill(args, report, spec))
            assert not r.is_error, r.content
            out.append((r.structured_content, _tree(report)))
        return out
    via_tools = _session(steps)

    shutil.rmtree(report)
    shutil.copytree(card_chart_fixture.parent, report)
    for (name, _), (tool, tree) in zip(STEPS, via_tools, strict=True):
        capsys.readouterr()
        code = cli.main(tool["argv"])
        cap = capsys.readouterr()
        assert (code, cap.out, cap.err) == (tool["exit_code"], tool["stdout"], tool["stderr"]), name
        assert _tree(report) == tree, name

    codes = [t["exit_code"] for t, _ in via_tools]
    assert codes[2] == 1 and codes[-1] == 1  # check's findings are a result, not an error
    assert via_tools[4][1] != via_tools[3][1]  # apply wrote; the dry run did not
    assert via_tools[5][1] == via_tools[4][1]  # re-apply is a no-op (the idempotent hint)


def test_paths_are_made_absolute(card_chart_fixture, tmp_path, monkeypatch):
    shutil.copytree(card_chart_fixture.parent, tmp_path / "report")
    monkeypatch.chdir(tmp_path)
    result = mcp_server.run_tool("inspect", {"report": "report"})
    assert result["argv"] == ["inspect", "--report", str(tmp_path / "report"), "--json"]
    assert result["exit_code"] == 0


# --- failures --------------------------------------------------------------------------------

def test_exit_2_is_a_tool_error_and_the_server_keeps_serving(tmp_path):
    async def steps(client):
        bad = await client.call_tool("inspect", {"report": str(tmp_path / "missing")})
        good = await client.call_tool("describe", {"guidelines": str(GUIDELINES)})
        return bad, good
    bad, good = _session(steps)
    assert bad.is_error and "bp: error" in bad.content[0].text
    assert not good.is_error and good.structured_content["exit_code"] == 0


def test_an_unexpected_exception_is_a_tool_error_not_a_crash(monkeypatch):
    def boom(argv):
        raise RuntimeError("unexpected")
    monkeypatch.setattr(cli, "main", boom)
    with pytest.raises(mcp_server.ToolError, match="RuntimeError: unexpected"):
        mcp_server.run_tool("describe", {})


def _without_mcp(*argv: str):
    """Run bp in a fresh interpreter in which `mcp` can't be imported, as on a plain install."""
    import subprocess
    code = ("import sys; sys.modules['mcp'] = None; from blueprint import cli; "
            "sys.exit(cli.main(sys.argv[1:]))")
    return subprocess.run([sys.executable, "-c", code, *argv], capture_output=True, text=True,
                          stdin=subprocess.DEVNULL, check=False)


def test_bp_mcp_without_the_extra_says_how_to_install_it():
    run = _without_mcp("mcp")
    assert run.returncode == 2
    assert "pip install 'blueprint-pbi[mcp]'" in run.stderr


def test_other_commands_never_import_mcp():
    """A plain install has no `mcp`: only `bp mcp` may import it."""
    run = _without_mcp("describe", "--guidelines", str(GUIDELINES), "--json")
    assert run.returncode == 0, run.stderr


# --- a long-lived server sees contract edits -------------------------------------------------

def test_contracts_are_reloaded_on_every_call(tmp_path):
    """The CLI loads contracts once per process; the server lives for a session, in which the
    user may add or edit their own --visuals contracts."""
    mine = tmp_path / "my-visuals"
    mine.mkdir()
    args = {"guidelines": str(GUIDELINES), "visuals": [str(mine)]}
    first = json.loads(mcp_server.run_tool("describe", args)["stdout"])["types"]
    (mine / "waterfall.yaml").write_text(  # the custom-contract shape tests/test_visual_types uses
        "type: waterfall\nvisual_type: waterfallChart\ninherits: column\n", encoding="utf-8")
    second = json.loads(mcp_server.run_tool("describe", args)["stdout"])["types"]
    assert sorted(first) == CORE_TYPES
    assert sorted(second) == sorted([*CORE_TYPES, "waterfall"])


# --- the real transport ----------------------------------------------------------------------

def test_stdio_session_against_bp_mcp():
    """`bp mcp` as a client launches it: a subprocess speaking MCP on stdin/stdout."""
    params = StdioServerParameters(command=sys.executable, args=["-m", "blueprint.cli", "mcp"],
                                   cwd=str(ROOT))
    async def go():
        async with Client(params) as client:
            tools = (await client.list_tools()).tools
            r = await client.call_tool("describe", {"guidelines": str(GUIDELINES)})
            return tools, r
    tools, r = asyncio.run(go())
    assert len(tools) == 7
    assert sorted(json.loads(r.structured_content["stdout"])["types"]) == CORE_TYPES
