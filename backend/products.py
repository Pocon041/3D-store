"""商城商品来源。

包含两类商品：

1. 种子商品（SEED_PRODUCTS）：写死在代码里，模型文件来自 KhronosGroup
   glTF-Sample-Models（CC-BY 4.0 / CC0），通过 jsdelivr CDN 直接引用。
   优点：不占本地存储；缺点：首次加载需要外网。
2. 用户资产：扫描 outputs/jobs/ 下所有 status=success 的 reconstruct
   任务，把它们也作为商品上架。这样平台跑出的真实重建结果可直接展示。

如果用户跑了 scripts/fetch_demo_models.py 把 GLB 下载到本地
data/samples/glb/<id>.glb，模块会优先返回本地路径（/static/samples/glb/...）。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from . import config
from .job_store import job_store
from .polyhaven_loader import load_polyhaven_products


# 模型 CDN：用 jsdelivr 镜像 GitHub raw，国内访问比 raw.githubusercontent.com 稳
_CDN = "https://cdn.jsdelivr.net/gh/KhronosGroup/glTF-Sample-Models@master/2.0"
_MV = "https://modelviewer.dev/shared-assets/models"


SEED_PRODUCTS: list[dict[str, Any]] = [
    {
        "id": "damaged-helmet",
        "name": "战损头盔（典藏 PBR）",
        "category": "collectibles",
        "price": 1280.0,
        "stock": 17,
        "description": (
            "全 PBR 渲染示例。金属拉丝、漆面磨损、法线贴图细节一览无遗。"
            "适合作为虚拟陈列收藏。3D 旋转、AR 真实摆放体验，告别『图片像但实物不像』。"
        ),
        "model_url": f"{_CDN}/DamagedHelmet/glTF-Binary/DamagedHelmet.glb",
        "thumbnail_url": f"{_CDN}/DamagedHelmet/screenshot/screenshot.png",
        "license": "CC-BY 4.0 (Khronos)",
        "source": "khronos",
        "tags": ["头盔", "PBR", "复古"],
        "tryonable": False,
    },
    {
        "id": "boom-box",
        "name": "经典蓝调录音机",
        "category": "digital",
        "price": 599.0,
        "stock": 32,
        "description": (
            "复古卡带音响，木纹喇叭与金属拉手细节俱全。"
            "在 3D 视角下可清晰检视旋钮材质与拉丝表面，避免拍照角度造成的色差错觉。"
        ),
        "model_url": f"{_CDN}/BoomBox/glTF-Binary/BoomBox.glb",
        "thumbnail_url": f"{_CDN}/BoomBox/screenshot/screenshot.jpg",
        "license": "CC-BY 4.0 (Khronos)",
        "source": "khronos",
        "tags": ["音响", "复古", "数码"],
        "tryonable": False,
    },
    {
        "id": "water-bottle",
        "name": "户外保温水壶 750ml",
        "category": "home",
        "price": 89.0,
        "stock": 120,
        "description": (
            "户外露营常备。LOGO 与瓶身曲面细节通过 PBR 完整呈现，"
            "在不同光照下质感真实，购前看清比图片更可靠。"
        ),
        "model_url": f"{_CDN}/WaterBottle/glTF-Binary/WaterBottle.glb",
        "thumbnail_url": f"{_CDN}/WaterBottle/screenshot/screenshot.jpg",
        "license": "CC-BY 4.0 (Khronos)",
        "source": "khronos",
        "tags": ["水壶", "户外", "家居"],
        "tryonable": False,
    },
    {
        "id": "avocado",
        "name": "进口牛油果（单只）",
        "category": "fresh",
        "price": 9.9,
        "stock": 999,
        "description": (
            "墨西哥 Hass 品种。3D 视角让消费者预先观察果型与表皮，"
            "降低生鲜电商常见的『图片好看实物不行』退货纠纷。"
        ),
        "model_url": f"{_CDN}/Avocado/glTF-Binary/Avocado.glb",
        "thumbnail_url": f"{_CDN}/Avocado/screenshot/screenshot.jpg",
        "license": "CC-BY 4.0 (Khronos)",
        "source": "khronos",
        "tags": ["生鲜", "进口", "水果"],
        "tryonable": False,
    },
    {
        "id": "duck",
        "name": "经典橡皮鸭浴室伴侣",
        "category": "toys",
        "price": 29.9,
        "stock": 540,
        "description": (
            "一代名物，复古 PVC 工艺。3D 旋转预览每个角度都能看到经典圆润造型。"
        ),
        "model_url": f"{_CDN}/Duck/glTF-Binary/Duck.glb",
        "thumbnail_url": f"{_CDN}/Duck/screenshot/screenshot.png",
        "license": "Public Domain (Khronos sample)",
        "source": "khronos",
        "tags": ["玩具", "经典"],
        "tryonable": False,
    },
    {
        "id": "lantern",
        "name": "古风庭院灯笼",
        "category": "home",
        "price": 459.0,
        "stock": 24,
        "description": (
            "黄铜骨架配磨砂玻璃。3D 模型展示了铆钉、铰链等手工工艺细节，"
            "辅助高客单家居购买决策。"
        ),
        "model_url": f"{_CDN}/Lantern/glTF-Binary/Lantern.glb",
        "thumbnail_url": f"{_CDN}/Lantern/screenshot/screenshot.jpg",
        "license": "CC-BY 4.0 (Khronos)",
        "source": "khronos",
        "tags": ["灯具", "家居", "复古"],
        "tryonable": False,
    },
    {
        "id": "toy-car",
        "name": "复古铁皮玩具车",
        "category": "toys",
        "price": 199.0,
        "stock": 36,
        "description": (
            "经典铁皮喷漆工艺，车身曲面与镀铬细节在 3D 视角下纤毫毕现。"
            "适合作为儿童玩具或办公桌摆件。"
        ),
        "model_url": f"{_CDN}/ToyCar/glTF-Binary/ToyCar.glb",
        "thumbnail_url": f"{_CDN}/ToyCar/screenshot/screenshot.jpg",
        "license": "CC-BY 4.0 (Khronos)",
        "source": "khronos",
        "tags": ["玩具", "复古", "铁皮"],
        "tryonable": False,
    },
    {
        "id": "antique-camera",
        "name": "古董八音盒相机",
        "category": "collectibles",
        "price": 3580.0,
        "stock": 5,
        "description": (
            "黄铜机身配皮质蒙皮，全 PBR 材质忠实还原老物件包浆。"
            "AR 摆放后可对比家中相同年代的收藏品体量。"
        ),
        "model_url": f"{_CDN}/AntiqueCamera/glTF-Binary/AntiqueCamera.glb",
        "thumbnail_url": f"{_CDN}/AntiqueCamera/screenshot/screenshot.png",
        "license": "CC-BY 4.0 (Khronos)",
        "source": "khronos",
        "tags": ["收藏", "古董", "相机"],
        "tryonable": False,
    },
    {
        "id": "fox",
        "name": "可动小狐狸玩偶",
        "category": "toys",
        "price": 459.0,
        "stock": 12,
        "description": (
            "内置三段动画的小狐狸，可呈现奔跑姿态。3D 预览先看模型再下单，"
            "避免拍照角度造成的造型误差。"
        ),
        "model_url": f"{_CDN}/Fox/glTF-Binary/Fox.glb",
        "thumbnail_url": f"{_CDN}/Fox/screenshot/screenshot.jpg",
        "license": "CC0 (Khronos)",
        "source": "khronos",
        "tags": ["动物", "玩偶", "动画"],
        "tryonable": False,
    },
    # ---------- 服装类（试穿入口） ----------
    {
        "id": "varia-shoe",
        "name": "炫彩跑鞋（多配色）",
        "category": "apparel",
        "price": 899.0,
        "stock": 40,
        "description": (
            "支持多种材质变体的运动跑鞋，3D 视角下可清晰看到鞋面网布、"
            "鞋底纹理与缝线工艺。配合虚拟试穿可直接预览上脚效果。"
        ),
        "model_url": f"{_CDN}/MaterialsVariantsShoe/glTF-Binary/MaterialsVariantsShoe.glb",
        "thumbnail_url": f"{_CDN}/MaterialsVariantsShoe/screenshot/screenshot.jpg",
        "license": "CC-BY 4.0 (Khronos)",
        "source": "khronos",
        "tags": ["鞋", "运动", "可换色"],
        "tryonable": True,
    },
    {
        "id": "corset",
        "name": "复古束腰马甲",
        "category": "apparel",
        "price": 458.0,
        "stock": 18,
        "description": (
            "维多利亚风束腰马甲，3D 模型展示蕾丝纹理与系带细节。"
            "进入虚拟试穿，上传人像即可预览搭配效果。"
        ),
        "model_url": f"{_CDN}/Corset/glTF-Binary/Corset.glb",
        "thumbnail_url": f"{_CDN}/Corset/screenshot/screenshot.jpg",
        "license": "CC-BY 4.0 (Khronos)",
        "source": "khronos",
        "tags": ["服饰", "复古", "蕾丝"],
        "tryonable": True,
    },
    # ---------- 数码/玩具补充 ----------
    {
        "id": "buggy",
        "name": "沙漠越野赛车（遥控）",
        "category": "digital",
        "price": 2680.0,
        "stock": 7,
        "description": (
            "高细节越野赛车模型，悬挂、轮胎花纹完整。3D 视角下可确认每个"
            "零件位置，方便高客单玩家购前确认。"
        ),
        "model_url": f"{_CDN}/Buggy/glTF-Binary/Buggy.glb",
        "thumbnail_url": f"{_CDN}/Buggy/screenshot/screenshot.jpg",
        "license": "CC-BY 4.0 (Khronos)",
        "source": "khronos",
        "tags": ["赛车", "遥控", "高级"],
        "tryonable": False,
    },
    # ---------- 生鲜补充 ----------
    {
        "id": "barramundi",
        "name": "冰鲜金目鲈（整条）",
        "category": "fresh",
        "price": 69.0,
        "stock": 50,
        "description": (
            "深海捕捞，3D 预览鱼鳞、眼神饱满度，购前判断新鲜度，"
            "降低生鲜电商常见 SKU 实物落差。"
        ),
        "model_url": f"{_CDN}/BarramundiFish/glTF-Binary/BarramundiFish.glb",
        "thumbnail_url": f"{_CDN}/BarramundiFish/screenshot/screenshot.jpg",
        "license": "CC-BY 4.0 (Khronos)",
        "source": "khronos",
        "tags": ["生鲜", "深海", "整条"],
        "tryonable": False,
    },
    # ---------- 家居/艺术 ----------
    {
        "id": "sheen-chair",
        "name": "丝绒光泽单人椅",
        "category": "home",
        "price": 2998.0,
        "stock": 11,
        "description": (
            "丝绒面料的微光泽在 3D 视角下随角度变化，PBR 模型完整还原织物质感。"
            "AR 摆放到实际空间，验证尺寸与客厅风格是否匹配。"
        ),
        "model_url": f"{_CDN}/SheenChair/glTF-Binary/SheenChair.glb",
        "thumbnail_url": f"{_CDN}/SheenChair/screenshot/screenshot.jpg",
        "license": "CC-BY 4.0 (Khronos)",
        "source": "khronos",
        "tags": ["椅子", "丝绒", "家居"],
        "tryonable": False,
    },
    # ---------- 收藏补充 ----------
    {
        "id": "dragon-attenuation",
        "name": "琉璃神龙摆件（手工吹制）",
        "category": "collectibles",
        "price": 8888.0,
        "stock": 4,
        "description": (
            "玻璃材质龙形摆件，体内含微气泡。3D 视图配合 transmission "
            "PBR 折射，光线穿过龙身呈现宝石级散射效果，远超图片表达力。"
        ),
        "model_url": f"{_CDN}/DragonAttenuation/glTF-Binary/DragonAttenuation.glb",
        "thumbnail_url": f"{_CDN}/DragonAttenuation/screenshot/screenshot.jpg",
        "license": "CC-BY 4.0 (Khronos)",
        "source": "khronos",
        "tags": ["琉璃", "稀有", "折射"],
        "tryonable": False,
    },
    {
        "id": "iridescence-lamp",
        "name": "虹彩极光灯（设计师款）",
        "category": "home",
        "price": 1599.0,
        "stock": 18,
        "description": (
            "灯罩表面镀膜在不同视角呈现彩虹色阶。3D 旋转就能直观看到"
            "色彩变化区间，购前避免『现场和图片色差大』。"
        ),
        "model_url": f"{_CDN}/IridescenceLamp/glTF-Binary/IridescenceLamp.glb",
        "thumbnail_url": f"{_CDN}/IridescenceLamp/screenshot/screenshot.jpg",
        "license": "CC-BY 4.0 (Khronos)",
        "source": "khronos",
        "tags": ["灯具", "设计师", "虹彩"],
        "tryonable": False,
    },
]


def _resolve_local_paths(product: dict[str, Any]) -> dict[str, Any]:
    """把 GLB / thumbnail 优先指向 data/samples/ 下的本地文件。

    变体（variant）商品用 base_id 共享同一份 GLB/缩略图，不用每个 SKU 都下一份。
    """
    product = dict(product)
    # 变体优先用 base_id 去找文件；无 base_id 就用自己的 id
    lookup_id = product.get("base_id") or product["id"]

    glb_local = config.SAMPLES_DIR / "glb" / f"{lookup_id}.glb"
    if glb_local.exists() and glb_local.stat().st_size > 0:
        product["model_url"] = f"{config.STATIC_URL_PREFIX}/samples/glb/{lookup_id}.glb"
        product["model_local"] = True
    else:
        product["model_local"] = False

    thumb_dir = config.SAMPLES_DIR / "thumb"
    for ext in (".jpg", ".png", ".webp", ".jpeg"):
        thumb_local = thumb_dir / f"{lookup_id}{ext}"
        if thumb_local.exists() and thumb_local.stat().st_size > 0:
            product["thumbnail_url"] = f"{config.STATIC_URL_PREFIX}/samples/thumb/{lookup_id}{ext}"
            product["thumbnail_local"] = True
            break
    else:
        product["thumbnail_local"] = False
    return product


def _user_assets_as_products() -> list[dict[str, Any]]:
    """把 outputs/jobs 下成功的 reconstruct / image_to_3d 任务暴露成商品。

    商品的 name / price / category 优先读取 job.params 里的覆盖值（由
    publish_job_as_product 写入），没有则用合理默认。
    """
    items: list[dict[str, Any]] = []
    for record in job_store.list_jobs():
        if record.task_type not in {"reconstruct", "image_to_3d"}:
            continue
        if record.status != "success":
            continue
        glb_abs = (
            record.outputs.optimized_glb
            or record.outputs.glb
        )
        if not glb_abs:
            continue
        try:
            rel = Path(glb_abs).resolve().relative_to(config.OUTPUT_DIR.resolve())
        except ValueError:
            continue
        url = f"{config.STATIC_URL_PREFIX}/jobs/{rel.as_posix()}"
        is_mock = bool(record.params.get("mock") or (record.outputs.provider == "mock"))

        # thumbnail：优先 job.outputs.thumbnail，其次任务目录下的 thumbnail.png
        thumb_url = None
        thumb_abs = None
        if record.outputs.thumbnail:
            thumb_abs = Path(record.outputs.thumbnail)
        if thumb_abs is None or not thumb_abs.exists():
            thumb_abs = config.OUTPUT_DIR / record.job_id / "thumbnail.png"
        if thumb_abs.exists():
            try:
                rel_t = thumb_abs.resolve().relative_to(config.OUTPUT_DIR.resolve())
                thumb_url = f"{config.STATIC_URL_PREFIX}/jobs/{rel_t.as_posix()}"
            except ValueError:
                thumb_url = None

        # 默认描述按任务类型生成
        if record.task_type == "image_to_3d":
            provider = record.outputs.provider or "mock"
            default_desc = (
                f"由用户在工作台用图片生成的 3D 模型，provider={provider}。"
                f"GLB 大小 {record.metrics.glb_size_mb or '?'} MB。"
            )
            default_name = f"AIGC 单图 3D · {record.job_id[:8]}"
            default_tags = ["AIGC", "图生3D", provider]
        else:
            default_desc = (
                f"由用户在工作台上传 {record.metrics.num_input_files or '?'} 张图片重建生成。"
                f"GLB 大小 {record.metrics.optimized_glb_size_mb or record.metrics.glb_size_mb or '?'} MB。"
            )
            default_name = f"自定义 3D 资产 {record.job_id[:8]}"
            default_tags = ["自定义", "重建"]

        # 允许 publish 时覆盖
        p = record.params or {}
        name = p.get("product_name") or default_name
        price = float(p.get("product_price") or 0.0)
        category = p.get("product_category") or "user-uploads"
        description = p.get("product_description") or default_desc
        tags = p.get("product_tags") or default_tags
        if is_mock and "mock" not in name.lower():
            name = f"[mock] {name}"

        items.append({
            "id": f"job-{record.job_id}",
            "name": name,
            "category": category,
            "price": price,
            "stock": int(p.get("product_stock") or 1),
            "description": description,
            "model_url": url,
            "thumbnail_url": thumb_url,
            "license": p.get("product_license") or "User Generated",
            "source": "user",
            "tags": tags,
            "tryonable": False,
            "job_id": record.job_id,
            "task_type": record.task_type,
            "model_local": True,
            "published": bool(p.get("published", False)),
        })
    return items


def publish_job_as_product(
    job_id: str,
    *,
    name: Optional[str] = None,
    price: Optional[float] = None,
    category: Optional[str] = None,
    description: Optional[str] = None,
    tags: Optional[list[str]] = None,
    stock: Optional[int] = None,
) -> Optional[dict[str, Any]]:
    """把已完成的 job 标记为"上架"并写入自定义商品字段。

    通过更新 job.params 里的 product_* 字段实现，避免引入新的数据存储。
    返回更新后的商品对象（dict）；找不到 job / 任务未成功时返回 None。
    """
    record = job_store.get_job(job_id)
    if record is None or record.status != "success":
        return None

    patch: dict[str, Any] = {"published": True}
    if name is not None:
        patch["product_name"] = name.strip()
    if price is not None:
        patch["product_price"] = float(price)
    if category is not None:
        patch["product_category"] = category.strip()
    if description is not None:
        patch["product_description"] = description.strip()
    if tags is not None:
        patch["product_tags"] = [t.strip() for t in tags if t and t.strip()]
    if stock is not None:
        patch["product_stock"] = int(stock)

    new_params = dict(record.params or {})
    new_params.update(patch)
    job_store.update_job(job_id, params=new_params)

    return get_product(f"job-{job_id}")


def list_products() -> list[dict[str, Any]]:
    # 1) Khronos 16 个精选（不再展开 SKU 变体，每件都是独立模型）
    khronos = [_resolve_local_paths(p) for p in SEED_PRODUCTS]
    # 2) Poly Haven 批量下载的独立模型（由 polyhaven_loader 构造好，已是本地化路径）
    poly = load_polyhaven_products()
    # 3) 用户作品
    users = _user_assets_as_products()
    return khronos + poly + users


def get_product(product_id: str) -> Optional[dict[str, Any]]:
    for p in list_products():
        if p["id"] == product_id:
            return p
    return None


CATEGORIES = [
    {"key": "all", "label": "全部"},
    {"key": "apparel", "label": "服装"},
    {"key": "collectibles", "label": "收藏"},
    {"key": "digital", "label": "数码"},
    {"key": "home", "label": "家居"},
    {"key": "toys", "label": "玩具"},
    {"key": "fresh", "label": "生鲜"},
    {"key": "user-uploads", "label": "用户作品"},
]


def search_products(items: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    """按 id / name / description / tags / category 做不区分大小写的模糊搜索。

    把 id 也纳入是为了支持英文搜索：商品 name 通常是中文，但 id（如
    `damaged-helmet`、`ph-marble_bust_01`）保留英文 slug，用户可以用英文
    关键词找到中文商品。
    """
    q = (query or "").strip().lower()
    if not q:
        return items
    results: list[dict[str, Any]] = []
    for p in items:
        hay = " ".join([
            str(p.get("id", "")),
            str(p.get("name", "")),
            str(p.get("description", "")),
            " ".join(p.get("tags", []) or []),
            str(p.get("category", "")),
        ]).lower()
        if q in hay:
            results.append(p)
    return results
