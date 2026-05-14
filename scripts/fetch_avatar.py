"""下载试穿假人台 GLB 到 data/samples/avatars/。

按候选优先级尝试，第一个能下到的就用：

1. Xbot.glb (three.js 官方示例)
   - 来源：mrdoob/three.js Apache-2.0 仓库
   - Mixamo X-Bot 派生，自带标准 mixamorig 骨骼
   - "机器人"质感，没穿衣服，作为试穿假人台体型合适

2. Soldier.glb (three.js 官方示例)
   - 同样自带 mixamorig 骨骼，但身上有军装贴图
   - 备选

下载到 data/samples/avatars/mannequin.glb，
前端通过 /static/samples/avatars/mannequin.glb 直接加载。

用法：
    python scripts/fetch_avatar.py            # 用默认 (Xbot)
    python scripts/fetch_avatar.py --variant soldier
    python scripts/fetch_avatar.py --force
"""
from __future__ import annotations

import argparse
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend import config  # noqa: E402


CANDIDATES = {
    "xbot": [
        "https://cdn.jsdelivr.net/gh/mrdoob/three.js@dev/examples/models/gltf/Xbot.glb",
        "https://raw.githubusercontent.com/mrdoob/three.js/dev/examples/models/gltf/Xbot.glb",
    ],
    "soldier": [
        "https://cdn.jsdelivr.net/gh/mrdoob/three.js@dev/examples/models/gltf/Soldier.glb",
        "https://raw.githubusercontent.com/mrdoob/three.js/dev/examples/models/gltf/Soldier.glb",
    ],
}

TARGET_DIR = config.SAMPLES_DIR / "avatars"
TARGET_FILE = TARGET_DIR / "mannequin.glb"
LICENSE_FILE = TARGET_DIR / "LICENSE.txt"
LICENSE_TEXT = """Mannequin sources used by this demo
==================================

This file is downloaded from the three.js examples repository:
  https://github.com/mrdoob/three.js/tree/dev/examples/models/gltf

three.js is released under the MIT License. The bundled rigged human
models (Xbot.glb, Soldier.glb) are originally derived from Mixamo
(Adobe) and are made available by the three.js authors for
educational / demo purposes.

If you ship this commercially, please confirm the licensing terms
directly at https://www.mixamo.com/ and replace the file with an
asset whose license fits your distribution channel.

To swap in a different mannequin, just overwrite this file:
  data/samples/avatars/mannequin.glb

Recommended free-real-human alternatives you can download manually:
  - Ready Player Me (https://readyplayer.me/)
  - Mixamo X-Bot / Y-Bot (https://www.mixamo.com/)
  - Sketchfab CC0 base meshes
"""


def _download(url: str, dst: Path, timeout: int = 60) -> int:
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


def _try_urls(urls: list[str], dst: Path, retries: int = 2) -> tuple[bool, str]:
    last_err = ""
    for url in urls:
        for attempt in range(1, retries + 1):
            try:
                size = _download(url, dst)
                return True, f"{url} -> {size} bytes (try {attempt})"
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                last_err = f"{type(e).__name__}: {e}"
                time.sleep(min(2 ** attempt, 6))
    return False, last_err


def main() -> int:
    parser = argparse.ArgumentParser(description="下载试穿假人台 GLB")
    parser.add_argument("--variant", choices=list(CANDIDATES.keys()), default="xbot")
    parser.add_argument("--force", action="store_true", help="即便文件已存在也重新下载")
    args = parser.parse_args()

    if TARGET_FILE.exists() and not args.force:
        size = TARGET_FILE.stat().st_size
        print(f"already exists: {TARGET_FILE} ({size} bytes), use --force to redownload")
        return 0

    urls = CANDIDATES[args.variant]
    print(f"downloading mannequin variant={args.variant}")
    ok, info = _try_urls(urls, TARGET_FILE)
    if not ok:
        print(f"FAILED: {info}", file=sys.stderr)
        print("", file=sys.stderr)
        print("Manual fallback options:", file=sys.stderr)
        print("  1. Download any rigged GLB from Mixamo / Ready Player Me /", file=sys.stderr)
        print("     Sketchfab and save it as:", file=sys.stderr)
        print(f"       {TARGET_FILE}", file=sys.stderr)
        print("  2. Re-run the studio; the avatar try-on page will pick it up.", file=sys.stderr)
        return 2

    LICENSE_FILE.write_text(LICENSE_TEXT, encoding="utf-8")
    print(f"saved: {TARGET_FILE}")
    print(f"info:  {info}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
