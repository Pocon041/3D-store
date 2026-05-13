# Stop services started by start.ps1.
# Prefer killing by pid file, fallback to listening port.
$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
$logs = Join-Path $root "logs"

$BackendPort  = if ($env:BACKEND_PORT)  { $env:BACKEND_PORT }  else { "8000" }
$FrontendPort = if ($env:FRONTEND_PORT) { $env:FRONTEND_PORT } else { "5173" }

function Stop-ByPidFile([string]$name, [string]$pidFile) {
    if (Test-Path $pidFile) {
        $procId = (Get-Content $pidFile -Raw).Trim()
        if ($procId -and (Get-Process -Id $procId -ErrorAction SilentlyContinue)) {
            try {
                # also kill child procs (npm -> node, cmd -> npm, etc.)
                Get-CimInstance Win32_Process -Filter "ParentProcessId=$procId" -ErrorAction SilentlyContinue |
                    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
                Stop-Process -Id $procId -Force
                Write-Host "[ok] stopped $name pid=$procId"
            } catch {
                Write-Host "[warn] failed to stop $name pid=$procId : $_" -ForegroundColor Yellow
            }
        }
        Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
    }
}

function Stop-ByPort([string]$name, [int]$port) {
    $cs = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    foreach ($c in $cs) {
        try {
            Stop-Process -Id $c.OwningProcess -Force
            Write-Host "[ok] stopped $name on port $port pid=$($c.OwningProcess)"
        } catch {
            Write-Host "[warn] failed to stop $name on port $port : $_" -ForegroundColor Yellow
        }
    }
}

Stop-ByPidFile "backend"  (Join-Path $logs "backend.pid")
Stop-ByPidFile "frontend" (Join-Path $logs "frontend.pid")
Stop-ByPort    "backend"  $BackendPort
Stop-ByPort    "frontend" $FrontendPort

Write-Host "done."
