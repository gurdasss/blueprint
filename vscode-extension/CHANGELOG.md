# Changelog

## 0.1.2 (2026-11-19)

- Bundles Blueprint 0.12.0. Copilot gets an eighth tool, `init`, which writes starter guidelines,
  layouts and a page spec to edit. `describe` now gives each field's type, sort-by column,
  summarization and format string (null where there is none) and the relationships, and
  `section` returns only the parts you name. A theme finding says to run `theme`, and `apply`
  says when a spec has reached what only a model measure can do.
- README: what a machine with only VS Code, Copilot and Power BI Desktop needs, and the files
  you provide.

## 0.1.1 (2026-11-19)

- Marketplace tags: `power-bi`, `pbip`, `pbir`, `mcp`, `copilot` and the like, in place of the
  single `python` tag that `vsce` derived from the old description's "no Python needed".
- Bundles Blueprint 0.11.1: a broken custom visual contract or `.pbip` file is a clear error
  (`bp: error: ...`, exit 2) instead of a traceback.

## 0.1.0 (2026-11-18)

First version. Registers the bundled Blueprint engine (`bp.exe`, Blueprint 0.10.1 with
`bp mcp`) as an MCP server for Copilot agent mode, with a stable copy of the engine for other
MCP clients. Windows only.
