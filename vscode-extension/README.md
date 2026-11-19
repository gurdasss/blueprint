# Blueprint for Power BI

Build and check Power BI report pages from YAML page specs, from Copilot agent mode.

This extension carries the [Blueprint](https://github.com/gurdasss/blueprint) engine as a
self-contained Windows program and registers it as an MCP server. **No Python and no pip are
needed**: install the extension, open the folder with your PBIP project, and Blueprint's tools
are available to Copilot.

## Requirements

A machine with only **VS Code, GitHub Copilot and Power BI Desktop** is enough: the extension
carries the engine with its own interpreter and never uses a Python on the machine.

- **Windows x64.** The extension is published for `win32-x64` only; Windows on ARM gets no
  build. Power BI Desktop is Windows-only too.
- **VS Code 1.101 or later**, with **GitHub Copilot** in agent mode (which uses MCP tools).
- **A local folder.** Open the project folder in a normal window. In a Remote-WSL, SSH or Dev
  Container window the extension runs on the remote (Linux) side and registers no server (see
  Limitations).
- **A Power BI project saved as PBIP, in the PBIR report format** (a `definition/` folder), with
  its TMDL semantic model next to it. A `.pbix` file isn't read, and a report in the older
  PBIR-Legacy format (a single `report.json`) is refused: open and save it in a recent Power BI
  Desktop to convert it. Desktop is only needed to look at the result.

### Files you provide

These are plain YAML files, not installs. Copilot can write them using the `describe` tool.

- **Guidelines** (your standards: canvas size, spacing and grid, page rules, palette, typography, layouts). Set its
  absolute path in the `blueprint.guidelines` setting. `describe`, `inspect`, `check` and `fmt`
  also run without one, on Blueprint's defaults; `theme` needs guidelines that set a palette or
  typography.
- **Layouts**, which `apply` places a page's visuals into. Your guidelines point to them
  (`layouts.search_path`).

Ask Copilot to run the `init` tool on an empty folder: it writes a starter set (guidelines with
every key commented, seven layouts and a page spec) to edit, and never overwrites a file.
- **Page specs**, the YAML files `apply` builds pages from.

Examples to start from are in the repository's
[`guidelines/`](https://github.com/gurdasss/blueprint/tree/main/guidelines) (with
`guidelines/layouts/`) and [`template/`](https://github.com/gurdasss/blueprint/tree/main/template)
folders.

### Good to know

- **Absolute paths.** The server's working directory is chosen by the runtime that starts it,
  so give tools absolute paths (see Settings).
- **First start takes a few seconds.** The engine unpacks itself into `%TEMP%` each time it
  starts: about 2-4 s, once per session.
- **No `bp` in the terminal.** The engine isn't added to `PATH`; it is used through MCP. To use
  the same engine from another client, see below.

## What Copilot gets

Eight tools, one per `bp` command. Each runs the command and returns its exit code and output:

| Tool | What it does |
|---|---|
| `init` | Write starter guidelines, layouts and a page spec into a folder, to edit. Never overwrites. |
| `describe` | Everything a page spec can use: visual types and slots, layouts, guideline limits, and with `report`, the model's fields with their types, sort-by columns and format strings, and the relationships. `section` keeps only the parts you name. Read-only. |
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

Give tools absolute paths: the server's working directory is chosen by the editor or Copilot
runtime that starts it, so a relative path may not mean your open folder. Each result echoes
the resolved command line (`argv`), so you can see which file was used.

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
