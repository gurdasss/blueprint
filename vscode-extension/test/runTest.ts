// Runs test/suite inside a real VS Code (@vscode/test-electron 3.1.0: runTests downloads the
// version in VSCODE_VERSION, default 1.101.0, the oldest this extension declares support for).
//
// Needs, in the environment: BP_TEST_WORKSPACE, a folder holding the exe gate's inputs
// (guidelines/, sales-overview.yaml, report/), opened as the workspace; and BP_TEST_SESSION, a
// recorded MCP session (packaging/windows/mcp-session-*.jsonl) to replay into the server the
// extension defines. bin/bp.exe must be in place (the windows-exe workflow copies it there).
import * as path from "path";
import { runTests } from "@vscode/test-electron";

async function main(): Promise<void> {
  const workspace = process.env.BP_TEST_WORKSPACE;
  if (!workspace || !process.env.BP_TEST_SESSION) {
    throw new Error("set BP_TEST_WORKSPACE and BP_TEST_SESSION");
  }
  const root = path.resolve(__dirname, "..", "..");
  await runTests({
    version: process.env.VSCODE_VERSION || "1.101.0",
    extensionDevelopmentPath: root,
    extensionTestsPath: path.resolve(__dirname, "suite", "index"),
    launchArgs: [workspace, "--disable-extensions"],
  });
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
