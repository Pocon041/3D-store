$ErrorActionPreference = "Stop"
$front = Join-Path (Split-Path -Parent $PSScriptRoot) "frontend"
Set-Location $front

if (-not (Test-Path "node_modules")) {
  npm install
}
npm run dev
