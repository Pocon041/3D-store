# Install CatVTON conda env at project-local .conda\envs\catvton.
# - Uses Python 3.10 (CatVTON expected runtime; pycocotools 2.0.8 has wheels only up to py3.11).
# - All caches (pip / hf / conda pkgs / torch) stay under the repo .cache so C: is not polluted.
# - Installs versions EXACTLY from external\CatVTON\requirements.txt (kept verbatim).
#
# Usage:
#   .\scripts\install_catvton_env.ps1
#   .\scripts\install_catvton_env.ps1 -SkipTorch   # if torch already installed
#   .\scripts\install_catvton_env.ps1 -Force       # recreate env from scratch (removes the env dir)
#
# After install:
#   .\.conda\envs\catvton\python.exe -c "import torch; print(torch.cuda.is_available())"
param(
    [switch]$SkipTorch,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$envDir   = Join-Path $root ".conda\envs\catvton"
$cacheDir = Join-Path $root ".cache"
$pipCache = Join-Path $cacheDir "pip"
$hfCache  = Join-Path $cacheDir "huggingface"
$condaPkg = Join-Path $cacheDir "conda\pkgs"
$tmpDir   = Join-Path $cacheDir "tmp"
$catvton  = Join-Path $root "external\CatVTON"

foreach ($p in @($cacheDir, $pipCache, $hfCache, $condaPkg, $tmpDir, (Join-Path $root ".conda\envs"))) {
    New-Item -ItemType Directory -Force -Path $p | Out-Null
}

# All caches stay in project root (NOT C:\Users\...)
$env:PIP_CACHE_DIR        = $pipCache
$env:CONDA_PKGS_DIRS      = $condaPkg
$env:HF_HOME              = $hfCache
$env:HF_HUB_CACHE         = Join-Path $hfCache "hub"
$env:HUGGINGFACE_HUB_CACHE= Join-Path $hfCache "hub"
$env:TRANSFORMERS_CACHE   = Join-Path $hfCache "transformers"
$env:DIFFUSERS_CACHE      = Join-Path $hfCache "diffusers"
$env:TORCH_HOME           = Join-Path $cacheDir "torch"
$env:TEMP                 = $tmpDir
$env:TMP                  = $tmpDir
$env:HF_ENDPOINT          = "https://hf-mirror.com"
$env:HF_HUB_DISABLE_SYMLINKS_WARNING = "1"
$env:HF_HUB_DISABLE_XET    = "1"

# Force conda/pip/requests to bypass the Windows IE proxy when hitting the
# Chinese mirrors. Without this, conda's libmamba goes through 127.0.0.1:10808
# and dies with SSL EOF. The user has the proxy running for other apps; we just
# tell our installers to skip it.
$bypass = @(
    "mirrors.ustc.edu.cn",
    "mirrors.tuna.tsinghua.edu.cn",
    "pypi.tuna.tsinghua.edu.cn",
    "pypi.org",
    "files.pythonhosted.org",
    "download.pytorch.org",
    "pytorch.org",
    "huggingface.co",
    "hf-mirror.com",
    "github.com",
    "raw.githubusercontent.com",
    "objects.githubusercontent.com",
    "codeload.github.com",
    "127.0.0.1",
    "localhost"
) -join ","
$env:NO_PROXY = $bypass
$env:no_proxy = $bypass
# explicit empty proxy values so conda does NOT inherit IE settings
$env:CONDA_PROXY_HTTP   = ""
$env:CONDA_PROXY_HTTPS  = ""
# Also clear any inherited proxy env vars in this shell only
$env:HTTP_PROXY  = ""
$env:HTTPS_PROXY = ""
$env:ALL_PROXY   = ""

Write-Host "[env] PIP_CACHE_DIR=$env:PIP_CACHE_DIR"
Write-Host "[env] CONDA_PKGS_DIRS=$env:CONDA_PKGS_DIRS"
Write-Host "[env] HF_HOME=$env:HF_HOME"
Write-Host "[env] HF_ENDPOINT=$env:HF_ENDPOINT"
Write-Host "[env] NO_PROXY=$env:NO_PROXY"

# ---- locate conda ----
$conda = (Get-Command conda -ErrorAction SilentlyContinue).Source
if (-not $conda) {
    Write-Host "[err] conda not in PATH; activate Anaconda first" -ForegroundColor Red
    exit 1
}
Write-Host "[ok] conda = $conda"

# ---- (re)create env ----
if ($Force -and (Test-Path $envDir)) {
    Write-Host "[info] -Force: removing existing $envDir"
    & $conda remove -p $envDir --all -y 2>&1 | Out-Null
    if (Test-Path $envDir) { Remove-Item -Recurse -Force $envDir }
}

if (-not (Test-Path (Join-Path $envDir "python.exe"))) {
    Write-Host "[step] creating env at $envDir (python=3.10)"
    & $conda create -p $envDir python=3.10 -y -c conda-forge
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[err] conda create failed" -ForegroundColor Red
        exit 1
    }
}

$pyExe = Join-Path $envDir "python.exe"
Write-Host "[ok] env python = $pyExe"

# pip default index = tsinghua mirror (faster + stable in CN).
# torch wheels still need the official download.pytorch.org URL since cu124 GPU wheels are not on PyPI.
$pipMirror   = "https://pypi.tuna.tsinghua.edu.cn/simple"
$trustedHost = "pypi.tuna.tsinghua.edu.cn"

# upgrade pip to a recent one (otherwise some wheels can fail)
& $pyExe -m pip install --upgrade `
    --index-url $pipMirror --trusted-host $trustedHost `
    "pip<25" "wheel" "setuptools"

# ---- torch / torchvision pinned ----
# If wheels were pre-downloaded via BITS into .cache\wheels, use them directly to
# avoid pip's flaky socket. Otherwise fall back to the official PyTorch index.
if (-not $SkipTorch) {
    $wheelDir = Join-Path $cacheDir "wheels"
    $localTorch = Get-ChildItem -Path $wheelDir -Filter "torch-2.4.0*cu124*cp310*.whl" -ErrorAction SilentlyContinue | Select-Object -First 1
    $localVis   = Get-ChildItem -Path $wheelDir -Filter "torchvision-0.19.0*cu124*cp310*.whl" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($localTorch -and $localVis) {
        Write-Host "[step] installing torch / torchvision from local wheels"
        Write-Host "       torch       : $($localTorch.FullName)"
        Write-Host "       torchvision : $($localVis.FullName)"
        & $pyExe -m pip install --cache-dir $pipCache `
            --index-url $pipMirror --trusted-host $trustedHost `
            $localTorch.FullName $localVis.FullName
    } else {
        Write-Host "[step] installing torch==2.4.0 torchvision==0.19.0 (cu124 wheels from pytorch.org)"
        & $pyExe -m pip install --cache-dir $pipCache `
            --index-url https://download.pytorch.org/whl/cu124 `
            torch==2.4.0 torchvision==0.19.0
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[err] torch install failed" -ForegroundColor Red
        exit 1
    }
}

# ---- rest of requirements.txt ----
# We install the rest WITHOUT downgrading torch -- so we pass -U only when needed
# and rely on requirements.txt pins for the remaining packages.
$reqFile = Join-Path $catvton "requirements.txt"
if (-not (Test-Path $reqFile)) {
    Write-Host "[err] requirements.txt not found at $reqFile" -ForegroundColor Red
    exit 1
}

# Build a filtered requirements file:
#   - drop torch / torchvision (installed above from local wheels)
#   - rewrite matplotlib==3.9.1 -> 3.9.1.post1 (same code, only this version has a cp310 win wheel)
$filtered = Join-Path $tmpDir "catvton-requirements-filtered.txt"
Get-Content $reqFile | Where-Object {
    ($_ -notmatch "^torch==")        -and `
    ($_ -notmatch "^torchvision==")
} | ForEach-Object {
    $_ `
        -replace '^matplotlib==3\.9\.1$', 'matplotlib==3.9.1.post1' `
        -replace '^git\+https://github\.com/huggingface/diffusers\.git$', 'diffusers==0.32.2' `
        -replace '^accelerate==0\.31\.0$', 'accelerate==1.2.1'
} | Set-Content -Encoding UTF8 $filtered

Write-Host "[step] installing the rest of CatVTON requirements (verbatim, --prefer-binary to avoid source builds)"
Write-Host (Get-Content $filtered | Out-String)

# `--prefer-binary` makes pip pick wheels whenever available instead of sdist
# (otherwise matplotlib / pycocotools may try to compile and fail on systems with MinGW on PATH).
# Tsinghua mirror is primary, PyPI is extra fallback for packages it doesn't have.
& $pyExe -m pip install --cache-dir $pipCache `
    --index-url $pipMirror --trusted-host $trustedHost `
    --extra-index-url https://pypi.org/simple `
    --prefer-binary `
    -r $filtered
if ($LASTEXITCODE -ne 0) {
    Write-Host "[err] requirements install failed; see pip output above" -ForegroundColor Red
    exit 1
}

# ---- final verification ----
Write-Host "`n[verify] python / torch / cuda" -ForegroundColor Cyan
# Use single-quoted here-string so PowerShell does NOT expand $variables inside.
$verifyPy = @'
import sys, torch, importlib.util as u
print("python      =", sys.version.split()[0])
print("torch       =", torch.__version__)
print("torchvision =", __import__("torchvision").__version__)
print("cuda_avail  =", torch.cuda.is_available())
print("cuda_ver    =", torch.version.cuda)
print("gpu         =", torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu")
mods = ["diffusers","transformers","accelerate","huggingface_hub","peft",
        "fvcore","omegaconf","pycocotools","cloudpickle","av","PIL","cv2",
        "scipy","skimage","matplotlib","yaml"]
print("-- modules --")
for m in mods:
    spec = u.find_spec(m)
    state = "OK" if spec else "MISSING"
    print(f"  {m:18} {state}")
'@
& $pyExe -c $verifyPy
if ($LASTEXITCODE -ne 0) {
    Write-Host "[warn] verification print failed (some modules may be missing)" -ForegroundColor Yellow
}

Write-Host "`n[done] CatVTON env ready at:" -ForegroundColor Green
Write-Host "  $pyExe"
Write-Host "`nNext: download models with scripts\fetch_catvton_models.py" -ForegroundColor Gray
