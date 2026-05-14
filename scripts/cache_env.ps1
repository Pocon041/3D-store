# Dot-source this script before installs to keep caches inside the repo.
#
# Usage:
#   . .\scripts\cache_env.ps1
#   pip install -r requirements.txt
#   npm install
$root = Split-Path -Parent $PSScriptRoot

function Set-ProjectCacheEnv([string]$name, [string]$relPath) {
    $path = Join-Path $root $relPath
    [Environment]::SetEnvironmentVariable($name, $path, "Process")
    New-Item -ItemType Directory -Force -Path $path | Out-Null
}

Set-ProjectCacheEnv "XDG_CACHE_HOME"        ".cache"
Set-ProjectCacheEnv "HF_HOME"               ".cache\huggingface"
Set-ProjectCacheEnv "HF_HUB_CACHE"          ".cache\huggingface\hub"
Set-ProjectCacheEnv "HUGGINGFACE_HUB_CACHE" ".cache\huggingface\hub"
Set-ProjectCacheEnv "HF_DATASETS_CACHE"     ".cache\huggingface\datasets"
Set-ProjectCacheEnv "TRANSFORMERS_CACHE"    ".cache\huggingface\transformers"
Set-ProjectCacheEnv "DIFFUSERS_CACHE"       ".cache\huggingface\diffusers"
Set-ProjectCacheEnv "TORCH_HOME"            ".cache\torch"
Set-ProjectCacheEnv "PIP_CACHE_DIR"         ".cache\pip"
Set-ProjectCacheEnv "NPM_CONFIG_CACHE"      ".cache\npm"
Set-ProjectCacheEnv "MPLCONFIGDIR"          ".cache\matplotlib"
Set-ProjectCacheEnv "CONDA_PKGS_DIRS"       ".cache\conda\pkgs"
Set-ProjectCacheEnv "CONDA_ENVS_PATH"       ".conda\envs"
Set-ProjectCacheEnv "TEMP"                  ".cache\tmp"
Set-ProjectCacheEnv "TMP"                   ".cache\tmp"
[Environment]::SetEnvironmentVariable("HF_HUB_DISABLE_XET", "1", "Process")
if (-not $env:HF_ENDPOINT) {
    [Environment]::SetEnvironmentVariable("HF_ENDPOINT", "https://hf-mirror.com", "Process")
}

Write-Host ("[env] project cache root: {0}" -f (Join-Path $root ".cache"))
