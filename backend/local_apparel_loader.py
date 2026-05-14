"""Load manually imported apparel GLB files as shop products.

The actual GLB files live under data/samples/glb/ and are intentionally
gitignored because they can be large. This loader only exposes entries whose
files exist locally.
"""
from __future__ import annotations

from typing import Any
from urllib.parse import quote

from . import config


def _tryon_category(slot: str) -> str:
    if slot == "full":
        return "dress"
    if slot == "lower":
        return "lower"
    return "upper"


_LOCAL_APPAREL: list[dict[str, Any]] = [
    {
        "id": "local-apparel-adidas-jacket",
        "filename": "7ad398dd7b67d87e550dee9339bee091.glb",
        "name": "adidas 夹克上装",
        "price": 699.0,
        "stock": 12,
        "tags": ["服装", "夹克", "上装", "adidas"],
        "garment_slot": "upper",
    },
    {
        "id": "local-apparel-polo-shirt",
        "filename": "3b4c212dfe1d505444538e8592346caa.glb",
        "name": "Polo 衫短袖上衣",
        "price": 299.0,
        "stock": 20,
        "tags": ["服装", "Polo", "短袖", "上装"],
        "garment_slot": "upper",
    },
    {
        "id": "local-apparel-jeans",
        "filename": "e94719d68e8e34583a4f5ca549e38820.glb",
        "name": "牛仔裤下装",
        "price": 399.0,
        "stock": 16,
        "tags": ["服装", "牛仔裤", "下装"],
        "garment_slot": "lower",
    },
    {
        "id": "local-apparel-1987-0353-01",
        "filename": "1987_0353_01-100k-2048_std_draco.glb",
        "name": "博物馆服装藏品 1987.0353.01",
        "price": 1280.0,
        "stock": 1,
        "tags": ["服装", "连衣裙", "3D扫描", "Draco"],
        "garment_slot": "full",
    },
    {
        "id": "local-apparel-1988-0260-07",
        "filename": "1988_0260_07-100k-2048_std_draco.glb",
        "name": "博物馆服装藏品 1988.0260.07",
        "price": 1180.0,
        "stock": 1,
        "tags": ["服装", "连衣裙", "3D扫描", "Draco"],
        "garment_slot": "full",
    },
    {
        "id": "local-apparel-2009-0120-001",
        "filename": "2009_0120_001-150k-4096_std.glb",
        "name": "高清服装扫描 2009.0120.001",
        "price": 2680.0,
        "stock": 1,
        "tags": ["服装", "上装", "高清纹理", "4K"],
        "garment_slot": "upper",
    },
    {
        "id": "local-apparel-2019-0202-01",
        "filename": "2019_0202_01-100k-2048_std_draco.glb",
        "name": "博物馆服装藏品 2019.0202.01",
        "price": 1580.0,
        "stock": 1,
        "tags": ["服装", "上装", "3D扫描", "Draco"],
        "garment_slot": "upper",
    },
    {
        "id": "local-apparel-nmah-cs-309679",
        "filename": "NMAH-cs_309679_001-100k-4096_std.glb",
        "name": "NMAH 服装藏品 CS.309679",
        "price": 2980.0,
        "stock": 1,
        "tags": ["服装", "连衣裙", "博物馆藏品", "4K"],
        "garment_slot": "full",
    },
    {
        "id": "local-apparel-down-jacket-aa843c96",
        "filename": "aa843c9607b2e58e67ce39f5f7788c88.glb",
        "name": "羽绒服上装",
        "price": 899.0,
        "stock": 12,
        "tags": ["服装", "羽绒服", "外套", "上装", "down jacket"],
        "garment_slot": "upper",
    },
]


def _description(name: str, filename: str) -> str:
    return (
        f"{name}，由本地导入的高精度 GLB 服装模型生成商品条目。"
        "支持 360 度旋转检视，可观察布料轮廓、褶皱、纹理与结构细节，"
        f"原始文件：{filename}。"
    )


def _thumbnail_url(product_id: str) -> tuple[str | None, bool]:
    """Return an optional thumbnail URL if a same-id image exists."""
    thumb_dir = config.SAMPLES_DIR / "thumb"
    for ext in (".jpg", ".png", ".webp", ".jpeg"):
        thumb = thumb_dir / f"{product_id}{ext}"
        if thumb.exists() and thumb.stat().st_size > 0:
            return f"{config.STATIC_URL_PREFIX}/samples/thumb/{quote(thumb.name)}", True
    return None, False


def load_local_apparel_products() -> list[dict[str, Any]]:
    """Build product records for local apparel GLBs that are present."""
    products: list[dict[str, Any]] = []
    for item in _LOCAL_APPAREL:
        filename = item["filename"]
        model_path = config.SAMPLES_DIR / "glb" / filename
        if not model_path.exists() or model_path.stat().st_size <= 0:
            continue

        thumbnail_url, thumbnail_local = _thumbnail_url(item["id"])
        products.append({
            "id": item["id"],
            "name": item["name"],
            "category": "apparel",
            "price": item["price"],
            "stock": item["stock"],
            "description": _description(item["name"], filename),
            "model_url": f"{config.STATIC_URL_PREFIX}/samples/glb/{quote(filename)}",
            "thumbnail_url": thumbnail_url,
            "license": "Local import",
            "source": "local-apparel",
            "tags": item["tags"],
            "tryonable": True,
            "tryon_category": _tryon_category(item["garment_slot"]),
            "avatar_dressable": True,
            "garment_slot": item["garment_slot"],
            "model_local": True,
            "thumbnail_local": thumbnail_local,
            "filename": filename,
        })
    return products
