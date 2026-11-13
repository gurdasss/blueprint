# Move the mouse to a point, wait, and capture the whole screen (probe 50 and later).
#
#   powershell.exe -NoProfile -ExecutionPolicy Bypass -File hover_capture.ps1 <out.png> <x> <y> [settleMs]
#
# The Desktop bridge can only screenshot a report page, which never shows a hover, selection or
# focus state. This drives the real cursor instead and photographs the screen, so a transient
# state can be measured (with scripts/probe_pixels.py) like any other capture. Coordinates are
# physical screen pixels; -1 -1 captures without moving the cursor. -Click left-clicks at the
# point first (a selection persists, so it can be captured without holding the mouse), -Tab sends
# a Tab key (focus). Both change what the report shows: use a throwaway probe copy and never save.
param([string]$Out, [int]$X = -1, [int]$Y = -1, [int]$SettleMs = 900, [switch]$Click, [switch]$Tab)

Add-Type -AssemblyName System.Windows.Forms, System.Drawing
Add-Type @"
using System; using System.Runtime.InteropServices;
public class Cursor {
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int X, int Y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint x, uint y, uint d, int e);
  public static void Click() { mouse_event(0x02, 0, 0, 0, 0); mouse_event(0x04, 0, 0, 0, 0); }
}
"@

if ($X -ge 0 -and $Y -ge 0) { [Cursor]::SetCursorPos($X, $Y) | Out-Null }
if ($Click) { Start-Sleep -Milliseconds 250; [Cursor]::Click() }
if ($Tab) { Start-Sleep -Milliseconds 250; [System.Windows.Forms.SendKeys]::SendWait("{TAB}") }
Start-Sleep -Milliseconds $SettleMs

$bounds = [System.Windows.Forms.SystemInformation]::VirtualScreen
$bmp = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
$gfx = [System.Drawing.Graphics]::FromImage($bmp)
$gfx.CopyFromScreen($bounds.X, $bounds.Y, 0, 0, $bmp.Size)
$bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
$gfx.Dispose(); $bmp.Dispose()
Write-Output ("captured {0}x{1} -> {2}" -f $bounds.Width, $bounds.Height, $Out)
