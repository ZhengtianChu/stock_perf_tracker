$ErrorActionPreference = "Stop"

$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$taskName = "Option Ledger"
$launcher = Join-Path $projectDir "run_hidden.vbs"

$action = New-ScheduledTaskAction `
  -Execute "wscript.exe" `
  -Argument "`"$launcher`"" `
  -WorkingDirectory $projectDir

$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet `
  -MultipleInstances IgnoreNew `
  -RestartCount 3 `
  -RestartInterval (New-TimeSpan -Minutes 1) `
  -StartWhenAvailable `
  -ExecutionTimeLimit (New-TimeSpan -Hours 0) `
  -AllowStartIfOnBatteries

try {
  Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "Start the local Option Ledger web app at login." `
    -Force | Out-Null
  Write-Host "Installed startup task: $taskName"
} catch {
  Write-Host "Scheduled task install failed: $($_.Exception.Message)"
  Write-Host "Falling back to the current user's Startup folder."
  $startupDir = [Environment]::GetFolderPath("Startup")
  $shortcutPath = Join-Path $startupDir "Option Ledger.lnk"
  $shell = New-Object -ComObject WScript.Shell
  $shortcut = $shell.CreateShortcut($shortcutPath)
  $shortcut.TargetPath = "wscript.exe"
  $shortcut.Arguments = "`"$launcher`""
  $shortcut.WorkingDirectory = $projectDir
  $shortcut.Description = "Start the local Option Ledger web app at login."
  $shortcut.Save()
  Write-Host "Installed startup shortcut: $shortcutPath"
}

Write-Host "The app will start in the background after you log in."
Write-Host "Open http://127.0.0.1:8000 in your browser."
