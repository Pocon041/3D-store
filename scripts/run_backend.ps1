# Windows PowerShell 启动后端
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$BACKEND_HOST = if ($env:BACKEND_HOST) { $env:BACKEND_HOST } else { "0.0.0.0" }
$BACKEND_PORT = if ($env:BACKEND_PORT) { $env:BACKEND_PORT } else { "8000" }

uvicorn backend.main:app --host $BACKEND_HOST --port $BACKEND_PORT --reload
