# Remove C-drive caches that are likely related to this project.
#
# The script is intentionally conservative: it does not clear global pip/npm
# caches because those are shared by other Python/Node projects.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\cleanup_project_c_caches.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\cleanup_project_c_caches.ps1 -Apply
param(
    [switch]$Apply
)

$ErrorActionPreference = "Continue"

$targets = @(
    Join-Path $env:LOCALAPPDATA "Temp\pytest-of-$env:USERNAME"
)

$hfHub = Join-Path $env:USERPROFILE ".cache\huggingface\hub"
$catvtonRepos = @(
    "models--zhengchong--CatVTON",
    "models--runwayml--stable-diffusion-inpainting"
)
foreach ($name in $catvtonRepos) {
    $targets += Join-Path $hfHub $name
}

function Get-DirSizeMb([string]$path) {
    if (-not (Test-Path $path)) { return 0 }
    $sum = (Get-ChildItem -LiteralPath $path -Recurse -Force -ErrorAction SilentlyContinue |
        Measure-Object -Property Length -Sum).Sum
    return [math]::Round(($sum / 1MB), 2)
}

foreach ($target in $targets) {
    if (-not (Test-Path $target)) { continue }
    $sizeMb = Get-DirSizeMb $target
    if ($Apply) {
        Remove-Item -LiteralPath $target -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "[removed] $target ($sizeMb MB)"
    } else {
        Write-Host "[would remove] $target ($sizeMb MB)"
    }
}

if (-not $Apply) {
    Write-Host ""
    Write-Host "Dry run only. Add -Apply to remove these paths."
}
