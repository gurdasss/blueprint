#!/usr/bin/env bash
# Run the Power BI Desktop Bridge CLI (@microsoft/powerbi-desktop-bridge-cli) from WSL.
#
#   bash scripts/desktop.sh status
#   bash scripts/desktop.sh open /mnt/c/Users/<you>/blueprint-probes/21-x/Fixture.pbip
#   bash scripts/desktop.sh reload --pid <pid>
#
# The bridge is a Windows named pipe, so the CLI must run on Windows Node (a WSL install reports
# UNSUPPORTED_OS). Install it in a Windows terminal: npm install -g @microsoft/powerbi-desktop-bridge-cli.
# This calls Windows node.exe on the CLI's script directly (WSL's copy of the Windows PATH is
# frozen at WSL start, and cmd.exe quoting is fragile). Arguments that are WSL paths under /mnt/
# are converted to Windows paths. Output is the CLI's JSON (stdout) and progress (stderr).
set -euo pipefail

NODE="${BRIDGE_NODE:-/mnt/c/Program Files/nodejs/node.exe}"
if [ -z "${BRIDGE_CLI:-}" ]; then
  appdata=$(cd /mnt/c && cmd.exe /c 'echo %APPDATA%' 2>/dev/null | tr -d '\r')
  BRIDGE_CLI="$appdata\\npm\\node_modules\\@microsoft\\powerbi-desktop-bridge-cli\\dist\\cli.js"
fi
[ -x "$NODE" ] || { echo "desktop.sh: no Windows node at $NODE (set BRIDGE_NODE)" >&2; exit 2; }

# The Microsoft Store build of Desktop isn't where the CLI looks; its app alias is
# %LOCALAPPDATA%\Microsoft\WindowsApps\PBIDesktopStore.exe. Pass it through to Windows.
if [ -z "${PBI_DESKTOP_PATH:-}" ]; then
  local_appdata=$(cd /mnt/c && cmd.exe /c 'echo %LOCALAPPDATA%' 2>/dev/null | tr -d '\r')
  store="$local_appdata\\Microsoft\\WindowsApps\\PBIDesktopStore.exe"
  [ -e "$(wslpath -u "$store")" ] && export PBI_DESKTOP_PATH="$store"
fi
if [ -n "${PBI_DESKTOP_PATH:-}" ]; then
  export WSLENV="${WSLENV:+$WSLENV:}PBI_DESKTOP_PATH"
fi

args=()
for a in "$@"; do
  if [[ "$a" == /mnt/* ]]; then args+=("$(wslpath -w "$a")"); else args+=("$a"); fi
done
cd /mnt/c  # a Windows working directory: node.exe can't start in a \\wsl.localhost path
"$NODE" "$BRIDGE_CLI" "${args[@]}" | tr -d '\r'
