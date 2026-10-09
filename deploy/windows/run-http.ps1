# Start pen-agent MCP HTTP (streamable) with Bearer token
$ErrorActionPreference = "Stop"
$Root = "C:\Users\admin\Code\pen-agent"
$Venv = Join-Path $Root ".venv"
$TokenFile = Join-Path $Root "deploy\windows\.token"
$LogDir = Join-Path $Root "artifacts\logs"
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

if (-not (Test-Path $TokenFile)) {
  throw "Missing token file $TokenFile — run install.ps1 first"
}
$env:PEN_AGENT_TOKEN = (Get-Content $TokenFile -Raw).Trim()
$env:PEN_AGENT_PROFILE = "jingan"
$env:PEN_AGENT_DRY_RUN_DEFAULT = "1"
$env:PEN_AGENT_HTTP_HOST = "0.0.0.0"
$env:PEN_AGENT_HTTP_PORT = "8765"
$env:PEN_AGENT_ARTIFACT_DIR = Join-Path $Root "artifacts"
$env:PEN_AGENT_REQUIRE_CONFIRM = "1"

# Bind on all interfaces; reach via Tailscale hostname or LAN IP.
# Prefer uvicorn http_app for token middleware.
$py = Join-Path $Venv "Scripts\python.exe"
$args = @(
  "-m", "uvicorn",
  "pen_agent.http_app:create_app",
  "--factory",
  "--host", $env:PEN_AGENT_HTTP_HOST,
  "--port", $env:PEN_AGENT_HTTP_PORT,
  "--log-level", "info"
)
Write-Host "Starting pen-agent HTTP on $($env:PEN_AGENT_HTTP_HOST):$($env:PEN_AGENT_HTTP_PORT)"
Set-Location $Root
& $py @args
