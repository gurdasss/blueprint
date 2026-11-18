# Changelog

## 0.1.1 (2026-11-19)

- Marketplace tags: `power-bi`, `pbip`, `pbir`, `mcp`, `copilot` and the like, in place of the
  single `python` tag that `vsce` derived from the old description's "no Python needed".
- Bundles Blueprint 0.11.1: a broken custom visual contract or `.pbip` file is a clear error
  (`bp: error: ...`, exit 2) instead of a traceback.

## 0.1.0 (2026-11-18)

First version. Registers the bundled Blueprint engine (`bp.exe`, Blueprint 0.10.1 with
`bp mcp`) as an MCP server for Copilot agent mode, with a stable copy of the engine for other
MCP clients. Windows only.
