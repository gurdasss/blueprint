# Move the mouse to a point, wait, and capture the whole screen (probe 50 and later).
#
#   powershell.exe -NoProfile -ExecutionPolicy Bypass -File hover_capture.ps1 <out.png> <x> <y> [settleMs]
#
# The Desktop bridge can only screenshot a report page, which never shows a hover, selection or
# focus state. This drives the real cursor instead and photographs the screen, so a transient
# state can be measured (with scripts/probe_pixels.py) like any other capture. Coordinates are
# physical screen pixels; -1 -1 captures without moving the cursor.
param([string]$Out, [int]$X = -1, [int]$Y = -1, [int]$SettleMs = 900)

Add-Type -AssemblyName System.Windows.Forms, System.Drawing
Add-Type @"
using System; using System.Runtime.InteropServices;
public class Cursor { [DllImport("user32.dll")] public static extern bool SetCursorPos(int X, int Y); }
"@

if ($X -ge 0 -and $Y -ge 0) { [Cursor]::SetCursorPos($X, $Y) | Out-Null }
Start-Sleep -Milliseconds $SettleMs

$bounds = [System.Windows.Forms.SystemInformation]::VirtualScreen
$bmp = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
$gfx = [System.Drawing.Graphics]::FromImage($bmp)
$gfx.CopyFromScreen($bounds.X, $bounds.Y, 0, 0, $bmp.Size)
$bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
$gfx.Dispose(); $bmp.Dispose()
Write-Output ("captured {0}x{1} -> {2}" -f $bounds.Width, $bounds.Height, $Out)
