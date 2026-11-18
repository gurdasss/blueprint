# Blueprint for Power BI

Build and check Power BI report pages from YAML page specs, from Copilot agent mode.

This extension carries the [Blueprint](https://github.com/gurdasss/blueprint) engine as a
self-contained Windows program and registers it as an MCP server. **No Python and no pip are
needed**: install the extension, open the folder with your PBIP project, and Blueprint's tools
are available to Copilot.

## Requirements

- Windows (x64). Power BI Desktop is Windows-only, and so is the bundled engine.
- VS Code 1.101 or later, with GitHub Copilot (agent mode, which uses MCP tools).
- A Power BI project saved as **PBIP** with the **PBIR** report format, with its TMDL semantic
  model next to it. Power BI Desktop is only needed to look at the result.

## What Copilot gets

Seven tools, one per `bp` command. Each runs the command and returns its exit code and output:

| Tool | What it does |
|---|---|
| `describe` | Everything a page spec can use: visual types and slots, layouts, guideline limits, and with `report`, the model's fields. Read-only. |
| `inspect` | The report's pages, visuals, IDs and positions. Read-only. |
| `check` | Validate the report against the guidelines. Read-only. Exit 1 means findings. |
| `apply` | Create or update pages from page spec files. `dry_run` shows the planned writes. |
| `fmt` | Snap visuals to the guidelines grid. |
| `theme` | Write a theme from the guidelines and make the report use it. |
| `manifest` | Regenerate the report's Blueprint manifest. |

A typical request: *"Describe what I can build from Sales.Report, write a page spec for a sales
overview, apply it with a dry run first, then check the report."* If the report is open in
Power BI Desktop, accept **Apply external changes** after a write.

## Settings

- `blueprint.guidelines`: absolute path to your guidelines YAML file. Every tool uses it unless
  a call names its own. See the
  [guidelines documentation](https://github.com/gurdasss/blueprint#guidelines-and-layering).

Tools resolve relative paths against the first folder open in VS Code. Absolute paths are safest.

## Using the engine from other MCP clients

Run **Blueprint: Set Up for Other MCP Clients** from the Command Palette. It shows a stable
path to the engine (outside the extension's own folder, so it survives extension updates) and
can copy a ready-made Claude Code command, `claude mcp add blueprint -- "<path>" mcp`. Any
client that launches a stdio MCP server can use that path with the argument `mcp`.

## Limitations

- **Remote-WSL, SSH and Dev Container windows**: the extension then runs on the remote
  (Linux) side, where the bundled Windows engine can't run, and registers no server. There,
  install the engine with `pip install "blueprint-pbi[mcp]"` and add `bp mcp` as an MCP server.
- Blueprint is pre-alpha. It only writes report files it can validate, never deletes, and
  refuses to undo edits you made in Desktop unless told to; still, keep your project in git.

## Licence

MIT. Blueprint's source, documentation and issue tracker:
<https://github.com/gurdasss/blueprint>.
