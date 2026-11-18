// The integration test, inside VS Code's extension host. No test framework: each check throws.
import * as assert from "assert";
import { spawn } from "child_process";
import * as crypto from "crypto";
import * as fs from "fs";
import * as vscode from "vscode";
import type { BlueprintApi } from "../../src/extension";

const TOOLS = ["apply", "check", "describe", "fmt", "inspect", "manifest", "theme"];

/** Replay a recorded MCP session into a server the way a client does: keep stdin open until
 * every request has its reply (the server stops reading at end of input). */
function replay(def: vscode.McpStdioServerDefinition, session: string): Promise<Map<number, any>> {
  const requests = session.split(/\r?\n/).filter(Boolean).map((l) => JSON.parse(l));
  const want = requests.filter((m) => "id" in m).length;
  return new Promise((resolve, reject) => {
    const child = spawn(def.command, def.args, {
      cwd: vscode.workspace.workspaceFolders?.[0].uri.fsPath, // the session's relative paths
      env: { ...process.env, ...(def.env as Record<string, string>) },
    });
    const replies = new Map<number, any>();
    let buffer = "";
    let stderr = "";
    const timer = setTimeout(() => {
      child.kill();
      reject(new Error(`timed out with ${replies.size}/${want} replies; stderr: ${stderr}`));
    }, 120_000);
    child.stderr.on("data", (d) => (stderr += d));
    child.stdout.on("data", (d) => {
      buffer += d;
      let nl: number;
      while ((nl = buffer.indexOf("\n")) >= 0) {
        const line = buffer.slice(0, nl).trim();
        buffer = buffer.slice(nl + 1);
        if (line) {
          const msg = JSON.parse(line);
          if ("id" in msg) {
            replies.set(msg.id, msg);
          }
        }
      }
      if (replies.size >= want) {
        clearTimeout(timer);
        child.stdin.end();
        resolve(replies);
      }
    });
    child.on("error", reject);
    for (const m of requests) {
      child.stdin.write(JSON.stringify(m) + "\n");
    }
  });
}

export async function run(): Promise<void> {
  const ext = vscode.extensions.all.find((e) => e.packageJSON.name === "blueprint-pbi");
  assert.ok(ext, "the extension under test is loaded");
  // VS Code must activate it by itself (onStartupFinished): a Copilot harness session never runs
  // the MCP discovery that onMcpCollection waits for, so without this the server stays unknown.
  // Checked before anything here calls activate(), which would hide a missing activation event.
  for (let i = 0; i < 300 && !ext.isActive; i++) {
    await new Promise((r) => setTimeout(r, 100));
  }
  assert.ok(ext.isActive, "VS Code activated the extension on its own within 30 s of startup");
  const api = (await ext.activate()) as BlueprintApi; // already active: returns its API

  if (process.platform !== "win32") {
    // Off Windows (e.g. a Remote-WSL window) the bundled engine can't run: no server, no copy.
    assert.deepStrictEqual(api.definitions(), []);
    assert.strictEqual(await api.syncStableCopy(), undefined);
    console.log(`${process.platform}: activated on its own, no server definition (as documented)`);
    return;
  }

  // The command and the provider are contributed and registered.
  assert.ok((await vscode.commands.getCommands(true)).includes("blueprint.setUpOtherClients"));

  // The definition: the bundled exe, `mcp`, no cwd (the Copilot harness only partly supports
  // one), no guidelines by default.
  let [def] = api.definitions();
  assert.ok(def, "one server definition on Windows");
  assert.strictEqual(def.command, vscode.Uri.joinPath(ext.extensionUri, "bin", "bp.exe").fsPath);
  assert.deepStrictEqual(def.args, ["mcp"]);
  assert.strictEqual(def.cwd, undefined);
  assert.strictEqual(def.version, ext.packageJSON.version);
  assert.deepStrictEqual(def.env, {});

  // The guidelines setting reaches the server as BLUEPRINT_GUIDELINES.
  const config = vscode.workspace.getConfiguration("blueprint");
  await config.update("guidelines", "C:\\guidelines\\example.yaml", vscode.ConfigurationTarget.Global);
  [def] = api.definitions();
  assert.deepStrictEqual(def.env, { BLUEPRINT_GUIDELINES: "C:\\guidelines\\example.yaml" });
  await config.update("guidelines", undefined, vscode.ConfigurationTarget.Global);
  [def] = api.definitions();

  // What the extension registers starts a working server: replay a real client session.
  const replies = await replay(def, fs.readFileSync(process.env.BP_TEST_SESSION!, "utf8"));
  const tools = replies.get(2)?.result?.tools?.map((t: any) => t.name).sort();
  assert.deepStrictEqual(tools, TOOLS);
  const describe = replies.get(3)?.result?.structuredContent;
  assert.strictEqual(describe?.exit_code, 0);
  assert.strictEqual(Object.keys(JSON.parse(describe.stdout).types).length, 18, "every visual type");
  for (const [id, reply] of replies) {
    assert.ok(!("error" in reply), `request ${id} failed: ${JSON.stringify(reply.error)}`);
  }
  console.log(`replayed session: ${replies.size} replies, tools: ${tools.join(", ")}`);

  // The stable copy for other MCP clients: same bytes as the bundled exe, kept on a re-sync.
  const stable = await api.syncStableCopy();
  assert.ok(stable && fs.existsSync(stable), "stable copy exists");
  const sha = (p: string) => crypto.createHash("sha256").update(fs.readFileSync(p)).digest("hex");
  assert.strictEqual(sha(stable), sha(def.command));
  const mtime = fs.statSync(stable).mtimeMs;
  assert.strictEqual(await api.syncStableCopy(), stable);
  assert.strictEqual(fs.statSync(stable).mtimeMs, mtime, "an up-to-date copy is not rewritten");
  console.log(`stable copy: ${stable}`);
}
