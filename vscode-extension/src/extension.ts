// Blueprint for VS Code: a courier for the bundled engine. It registers bin/bp.exe (built by
// the repository's windows-exe workflow) as an MCP server, `bp.exe mcp`, and keeps a copy at a
// stable path for other MCP clients. No engine logic lives here.
//
// API (verified in vscode.d.ts at tags 1.101.0 and 1.146.0): contributes.mcpServerDefinitionProviders
// in package.json, vscode.lm.registerMcpServerDefinitionProvider(id, provider), and
// new McpStdioServerDefinition(label, command, args?, env?, version?) with a settable cwd. The
// contribution generates the activation event onMcpCollection:<id> (mcpConfiguration.ts), and the
// command generates onCommand:<id> (menusExtensionPoint.ts), so package.json needs no
// activationEvents.

import * as crypto from "crypto";
import * as fs from "fs";
import * as path from "path";
import * as vscode from "vscode";

const PROVIDER_ID = "blueprint"; // must match contributes.mcpServerDefinitionProviders[].id
const EXE = "bp.exe";

/** What activate() returns: used by the integration test, and harmless to anyone else. */
export interface BlueprintApi {
  definitions(): vscode.McpStdioServerDefinition[];
  syncStableCopy(): Promise<string | undefined>;
}

export function activate(context: vscode.ExtensionContext): BlueprintApi {
  const log = vscode.window.createOutputChannel("Blueprint", { log: true });
  const bundled = vscode.Uri.joinPath(context.extensionUri, "bin", EXE).fsPath;
  const stableDir = vscode.Uri.joinPath(context.globalStorageUri, "bin").fsPath;
  const changed = new vscode.EventEmitter<void>();
  let warnedPlatform = false;

  function definitions(): vscode.McpStdioServerDefinition[] {
    if (process.platform !== "win32") {
      // Power BI Desktop and the bundled engine are Windows-only. In a Remote-WSL window the
      // extension runs on Linux: there, install the engine with pip (README).
      if (!warnedPlatform) {
        log.warn(`Blueprint's bundled engine runs on Windows only; this is ${process.platform}.`);
        warnedPlatform = true;
      }
      return [];
    }
    if (!fs.existsSync(bundled)) {
      log.error(`The bundled engine is missing: ${bundled}. Reinstall the extension.`);
      return [];
    }
    const env: Record<string, string> = {};
    const guidelines = vscode.workspace.getConfiguration("blueprint").get<string>("guidelines");
    if (guidelines) {
      env.BLUEPRINT_GUIDELINES = guidelines;
    }
    const version = String(context.extension.packageJSON.version);
    const def = new vscode.McpStdioServerDefinition("Blueprint", bundled, ["mcp"], env, version);
    const folder = vscode.workspace.workspaceFolders?.[0];
    if (folder && folder.uri.scheme === "file") {
      def.cwd = folder.uri; // so a tool's relative paths mean the open folder
    }
    return [def];
  }

  /** Copy the bundled exe to a stable path (globalStorage/bin/bp.exe) for other MCP clients.
   * VS Code itself always runs the copy inside the extension, whose path changes per version,
   * so an update never fights a running server. The stable copy is replaced only when its
   * content differs; if another client is running it, the old copy stays until next time. */
  async function syncStableCopy(): Promise<string | undefined> {
    if (process.platform !== "win32" || !fs.existsSync(bundled)) {
      return undefined;
    }
    const target = path.join(stableDir, EXE);
    const marker = path.join(stableDir, `${EXE}.sha256`);
    const hash = crypto.createHash("sha256").update(await fs.promises.readFile(bundled)).digest("hex");
    try {
      if (fs.existsSync(target) && (await fs.promises.readFile(marker, "utf8")).trim() === hash) {
        return target;
      }
    } catch {
      // no marker yet: copy below
    }
    await fs.promises.mkdir(stableDir, { recursive: true });
    const temp = `${target}.tmp`;
    try {
      await fs.promises.copyFile(bundled, temp);
      await fs.promises.rename(temp, target);
      await fs.promises.writeFile(marker, hash);
      log.info(`Engine copied for other MCP clients: ${target}`);
    } catch (err) {
      await fs.promises.rm(temp, { force: true });
      if (!fs.existsSync(target)) {
        log.error(`Could not copy the engine to ${target}: ${err}`);
        return undefined;
      }
      log.warn(`Kept the existing ${target} (probably in use by another MCP client): ${err}`);
    }
    return target;
  }

  context.subscriptions.push(
    log,
    changed,
    vscode.lm.registerMcpServerDefinitionProvider(PROVIDER_ID, {
      onDidChangeMcpServerDefinitions: changed.event,
      provideMcpServerDefinitions: async () => definitions(),
    }),
    vscode.workspace.onDidChangeConfiguration((e) => {
      if (e.affectsConfiguration("blueprint.guidelines")) {
        changed.fire();
      }
    }),
    vscode.workspace.onDidChangeWorkspaceFolders(() => changed.fire()),
    vscode.commands.registerCommand("blueprint.setUpOtherClients", async () => {
      const exe = await syncStableCopy();
      if (!exe) {
        vscode.window.showErrorMessage("Blueprint: the bundled engine is not available here (Windows only). See the Blueprint output.");
        return;
      }
      const claude = `claude mcp add blueprint -- "${exe}" mcp`;
      const pick = await vscode.window.showInformationMessage(
        `Blueprint's engine for other MCP clients: ${exe} (run it with the argument "mcp").`,
        "Copy Claude Code command",
        "Copy path",
      );
      if (pick === "Copy Claude Code command") {
        await vscode.env.clipboard.writeText(claude);
      } else if (pick === "Copy path") {
        await vscode.env.clipboard.writeText(exe);
      }
    }),
  );

  // Keep the stable copy current without delaying activation.
  void syncStableCopy().catch((err) => log.error(`Stable copy failed: ${err}`));

  return { definitions, syncStableCopy };
}

export function deactivate(): void {
  // Nothing to release: VS Code stops the MCP server it started.
}
