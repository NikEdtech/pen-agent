# Register a Scheduled Task that starts pen-agent HTTP at logon
$ErrorActionPreference = "Stop"
$Root = "C:\Users\admin\Code\pen-agent"
$Runner = Join-Path $Root "deploy\windows\run-http.ps1"
$TaskName = "pen-agent-mcp-http"

$action = New-ScheduledTaskAction `
  -Execute "powershell.exe" `
  -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$Runner`""

$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null
Write-Host "Registered scheduled task '$TaskName' (AtLogOn)."
Write-Host "Start now with: Start-ScheduledTask -TaskName $TaskName"
