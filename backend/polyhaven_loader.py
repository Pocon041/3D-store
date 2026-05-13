"""把 Poly Haven 下载得到的元数据转成商城商品。

依赖：
- data/polyhaven_products.json 由 scripts/fetch_polyhaven_models.py 生成
- data/samples/polyhaven/<slug>/ 下有 .gltf + .bin + textures + _thumb.png

数据合成规则：
- category: 按 Poly Haven categories 映射到 home/collectibles/digital/fresh/toys/apparel
- price / stock: 按 slug hash 稳定生成，避免每次刷新都变
- description: 基于 tags + name + author 组装
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from . import config


_JSON_PATH = config.PROJECT_ROOT / "data" / "polyhaven_products.json"
_ASSETS_SUBDIR = "polyhaven"  # data/samples/polyhaven/

# Poly Haven 原始类目 → 商城类目
_CATEGORY_MAP: dict[str, str] = {
    # 家居功能件
    "furniture": "home",
    "seating": "home",
    "table": "home",
    "shelves": "home",
    "bed": "home",
    "lighting": "home",
    "containers": "home",
    "appliances": "home",
    # 装饰艺术 → 收藏
    "decorative": "collectibles",
    "statues": "collectibles",
    "vases": "collectibles",
    "wall decoration": "collectibles",
    # 生鲜/食物
    "food": "fresh",
    "dishes": "fresh",
    # 数码/电子/办公
    "electronics": "digital",
    "tools": "digital",
    "office": "digital",
    "books": "digital",
}

# 当商品只命中 "props"（或 rigged/collection 等不可用分类）时，用 tags 兜底
_TAG_RULES: list[tuple[tuple[str, ...], str]] = [
    # tags 命中关键词 → 商城类目
    (("toy", "kids", "child", "doll", "plush", "stuffed"), "toys"),
    (("sport", "ball", "football", "soccer", "baseball", "basketball"), "toys"),
    (("weapon", "sword", "cannon", "gun", "knife", "armor"), "collectibles"),
    (("statue", "bust", "sculpture", "art", "ornament"), "collectibles"),
    (("camera", "phone", "radio", "tv", "television", "computer", "console", "cassette"), "digital"),
    (("clock", "watch", "mechanical"), "digital"),
    (("food", "fruit", "cake", "cheese", "bread", "meat", "fish", "can", "bottle", "drink"), "fresh"),
    (("bag", "shoe", "hat", "scarf", "glove"), "apparel"),
]

# 每个商城类目的价格区间
_PRICE_RANGE: dict[str, tuple[int, int]] = {
    "home": (180, 4800),
    "collectibles": (480, 9800),
    "digital": (280, 3800),
    "fresh": (20, 280),
    "toys": (60, 980),
    "apparel": (180, 1580),
}


def _stable_int(seed: str, lo: int, hi: int) -> int:
    """按 slug 稳定生成 [lo, hi] 的整数。"""
    h = int(hashlib.md5(seed.encode("utf-8")).hexdigest(), 16)
    return lo + h % (hi - lo + 1)


def _pick_category(poly_categories: list[str], tags: list[str] | None = None) -> str:
    """从 Poly Haven categories 中挑一个映射到商城类目。

    优先级：
    1. categories 在白名单里 → 直接映射
    2. tags 命中 _TAG_RULES → 对应类目
    3. 默认 home
    """
    for c in poly_categories:
        if c in _CATEGORY_MAP:
            return _CATEGORY_MAP[c]
    tagset = {t.lower() for t in (tags or [])}
    for keywords, target in _TAG_RULES:
        if tagset & set(keywords):
            return target
    return "home"


def _name_cn(raw_name: str) -> str:
    """粗略把英文名做成"更像商品"的中文展示。保留原英文。"""
    # 简单前缀规则：看几个常见关键词（仅装饰用途，真实业务可用翻译 API）
    name_lower = raw_name.lower()
    prefix_map = [
        ("chair", "典藏"), ("sofa", "沙龙"), ("table", "精工"),
        ("lamp", "灯饰"), ("lantern", "庭院"), ("chandelier", "吊灯"),
        ("vase", "装饰"), ("bust", "艺术"),
        ("statue", "雕塑"), ("drawer", "收纳"), ("cabinet", "收纳"),
        ("shelf", "展示"), ("shelves", "展示"),
        ("clock", "时计"), ("camera", "经典"),
        ("duck", "玩趣"), ("gnome", "趣味"),
    ]
    for kw, prefix in prefix_map:
        if kw in name_lower:
            return f"{prefix} · {raw_name}"
    return raw_name


def _description_cn(raw_name: str, categories: list[str], tags: list[str], author: str) -> str:
    tag_text = "、".join((tags or [])[:5]) or "高精度 PBR"
    cat_cn = {
        "home": "家居", "collectibles": "艺术", "digital": "数码",
        "fresh": "生活", "toys": "玩趣", "apparel": "服饰",
    }.get(_pick_category(categories, tags), "家居")
    return (
        f"{raw_name} · {cat_cn}类 3D 商品。PBR 全材质渲染，"
        f"贴图表现：{tag_text}。"
        f"模型作者：{author or 'Poly Haven'}，CC0 许可，可自由商用展示。"
        "3D 旋转预览可确认每个角度细节，AR 模式一键投射到真实场景。"
    )


def _build_one(meta: dict[str, Any]) -> dict[str, Any]:
    slug = meta["slug"]
    name_en = meta.get("name") or slug
    gltf_name = meta.get("gltf_name") or f"{slug}_1k.gltf"
    tags = meta.get("tags") or []
    category = _pick_category(meta.get("categories") or [], tags)
    lo, hi = _PRICE_RANGE[category]
    price = _stable_int(slug, lo, hi)
    stock = _stable_int("stock_" + slug, 5, 220)

    author = (meta.get("authors") or ["Poly Haven"])[0]
    model_url = f"{config.STATIC_URL_PREFIX}/samples/{_ASSETS_SUBDIR}/{slug}/{gltf_name}"

    # thumbnail 走 _thumb.png
    thumb_abs = config.SAMPLES_DIR / _ASSETS_SUBDIR / slug / "_thumb.png"
    thumb_url: str | None = None
    thumb_local = False
    if thumb_abs.exists() and thumb_abs.stat().st_size > 0:
        thumb_url = f"{config.STATIC_URL_PREFIX}/samples/{_ASSETS_SUBDIR}/{slug}/_thumb.png"
        thumb_local = True

    return {
        "id": f"ph-{slug}",
        "name": _name_cn(name_en),
        "category": category,
        "price": float(price),
        "stock": int(stock),
        "description": _description_cn(name_en, meta.get("categories") or [], meta.get("tags") or [], author),
        "model_url": model_url,
        "thumbnail_url": thumb_url,
        "license": f"CC0 · {author}",
        "source": "polyhaven",
        "tags": (meta.get("tags") or [])[:6],
        "tryonable": False,
        "model_local": True,
        "thumbnail_local": thumb_local,
    }


def load_polyhaven_products() -> list[dict[str, Any]]:
    """读取 polyhaven_products.json 并构造商品列表。JSON 不存在时返回空列表。"""
    if not _JSON_PATH.exists():
        return []
    try:
        data = json.loads(_JSON_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    results: list[dict[str, Any]] = []
    for meta in data:
        if not meta.get("ok"):
            continue
        try:
            results.append(_build_one(meta))
        except Exception:
            continue
    return results
