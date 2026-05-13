"""把种子商品的 GLB + 缩略图下载到 data/samples/{glb,thumb}/。

下载完成后 backend/products.py 会自动改用本地路径，断网也能演示。

特性：
- 并发下载（默认 6 线程）
- 自动重试（默认 3 次，指数退避）
- 已存在文件自动跳过
- 缩略图自动尝试 .png / .jpg / .webp / .jpeg

用法：
    python scripts/fetch_demo_models.py            # 全量
    python scripts/fetch_demo_models.py --force    # 重新下载
    python scripts/fetch_demo_models.py --jobs 8   # 调并发
"""
from __future__ import annotations

import argparse
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend import config  # noqa: E402
from backend.products import SEED_PRODUCTS  # noqa: E402


_TIMEOUT = 60
_RETRIES = 3
_THUMB_EXTS = (".png", ".jpg", ".jpeg", ".webp")


def _download_one(url: str, dst: Path, timeout: int = _TIMEOUT) -> int:
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(dst.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": "aigc-3d-demo/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp, tmp.open("wb") as f:
        while True:
            chunk = resp.read(128 * 1024)
            if not chunk:
                break
            f.write(chunk)
    tmp.replace(dst)
    return dst.stat().st_size


def _retry_download(url: str, dst: Path, retries: int = _RETRIES) -> tuple[bool, str]:
    last_err = ""
    for attempt in range(1, retries + 1):
        try:
            size = _download_one(url, dst)
            return True, f"{size} bytes (try {attempt})"
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last_err = f"{type(e).__name__}: {e}"
            time.sleep(min(2 ** attempt, 8))
    return False, last_err


def _try_thumb(thumb_url: str, dst_dir: Path, pid: str) -> tuple[bool, str]:
    """thumb_url 末尾可能是 .jpg / .png 等，逐个 ext 尝试。"""
    # 先按原 URL 试一次
    suffix = Path(urlparse(thumb_url).path).suffix.lower() or ".jpg"
    dst = dst_dir / f"{pid}{suffix}"
    ok, info = _retry_download(thumb_url, dst, retries=2)
    if ok:
        return True, f"{dst.name} {info}"

    # 不行的话换其他扩展名探测
    base = thumb_url.rsplit(".", 1)[0]
    for ext in _THUMB_EXTS:
        if ext == suffix:
            continue
        url = base + ext
        dst = dst_dir / f"{pid}{ext}"
        ok, info = _retry_download(url, dst, retries=1)
        if ok:
            return True, f"{dst.name} {info}"
    return False, f"all extensions failed for {pid}"


def _existing_glb(pid: str) -> Path | None:
    p = config.SAMPLES_DIR / "glb" / f"{pid}.glb"
    return p if p.exists() and p.stat().st_size > 0 else None


def _existing_thumb(pid: str) -> Path | None:
    for ext in _THUMB_EXTS:
        p = config.SAMPLES_DIR / "thumb" / f"{pid}{ext}"
        if p.exists() and p.stat().st_size > 0:
            return p
    return None


def fetch_one(product: dict, force: bool = False) -> dict:
    pid = product["id"]
    glb_dir = config.SAMPLES_DIR / "glb"
    thumb_dir = config.SAMPLES_DIR / "thumb"
    report = {"id": pid, "glb": "", "thumb": ""}

    # ---- GLB ----
    glb_dst = glb_dir / f"{pid}.glb"
    if not force and _existing_glb(pid):
        report["glb"] = f"skip ({glb_dst.stat().st_size} bytes)"
    else:
        ok, info = _retry_download(product["model_url"], glb_dst)
        report["glb"] = ("ok " if ok else "FAIL ") + info

    # ---- thumbnail ----
    if not force and _existing_thumb(pid):
        report["thumb"] = f"skip ({_existing_thumb(pid).name})"
    elif product.get("thumbnail_url"):
        ok, info = _try_thumb(product["thumbnail_url"], thumb_dir, pid)
        report["thumb"] = ("ok " if ok else "FAIL ") + info
    else:
        report["thumb"] = "no thumb url"

    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="覆盖已存在文件")
    parser.add_argument("--jobs", type=int, default=6, help="并发线程数")
    args = parser.parse_args()

    print(f"开始下载 {len(SEED_PRODUCTS)} 个商品资源，并发 {args.jobs}")
    started = time.time()

    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = {pool.submit(fetch_one, p, args.force): p["id"] for p in SEED_PRODUCTS}
        for fut in as_completed(futures):
            pid = futures[fut]
            try:
                r = fut.result()
                print(f"[{pid:18}] glb={r['glb']:<40} thumb={r['thumb']}")
            except Exception as e:
                print(f"[{pid:18}] EXCEPTION {e}")

    elapsed = time.time() - started
    print(f"完成，耗时 {elapsed:.1f}s")


if __name__ == "__main__":
    main()
