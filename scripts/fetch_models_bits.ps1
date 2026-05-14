# Robust model fetcher using Windows BITS + hf-mirror.com.
#
# huggingface_hub.snapshot_download keeps deadlocking on hf-mirror's CDN
# (CloseWait connections on a few weights, no progress for 10+ minutes).
# BITS is the Windows-native HTTP downloader: it survives stalled chunks,
# resumes automatically, runs in the background even after PowerShell exits,
# and most importantly bypasses the system IE proxy when -ProxyUsage NoProxy.
#
# We list each repo's files via the HF JSON API once (a tiny 200-byte call),
# then queue every file as its own BITS job. Files already at the right size
# are skipped.
#
# Usage:
#   .\scripts\fetch_models_bits.ps1
#   .\scripts\fetch_models_bits.ps1 -Repos "zhengchong/CatVTON"     # only one
#
# Resulting layout:
#   data/models/<org>--<name>/<file_path_in_repo>
#   data/models/<org>--<name>/subdir/file.safetensors
param(
    [string[]]$Repos = @(
        "booksforcharlie/stable-diffusion-inpainting",
        "zhengchong/CatVTON"
    ),
    # API endpoint: hf-mirror's /api/* keeps 308-redirecting, so we hit the
    # main huggingface.co for the JSON tree call (a few hundred bytes).
    # Real downloads still go to hf-mirror.com.
    [string]$ApiEndpoint = "https://huggingface.co",
    [string]$DlEndpoint  = "https://hf-mirror.com",
    [string]$Revision = "main",
    [int]$MaxConcurrent = 4
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$modelsDir = Join-Path $root "data\models"
New-Item -ItemType Directory -Force -Path $modelsDir | Out-Null

# proxy bypass
$bypass = @(
    "huggingface.co",
    "hf-mirror.com",
    "cdn-lfs.huggingface.co",
    "127.0.0.1",
    "localhost"
) -join ","
$env:NO_PROXY = $bypass
$env:no_proxy = $bypass
$env:HTTPS_PROXY = ""
$env:HTTP_PROXY  = ""
$env:ALL_PROXY   = ""

function Get-RepoFileList {
    param([string]$RepoId, [string]$ApiEndpoint, [string]$Revision)
    # The JSON tree API returns all files (including LFS sizes) in one call.
    $api = "$ApiEndpoint/api/models/$RepoId/tree/$Revision`?recursive=true"
    Write-Host "[list] $api" -ForegroundColor DarkGray
    $entries = Invoke-RestMethod -Uri $api -Method Get -TimeoutSec 30 -UseBasicParsing
    # Each entry has: type ('file'/'directory'), path, size, lfs (optional)
    return $entries | Where-Object { $_.type -eq "file" }
}

function Resolve-LocalPath {
    param([string]$RepoId, [string]$RelPath)
    $name = $RepoId.Replace("/", "--")
    return Join-Path $modelsDir (Join-Path $name $RelPath)
}

function Should-Download {
    param([string]$LocalPath, [long]$ExpectedSize)
    if (-not (Test-Path $LocalPath)) { return $true }
    $existing = (Get-Item $LocalPath).Length
    if ($ExpectedSize -gt 0 -and $existing -ne $ExpectedSize) {
        Write-Host "  [resize] $LocalPath  $existing != $ExpectedSize, retry" -ForegroundColor DarkYellow
        return $true
    }
    return $false
}

# Drain leftover BITS jobs from previous runs ONLY if they are in a final
# state (Transferred / Error / Cancelled). Active Transferring / Connecting
# jobs are kept so we don't clobber a download that's already making progress
# (e.g. user manually started one before re-running this script).
Get-BitsTransfer -ErrorAction SilentlyContinue | Where-Object {
    $_.DisplayName -like "hf-*" -and ($_.JobState -in @("Transferred","Error","Cancelled"))
} | ForEach-Object {
    Write-Host "[clean] removing stale BITS job: $($_.DisplayName) state=$($_.JobState)" -ForegroundColor DarkGray
    if ($_.JobState -eq "Transferred") {
        Complete-BitsTransfer -BitsJob $_
    } else {
        Remove-BitsTransfer -BitsJob $_
    }
}

foreach ($repo in $Repos) {
    Write-Host "`n=== $repo ===" -ForegroundColor Cyan
    $files = Get-RepoFileList -RepoId $repo -ApiEndpoint $ApiEndpoint -Revision $Revision
    Write-Host "[ok] $($files.Count) files in repo"

    # Build the to-download list (skip already-correct files).
    $todo = @()
    foreach ($f in $files) {
        $local = Resolve-LocalPath -RepoId $repo -RelPath $f.path
        $expected = [long]($f.size)
        if (-not (Should-Download -LocalPath $local -ExpectedSize $expected)) {
            continue
        }
        New-Item -ItemType Directory -Force -Path (Split-Path $local) | Out-Null
        $url = "$DlEndpoint/$repo/resolve/$Revision/$($f.path)"
        # BITS DisplayName must not contain forward slashes -> sanitize.
        $safeName = "hf-" + ($repo.Replace('/','--')) + "-" + ($f.path.Replace('/','_'))
        $todo += [pscustomobject]@{
            Url   = $url
            Local = $local
            Size  = $expected
            Name  = $safeName
        }
    }
    Write-Host "[plan] $($todo.Count) files to download"
    if ($todo.Count -eq 0) { continue }

    # Submit BITS jobs in batches.
    $bitsTodo = @()
    foreach ($it in $todo) {
        if ($it.Size -gt 0 -and $it.Size -lt 1MB) {
            Write-Host "  [http] $($it.Url.Substring($DlEndpoint.Length+1))" -ForegroundColor DarkGray
            try {
                $httpUrl = $it.Url.Replace($DlEndpoint, $ApiEndpoint)
                Invoke-WebRequest -Uri $httpUrl -OutFile $it.Local -UseBasicParsing -TimeoutSec 60 -MaximumRedirection 10
            } catch {
                Write-Host "  [warn] HTTP fallback failed, queueing BITS: $($_.Exception.Message)" -ForegroundColor Yellow
                $bitsTodo += $it
            }
        } else {
            $bitsTodo += $it
        }
    }
    if ($bitsTodo.Count -eq 0) { continue }

    $idx = 0
    $nonFinalStates = @("Connecting","Transferring","Queued","Suspended","TransientError","Acknowledged")
    while ($idx -lt $bitsTodo.Count) {
        $batch = $bitsTodo[$idx..([Math]::Min($idx + $MaxConcurrent - 1, $bitsTodo.Count - 1))]
        $batchIds = @()
        foreach ($it in $batch) {
            $sizeMB = if ($it.Size -gt 0) { "{0:N1} MB" -f ($it.Size / 1MB) } else { "?" }
            $relUrl = $it.Url.Substring($DlEndpoint.Length+1)
            Write-Host "  [bits] $relUrl  ($sizeMB)" -ForegroundColor DarkGray
            $j = Start-BitsTransfer `
                -Source $it.Url `
                -Destination $it.Local `
                -ProxyUsage NoProxy `
                -Asynchronous `
                -DisplayName $it.Name
            $batchIds += $j.JobId
        }
        # Wait for this batch to leave non-final states.
        $startTime = Get-Date
        $lastTotalMB = 0.0
        $stuckSince = $null
        do {
            Start-Sleep -Seconds 5
            # Get-BitsTransfer -JobId only accepts a SINGLE GUID. Pull all and filter.
            $current = Get-BitsTransfer -ErrorAction SilentlyContinue | Where-Object { $batchIds -contains $_.JobId }
            if (-not $current) {
                Write-Host "  [warn] could not query BITS jobs, retrying" -ForegroundColor Yellow
                continue
            }
            $alive = @($current | Where-Object { $nonFinalStates -contains $_.JobState })
            $done  = $batchIds.Count - $alive.Count
            $totMB = ([double](($current | Measure-Object -Property BytesTransferred -Sum).Sum)) / 1MB
            $age = ((Get-Date) - $startTime).TotalSeconds
            Write-Host ("  ... batch progress {0}/{1} files done, {2:N1} MB transferred ({3:N0}s)" -f $done, $batchIds.Count, $totMB, $age)

            # Stuck detection: total bytes haven't budged for 3+ minutes.
            if ($totMB -gt $lastTotalMB + 0.5) {
                $lastTotalMB = $totMB
                $stuckSince = $null
            } elseif ($alive.Count -gt 0 -and $totMB -lt $lastTotalMB + 0.5) {
                if ($null -eq $stuckSince) { $stuckSince = Get-Date }
                $stuckSecs = ((Get-Date) - $stuckSince).TotalSeconds
                if ($stuckSecs -gt 180) {
                    Write-Host "  [stuck] no byte progress in 3+ minutes, suspending+resuming" -ForegroundColor Yellow
                    $alive | ForEach-Object {
                        Suspend-BitsTransfer -BitsJob $_ -ErrorAction SilentlyContinue
                        Start-Sleep -Milliseconds 500
                        Resume-BitsTransfer -BitsJob $_ -ErrorAction SilentlyContinue
                    }
                    $stuckSince = Get-Date  # reset timer
                }
            }
        } while ($alive.Count -gt 0)

        # Complete the batch.
        $current = Get-BitsTransfer -ErrorAction SilentlyContinue | Where-Object { $batchIds -contains $_.JobId }
        foreach ($j in $current) {
            switch ($j.JobState) {
                "Transferred" {
                    Complete-BitsTransfer -BitsJob $j
                }
                "Error" {
                    Write-Host "  [err] $($j.DisplayName) -> $($j.ErrorDescription)" -ForegroundColor Red
                    Remove-BitsTransfer -BitsJob $j
                }
                "Cancelled" {
                    Write-Host "  [cancelled] $($j.DisplayName)" -ForegroundColor Yellow
                    Remove-BitsTransfer -BitsJob $j
                }
                default {
                    # Should not happen because the wait loop only exits when no job is in a non-final state.
                    Write-Host "  [unexpected] $($j.DisplayName) state=$($j.JobState) -- leaving alone" -ForegroundColor Yellow
                }
            }
        }
        $idx += $batch.Count
    }
}

Write-Host "`n[done] all repos processed. files at:" -ForegroundColor Green
foreach ($repo in $Repos) {
    $name = $repo.Replace("/", "--")
    $dir  = Join-Path $modelsDir $name
    if (Test-Path $dir) {
        $size = (Get-ChildItem $dir -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum / 1MB
        Write-Host ("  {0,-50} {1,8:N1} MB" -f $name, $size)
    }
}
