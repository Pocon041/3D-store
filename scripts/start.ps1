# One-click start for backend (uvicorn) and frontend (vite).
# Auto-loads scripts\.env.local (gitignored) so provider keys are not pasted to shell.
# Processes run detached so closing this shell does not kill them.
#
# Usage:
#   .\scripts\start.ps1                # auto load .env.local
#   .\scripts\start.ps1 -Restart       # kill anything listening on the ports first
#   .\scripts\start.ps1 -NoEnvFile     # ignore .env.local
# Stop:
#   .\scripts\stop.ps1
param(
    [switch]$Restart,
    [switch]$NoEnvFile
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$logs = Join-Path $root "logs"
New-Item -ItemType Directory -Force -Path $logs | Out-Null

# ---- Load .env.local (KEY=VALUE per line, # for comments) ----
function Import-DotEnv([string]$path) {
    if (-not (Test-Path $path)) { return $false }
    Get-Content $path | ForEach-Object {
        $line = $_.Trim()
        if (-not $line) { return }
        if ($line.StartsWith("#")) { return }
        $eq = $line.IndexOf("=")
        if ($eq -lt 1) { return }
        $name  = $line.Substring(0, $eq).Trim()
        $value = $line.Substring($eq + 1).Trim()
        # strip surrounding quotes if any
        if ($value.StartsWith('"') -and $value.EndsWith('"')) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        # Set in current process AND for child processes
        [Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
    return $true
}

if (-not $NoEnvFile) {
    $envFile = Join-Path $PSScriptRoot ".env.local"
    if (Import-DotEnv $envFile) {
        Write-Host "[env] loaded $envFile" -ForegroundColor DarkGray
    } else {
        Write-Host "[env] no .env.local found; using shell env only" -ForegroundColor DarkGray
    }
}

$BackendHost  = if ($env:BACKEND_HOST)  { $env:BACKEND_HOST }  else { "127.0.0.1" }
$BackendPort  = if ($env:BACKEND_PORT)  { $env:BACKEND_PORT }  else { "8000" }
$FrontendPort = if ($env:FRONTEND_PORT) { $env:FRONTEND_PORT } else { "5173" }

if ($env:IMAGE3D_PROVIDER) {
    $tripoState = if ($env:TRIPO_API_KEY) { "tripo key SET" } else { "no tripo key" }
    Write-Host ("[env] IMAGE3D_PROVIDER={0} ({1})" -f $env:IMAGE3D_PROVIDER, $tripoState) -ForegroundColor DarkGray
}

function Test-PortListen([int]$port) {
    $c = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    return $null -ne $c
}

function Stop-Port([int]$port) {
    Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
        ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
}

if ($Restart) {
    Stop-Port $BackendPort
    Stop-Port $FrontendPort
    Remove-Item (Join-Path $logs "backend.pid"),(Join-Path $logs "frontend.pid") -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 300
}

# ---- Backend ----
$venvPython = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "[err] missing $venvPython; run 'python -m venv .venv' and 'pip install -r requirements.txt'" -ForegroundColor Red
    exit 1
}

if (Test-PortListen $BackendPort) {
    Write-Host "[skip] backend port $BackendPort is already in use; skipping start" -ForegroundColor Yellow
} else {
    $beLog = Join-Path $logs "backend.log"
    $beErr = Join-Path $logs "backend.err.log"
    $bePid = Join-Path $logs "backend.pid"
    $beArgs = @("-m","uvicorn","backend.main:app","--host",$BackendHost,"--port",$BackendPort)
    $proc = Start-Process -FilePath $venvPython -ArgumentList $beArgs -WorkingDirectory $root -RedirectStandardOutput $beLog -RedirectStandardError $beErr -PassThru -WindowStyle Hidden
    Set-Content -Path $bePid -Value $proc.Id
    Write-Host "[ok] backend pid=$($proc.Id) port=$BackendPort log=$beLog"
}

# ---- Frontend ----
$front = Join-Path $root "frontend"
if (-not (Test-Path (Join-Path $front "node_modules"))) {
    Write-Host "[info] installing frontend deps via npm install ..." -ForegroundColor Cyan
    Push-Location $front
    npm install
    Pop-Location
}

if (Test-PortListen $FrontendPort) {
    Write-Host "[skip] frontend port $FrontendPort is already in use; skipping start" -ForegroundColor Yellow
} else {
    $feLog = Join-Path $logs "frontend.log"
    $feErr = Join-Path $logs "frontend.err.log"
    $fePid = Join-Path $logs "frontend.pid"
    $feArgs = @("/c","npm","run","dev","--","--port",$FrontendPort,"--strictPort")
    $proc = Start-Process -FilePath "cmd.exe" -ArgumentList $feArgs -WorkingDirectory $front -RedirectStandardOutput $feLog -RedirectStandardError $feErr -PassThru -WindowStyle Hidden
    Set-Content -Path $fePid -Value $proc.Id
    Write-Host "[ok] frontend pid=$($proc.Id) port=$FrontendPort log=$feLog"
}

Write-Host ""
Write-Host "waiting for services ..." -ForegroundColor Cyan
$deadline = (Get-Date).AddSeconds(25)
while ((Get-Date) -lt $deadline) {
    $beReady = Test-PortListen $BackendPort
    $feReady = Test-PortListen $FrontendPort
    if ($beReady -and $feReady) { break }
    Start-Sleep -Milliseconds 500
}

Write-Host ""
Write-Host "ready:" -ForegroundColor Cyan
Write-Host ("  backend  http://{0}:{1}/api/health" -f $BackendHost, $BackendPort) -ForegroundColor Green
Write-Host ("  frontend http://localhost:{0}/"      -f $FrontendPort) -ForegroundColor Green
Write-Host ""
Write-Host "tail logs:  Get-Content logs\backend.log -Tail 30 -Wait" -ForegroundColor DarkGray
Write-Host "stop all :  .\scripts\stop.ps1" -ForegroundColor DarkGray
