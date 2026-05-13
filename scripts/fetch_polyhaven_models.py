"""从 Poly Haven（CC0，商用可）批量下载独立 3D 模型作为商城商品。

流程：
1. 调 https://api.polyhaven.com/assets?t=models 拿到全部模型清单。
2. 按 categories 白名单 / 黑名单过滤适合作电商商品的模型。
3. 按热度排序取前 N 个。
4. 对每个模型调 /files API，取 1k 版本的 gltf + 所有引用文件（bin、textures）。
5. 下载到 data/samples/polyhaven/<slug>/，保持相对路径。
6. 拉 thumbnail 到 _thumb.png。
7. 输出 data/polyhaven_products.json 供 backend 使用。

注意：
- Poly Haven 的模型是 .gltf + 独立 .bin + textures；model-viewer 加载 gltf 时浏览器会同目录自动拿。
- 下载大小粗估：100 个模型 × 1-3 MB/个 ≈ 100-300 MB。
- 国内访问 dl.polyhaven.org 走 Cloudflare CDN，通常 OK。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend import config  # noqa: E402


# 适合作电商商品的 Poly Haven categories
_WHITELIST = {
    "furniture", "seating", "table", "shelves",
    "lighting",
    "containers", "kitchenware", "office",
    "decorative",
    "food",
    "electronics", "tools",
    "props",
}
# 明确不要的
_BLACKLIST = {
    "industrial", "nature", "plants", "rocks", "trees",
    "ground cover", "structures", "abstract",
    "construction",
}


def fetch_json(url: str, timeout: int = 30) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "aigc-3d-demo/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _download_file(url: str, dst: Path, timeout: int = 60, chunk: int = 128 * 1024,
                   retries: int = 3) -> int:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() and dst.stat().st_size > 0:
        return dst.stat().st_size
    tmp = dst.with_suffix(dst.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": "aigc-3d-demo/0.1"})
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r, tmp.open("wb") as f:
                while True:
                    data = r.read(chunk)
                    if not data:
                        break
                    f.write(data)
            tmp.replace(dst)
            return dst.stat().st_size
        except Exception as e:
            last_err = e
            time.sleep(min(2 ** attempt, 6))
    # 清理未完成的 .part
    try:
        tmp.unlink(missing_ok=True)
    except Exception:
        pass
    raise RuntimeError(f"{type(last_err).__name__}: {last_err}")


def _score(asset: dict) -> int:
    """粗略打分：优先高下载量 / 多 category 命中白名单。"""
    cats = set(asset.get("categories") or [])
    if cats & _BLACKLIST:
        return -1
    if not (cats & _WHITELIST):
        return -1
    dl = int(asset.get("download_count") or 0)
    # 白名单 category 命中越多加分
    hit = len(cats & _WHITELIST) * 1000
    return dl + hit


def select_assets(all_assets: dict, n: int) -> list[tuple[str, dict]]:
    candidates = []
    for slug, data in all_assets.items():
        s = _score(data)
        if s < 0:
            continue
        candidates.append((s, slug, data))
    candidates.sort(key=lambda x: -x[0])
    return [(slug, data) for _, slug, data in candidates[:n]]


def fetch_one(slug: str, asset_meta: dict, out_dir: Path) -> dict:
    """下载一个模型所有 1k 文件，并返回给 products.py 用的元数据。"""
    result = {"slug": slug, "ok": False, "reason": "", "files": []}
    try:
        files = fetch_json(f"https://api.polyhaven.com/files/{slug}")
    except Exception as e:
        result["reason"] = f"files api failed: {e}"
        return result

    gltf_pool = files.get("gltf") or {}
    # 1k 是最小够用的版本；个别模型没有 1k 就退到 2k
    bucket = gltf_pool.get("1k") or gltf_pool.get("2k") or gltf_pool.get("4k")
    if not bucket or "gltf" not in bucket:
        result["reason"] = "no gltf bucket"
        return result

    model_dir = out_dir / slug
    model_dir.mkdir(parents=True, exist_ok=True)

    gltf_info = bucket["gltf"]
    gltf_url = gltf_info["url"]
    gltf_name = Path(urllib.parse.urlparse(gltf_url).path).name
    gltf_path = model_dir / gltf_name

    try:
        _download_file(gltf_url, gltf_path)
        result["files"].append(gltf_name)
        for rel, info in (gltf_info.get("include") or {}).items():
            # include 是 {"相对路径": {url,size,md5}}，有时候是 "@{url=...}" 形式
            # 保持 gltf 引用的相对路径
            url = info["url"] if isinstance(info, dict) else info
            dst = model_dir / rel
            _download_file(url, dst)
            result["files"].append(rel)
    except Exception as e:
        result["reason"] = f"download error: {e}"
        return result

    # 缩略图
    try:
        thumb_url = f"https://cdn.polyhaven.com/asset_img/primary/{slug}.png?width=512&height=512"
        _download_file(thumb_url, model_dir / "_thumb.png")
    except Exception:
        pass  # 缩略图失败不影响主流程

    result["ok"] = True
    result["gltf_name"] = gltf_name
    result["name"] = asset_meta.get("name")
    result["categories"] = asset_meta.get("categories") or []
    result["tags"] = asset_meta.get("tags") or []
    result["authors"] = list((asset_meta.get("authors") or {}).keys())
    result["download_count"] = asset_meta.get("download_count") or 0
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=84, help="目标商品数（默认 84，加上 Khronos 16 个合计 100）")
    parser.add_argument("--jobs", type=int, default=6, help="并发线程")
    parser.add_argument("--output-json", default="data/polyhaven_products.json")
    args = parser.parse_args()

    print("拉取 Poly Haven 模型清单…")
    t0 = time.time()
    try:
        all_assets = fetch_json("https://api.polyhaven.com/assets?t=models")
    except Exception as e:
        print(f"[error] 无法获取模型列表：{e}")
        return
    print(f"总计 {len(all_assets)} 个，耗时 {time.time()-t0:.1f}s")

    chosen = select_assets(all_assets, args.count)
    print(f"筛选出 {len(chosen)} 个候选")

    out_dir = config.SAMPLES_DIR / "polyhaven"
    out_dir.mkdir(parents=True, exist_ok=True)

    reports: list[dict] = []
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = {
            pool.submit(fetch_one, slug, data, out_dir): slug
            for slug, data in chosen
        }
        for i, fut in enumerate(as_completed(futures), start=1):
            slug = futures[fut]
            try:
                r = fut.result()
            except Exception as e:
                r = {"slug": slug, "ok": False, "reason": f"exception: {e}"}
            reports.append(r)
            tag = "ok" if r.get("ok") else "FAIL"
            print(f"[{i:3}/{len(chosen)}] {tag:4} {slug:30} {r.get('reason', '')}")

    elapsed = time.time() - t0
    ok_count = sum(1 for r in reports if r.get("ok"))
    print(f"下载完成，成功 {ok_count}/{len(reports)}，耗时 {elapsed:.1f}s")

    # 写 polyhaven_products.json 供 backend 读取
    out_json = ROOT / args.output_json
    out_json.parent.mkdir(parents=True, exist_ok=True)
    # 只保留成功的
    successes = [r for r in reports if r.get("ok")]
    out_json.write_text(
        json.dumps(successes, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"已写入 {out_json}，{len(successes)} 条")


if __name__ == "__main__":
    main()
