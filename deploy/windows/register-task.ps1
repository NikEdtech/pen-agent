# Register a Scheduled Task that starts pen-agent HTTP at logon
$ErrorActionPreference = "Stop"
$Root = "C:\Users\admin\Code\pen-agent"
$Runner = Join-Path $Root "deploy\windows\run-http.ps1"
$TaskName = "pen-agent-mcp-http"

$action = New-ScheduledTaskAction `
  -Execute "powershell.exe" `
  -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$Runner`""

$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet `
  -RestartCount 3 `
  -RestartInterval (New-TimeSpan -Minutes 1) `
  -AllowStartIfOnBatteries `
  -DontStopIfGoingOnBatteries `
  -ExecutionTimeLimit (New-TimeSpan -Days 0)

# Prefer current user without DOMAIN\ prefix issues on some Windows setups
try {
  Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
} catch {
  # Fallback via schtasks
  schtasks /Create /TN $TaskName /SC ONLOGON /RL LIMITED /F /TR "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$Runner`"" | Out-Null
}
Write-Host "Registered scheduled task '$TaskName' (AtLogOn)."
Write-Host "Start now with: Start-ScheduledTask -TaskName $TaskName"
