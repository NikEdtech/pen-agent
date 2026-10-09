# Install pen-agent on Windows (run as admin user)
# Usage: powershell -ExecutionPolicy Bypass -File deploy\windows\install.ps1

$ErrorActionPreference = "Stop"
$Root = "C:\Users\admin\Code\pen-agent"
$Venv = Join-Path $Root ".venv"
$TokenFile = Join-Path $Root "deploy\windows\.token"

Write-Host "==> Ensuring repo at $Root"
if (-not (Test-Path $Root)) {
  New-Item -ItemType Directory -Path (Split-Path $Root) -Force | Out-Null
  git clone https://github.com/NikEdtech/pen-agent.git $Root
} else {
  Push-Location $Root
  git pull --ff-only
  Pop-Location
}

Write-Host "==> Creating venv"
python -m venv $Venv
& "$Venv\Scripts\python.exe" -m pip install -U pip setuptools wheel
& "$Venv\Scripts\pip.exe" install -e "$Root[dev]"

if (-not (Test-Path $TokenFile)) {
  $token = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 40 | ForEach-Object { [char]$_ })
  New-Item -ItemType Directory -Path (Split-Path $TokenFile) -Force | Out-Null
  Set-Content -Path $TokenFile -Value $token -NoNewline
  Write-Host "==> Wrote new token to $TokenFile"
} else {
  Write-Host "==> Reusing token at $TokenFile"
}

Write-Host "==> Running dry-run self-test"
& "$Venv\Scripts\pen-agent.exe" thankyou "Test" --message "dry-run ok" --brand "pen-agent"
Write-Host "Install complete."
