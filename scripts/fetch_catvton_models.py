"""Pre-fetch the model weights CatVTON needs from huggingface mirror.

Downloads to data/models/<org>--<name> via huggingface_hub.snapshot_download
with local_dir (flat layout, no Windows symlinks). Uses https://hf-mirror.com
so it works inside the GFW.

Why local_dir instead of hub cache: hf-mirror's CDN sometimes hangs with
multi-worker concurrent connections; using max_workers=1 + a short
HF_HUB_DOWNLOAD_TIMEOUT makes it fail fast on a stuck connection so
subsequent retries make progress.

Models pulled:
  1. booksforcharlie/stable-diffusion-inpainting   (~4 GB; SD-1.5 inpaint base)
  2. zhengchong/CatVTON                            (~5 GB; CatVTON weights + DensePose/SCHP ckpts)

Idempotent: re-run resumes from where it stopped.

Usage:
    .conda\\envs\\catvton\\python.exe scripts\\fetch_catvton_models.py
    .conda\\envs\\catvton\\python.exe scripts\\fetch_catvton_models.py --base-only
    .conda\\envs\\catvton\\python.exe scripts\\fetch_catvton_models.py --no-base
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = PROJECT_ROOT / "data" / "models"


def _setup_env() -> Path:
    """Force HF cache into the project .cache so C: is not polluted."""
    cache = PROJECT_ROOT / ".cache" / "huggingface"
    hub = cache / "hub"
    hub.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    os.environ["HF_HOME"] = str(cache)
    os.environ["HF_HUB_CACHE"] = str(hub)
    os.environ["HUGGINGFACE_HUB_CACHE"] = str(hub)
    os.environ["TRANSFORMERS_CACHE"] = str(cache / "transformers")
    os.environ["DIFFUSERS_CACHE"] = str(cache / "diffusers")
    os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
    # Make stuck connections fail fast (default is 10s but no overall timeout).
    os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "20")
    # Bypass system proxy for huggingface/mirror in case Windows IE proxy is on.
    bypass = ",".join([
        os.environ.get("NO_PROXY", ""),
        "huggingface.co",
        "hf-mirror.com",
        "cdn-lfs.huggingface.co",
        "127.0.0.1",
        "localhost",
    ]).strip(",")
    os.environ["NO_PROXY"] = bypass
    os.environ["no_proxy"] = bypass
    return hub


def _local_dir_for(repo_id: str) -> Path:
    """data/models/<org>--<name>/  matches CatVTON's `--resume-path` convention."""
    return MODELS_DIR / repo_id.replace("/", "--")


def _download(repo_id: str, retries: int = 6) -> Path:
    from huggingface_hub import snapshot_download  # type: ignore

    local_dir = _local_dir_for(repo_id)
    local_dir.mkdir(parents=True, exist_ok=True)

    last_err = ""
    for attempt in range(1, retries + 1):
        try:
            print(f"[fetch] {repo_id}  attempt {attempt}/{retries} -> {local_dir}", flush=True)
            t0 = time.time()
            path = snapshot_download(
                repo_id=repo_id,
                local_dir=str(local_dir),
                # Single worker -> slower peak speed but won't deadlock when
                # hf-mirror CDN starves a few connections.
                max_workers=1,
                # etag_timeout default is fine, the real fix is HF_HUB_DOWNLOAD_TIMEOUT above.
                etag_timeout=15,
            )
            dt = time.time() - t0
            print(f"[ok]    {repo_id} -> {path} ({dt:.1f}s)", flush=True)
            return Path(path)
        except Exception as e:  # network / hash / disk
            last_err = f"{type(e).__name__}: {e}"
            print(f"[warn]  {repo_id}: {last_err}", flush=True)
            backoff = min(5 * attempt, 30)
            print(f"[warn]  retrying in {backoff}s", flush=True)
            time.sleep(backoff)
    raise RuntimeError(f"failed to fetch {repo_id} after {retries} attempts: {last_err}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Pre-fetch CatVTON models from hf-mirror.")
    parser.add_argument("--base-only", action="store_true", help="only the SD inpainting base")
    parser.add_argument("--no-base", action="store_true", help="skip the SD inpainting base")
    parser.add_argument(
        "--base-repo",
        default=os.environ.get("CATVTON_BASE_MODEL_PATH", "booksforcharlie/stable-diffusion-inpainting"),
    )
    parser.add_argument(
        "--catvton-repo",
        default=os.environ.get("CATVTON_RESUME_PATH", "zhengchong/CatVTON"),
    )
    args = parser.parse_args()

    hub = _setup_env()
    print(f"[env] HF_ENDPOINT={os.environ['HF_ENDPOINT']}")
    print(f"[env] HF_HUB_CACHE={hub}")
    print(f"[env] models out dir = {MODELS_DIR}")

    try:
        if not args.no_base:
            _download(args.base_repo)
        if not args.base_only:
            _download(args.catvton_repo)
    except Exception as e:
        print(f"[err] {e}", file=sys.stderr)
        return 2

    print("[done] all CatVTON models cached locally.")
    print(f"       SD inpaint base : {_local_dir_for(args.base_repo)}")
    print(f"       CatVTON weights : {_local_dir_for(args.catvton_repo)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
