# setup_shortcut.ps1
# Creates a desktop shortcut for the SAM floating launcher.
# Optionally adds it to the Windows Startup folder so it appears on every login.
#
# Run once from the Sam-Agent directory:
#   powershell -ExecutionPolicy Bypass -File setup_shortcut.ps1
#
# To also auto-start on login, run:
#   powershell -ExecutionPolicy Bypass -File setup_shortcut.ps1 -AutoStart

param(
    [switch]$AutoStart  # pass -AutoStart to also add to Windows Startup folder
)

$ErrorActionPreference = "Stop"

$samDir   = Split-Path -Parent $MyInvocation.MyCommand.Definition
$vbsPath  = Join-Path $samDir "start_launcher.vbs"
$iconPath = Join-Path $samDir "face.png"   # used as reference; shortcut uses wscript icon

# ── Helper: create a .lnk shortcut ──────────────────────────────────────────
function New-Shortcut {
    param($LinkPath, $TargetPath, $Arguments, $WorkDir, $Description)
    $wsh  = New-Object -ComObject WScript.Shell
    $link = $wsh.CreateShortcut($LinkPath)
    $link.TargetPath       = "wscript.exe"
    $link.Arguments        = "`"$TargetPath`""
    $link.WorkingDirectory = $WorkDir
    $link.Description      = $Description
    $link.WindowStyle      = 1
    $link.Save()
    Write-Host "  Created: $LinkPath"
}

# ── 1. Desktop shortcut ──────────────────────────────────────────────────────
$desktopPath = [Environment]::GetFolderPath("Desktop")
$shortcut    = Join-Path $desktopPath "SAM Launcher.lnk"

New-Shortcut -LinkPath   $shortcut `
             -TargetPath $vbsPath `
             -WorkDir    $samDir `
             -Description "Start the SAM floating desktop button"

# ── 2. Startup folder (optional) ────────────────────────────────────────────
if ($AutoStart) {
    $startupDir = [Environment]::GetFolderPath("Startup")
    $startup    = Join-Path $startupDir "SAM Launcher.lnk"

    New-Shortcut -LinkPath   $startup `
                 -TargetPath $vbsPath `
                 -WorkDir    $samDir `
                 -Description "Auto-start SAM floating launcher on login"

    Write-Host ""
    Write-Host "Auto-start entry added. SAM launcher will appear on every login."
}

Write-Host ""
Write-Host "Done. Double-click 'SAM Launcher' on your desktop to start the floating orb."
Write-Host "Click the orb to launch Sam. Drag to reposition it anywhere on screen."
