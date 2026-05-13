"""Mock 管线：在没有 GPU / 没有装 Nerfstudio / 没有 CatVTON 的情况下也能跑通全链路。

设计原则：
1. 输出真实可加载的 3D 资产（GLB / PLY），让前端 model-viewer 能直接展示。
2. 不依赖 GPU；trimesh 是纯 Python 的。
3. 输出 metrics.json，让前端指标面板可以渲染。
"""
from __future__ import annotations

import json
import math
import shutil
import time
from pathlib import Path
from typing import Optional

from .. import config
from ..job_store import job_store
from ..utils.metrics import Timer, compression_ratio, dir_size_mb, file_size_mb


def _try_generate_cube_glb(target: Path) -> bool:
    """用 trimesh 程序化生成一个简单立方体 GLB。失败返回 False。

    不主动设置 visuals，让 trimesh 用默认 PBR 材质，避免不同 trimesh 版本
    对 ColorVisuals 转 GLB 行为不一致带来的问题。
    """
    try:
        import trimesh
    except Exception:
        return False
    try:
        mesh = trimesh.creation.box(extents=(1.0, 1.0, 1.0))
        target.parent.mkdir(parents=True, exist_ok=True)
        mesh.export(target)
        return target.exists() and target.stat().st_size > 0
    except Exception:
        return False


def _try_generate_sphere_ply(target: Path) -> bool:
    """生成一个简易球体 PLY，模拟 Gaussian Splat 点云占位。"""
    try:
        import numpy as np
        import trimesh
    except Exception:
        return False
    try:
        sphere = trimesh.creation.icosphere(subdivisions=3, radius=0.5)
        # 用法线方向生成颜色
        colors = ((sphere.vertex_normals * 0.5 + 0.5) * 255).astype("uint8")
        rgba = np.concatenate([colors, np.full((colors.shape[0], 1), 255, dtype="uint8")], axis=1)
        cloud = trimesh.points.PointCloud(sphere.vertices, colors=rgba)
        target.parent.mkdir(parents=True, exist_ok=True)
        cloud.export(target)
        return target.exists() and target.stat().st_size > 0
    except Exception:
        return False


def _try_generate_thumbnail(target: Path, label: str = "mock") -> bool:
    """生成一张 256x256 占位缩略图，让商城卡片有视觉反馈而不是首字。

    用 PIL 画一个等距投影的"立方体"+ 标签，足够区分 mock / 真实产物即可。
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        return False
    try:
        size = 256
        img = Image.new("RGB", (size, size), (240, 244, 250))
        draw = ImageDraw.Draw(img)

        # 渐变背景
        for y in range(size):
            t = y / size
            r = int(240 + (227 - 240) * t)
            g = int(244 + (232 - 244) * t)
            b = int(250 + (244 - 250) * t)
            draw.line([(0, y), (size, y)], fill=(r, g, b))

        # 等距立方体三面
        cx, cy = 128, 130
        s = 56
        top = [(cx, cy - s), (cx + s, cy - s // 2), (cx, cy), (cx - s, cy - s // 2)]
        left = [(cx - s, cy - s // 2), (cx, cy), (cx, cy + s), (cx - s, cy + s // 2)]
        right = [(cx + s, cy - s // 2), (cx, cy), (cx, cy + s), (cx + s, cy + s // 2)]
        draw.polygon(top, fill=(180, 196, 220), outline=(120, 130, 150))
        draw.polygon(left, fill=(130, 150, 180), outline=(120, 130, 150))
        draw.polygon(right, fill=(150, 170, 200), outline=(120, 130, 150))

        # 文字标签
        try:
            font_big = ImageFont.truetype("arial.ttf", 18)
            font_small = ImageFont.truetype("arial.ttf", 12)
        except Exception:
            font_big = ImageFont.load_default()
            font_small = font_big
        draw.text((12, 12), "3D Asset", fill=(40, 50, 70), font=font_big)
        draw.text((12, 232), label, fill=(90, 100, 130), font=font_small)

        target.parent.mkdir(parents=True, exist_ok=True)
        img.save(target, format="PNG")
        return True
    except Exception:
        return False


def _try_generate_cube_obj(target: Path) -> bool:
    """生成一个最小 OBJ。即使没有 trimesh 也可以手写。"""
    target.parent.mkdir(parents=True, exist_ok=True)
    obj_text = """# Mock cube
v -0.5 -0.5 -0.5
v  0.5 -0.5 -0.5
v  0.5  0.5 -0.5
v -0.5  0.5 -0.5
v -0.5 -0.5  0.5
v  0.5 -0.5  0.5
v  0.5  0.5  0.5
v -0.5  0.5  0.5
f 1 2 3 4
f 5 6 7 8
f 1 5 8 4
f 2 6 7 3
f 4 3 7 8
f 1 2 6 5
"""
    target.write_text(obj_text, encoding="utf-8")
    return True


def _ensure_sample_glb() -> Optional[Path]:
    """如果 data/samples/mock_model.glb 不存在，则自动生成一个。"""
    sample = config.SAMPLES_DIR / "mock_model.glb"
    if sample.exists() and sample.stat().st_size > 0:
        return sample
    if _try_generate_cube_glb(sample):
        return sample
    return None


def run_mock_reconstruct(job_id: str, num_input_files: int, raw_size_mb: float) -> dict:
    """Mock 重建：复制示例 GLB / 生成 PLY / OBJ 到输出目录。"""
    job_dir = config.OUTPUT_DIR / job_id
    exports_dir = job_dir / "exports"
    glb_dir = exports_dir / "glb"
    splat_dir = exports_dir / "splat"
    mesh_dir = exports_dir / "mesh"

    job_store.update_job(job_id, status="running", stage="prepare_images", progress=0.1)
    job_store.append_log(job_id, "[mock] start reconstruction")

    timings: dict[str, float] = {}

    with Timer() as t_glb:
        sample_glb = _ensure_sample_glb()
        if sample_glb is None:
            raise RuntimeError("无法生成 mock GLB（缺少 trimesh，且无内置示例）。请安装 trimesh。")
        glb_target = glb_dir / "model.glb"
        glb_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(sample_glb, glb_target)
    timings["convert_glb"] = t_glb.seconds
    job_store.update_job(job_id, stage="convert_glb", progress=0.5,
                         outputs={"glb": str(glb_target)})

    with Timer() as t_opt:
        # mock 下让 optimized.glb 直接复用同一份，便于前端展示
        optimized_glb = glb_dir / "model.optimized.glb"
        shutil.copy2(glb_target, optimized_glb)
    timings["optimize_glb"] = t_opt.seconds
    job_store.update_job(job_id, stage="optimize_glb", progress=0.7,
                         outputs={"optimized_glb": str(optimized_glb)})

    with Timer() as t_splat:
        ply_path = splat_dir / "splat.ply"
        if not _try_generate_sphere_ply(ply_path):
            ply_path = None  # type: ignore
    timings["export_splat"] = t_splat.seconds
    if ply_path is not None:
        job_store.update_job(job_id, outputs={"ply": str(ply_path), "splat": str(ply_path)})

    with Timer() as t_mesh:
        obj_path = mesh_dir / "mesh.obj"
        _try_generate_cube_obj(obj_path)
    timings["export_mesh"] = t_mesh.seconds
    job_store.update_job(job_id, outputs={"obj": str(obj_path)})

    # 缩略图（让商城卡片有视觉反馈）
    thumb_path = job_dir / "thumbnail.png"
    _try_generate_thumbnail(thumb_path, label=f"mock · {job_id[:8]}")

    glb_size = file_size_mb(glb_target)
    optimized_size = file_size_mb(optimized_glb)

    metrics = {
        "job_id": job_id,
        "input": {
            "mode": "mock",
            "num_images": num_input_files,
            "raw_size_mb": raw_size_mb,
        },
        "timing": {
            **{k: round(v, 3) for k, v in timings.items()},
            "total_sec": round(sum(timings.values()), 3),
        },
        "outputs": {
            "splat_size_mb": file_size_mb(ply_path) if ply_path else 0.0,
            "obj_size_mb": file_size_mb(obj_path),
            "glb_size_mb": glb_size,
            "optimized_glb_size_mb": optimized_size,
            "compression_ratio": compression_ratio(glb_size, optimized_size),
        },
    }
    metrics_path = job_dir / "metrics.json"
    metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    preview_url = f"{config.STATIC_URL_PREFIX}/jobs/{job_id}/exports/glb/model.optimized.glb"
    job_store.update_job(
        job_id,
        status="success",
        stage="finished",
        progress=1.0,
        outputs={"preview_url": preview_url},
        metrics={
            "glb_size_mb": metrics["outputs"]["glb_size_mb"],
            "optimized_glb_size_mb": metrics["outputs"]["optimized_glb_size_mb"],
            "compression_ratio": metrics["outputs"]["compression_ratio"],
            "splat_size_mb": metrics["outputs"]["splat_size_mb"],
            "obj_size_mb": metrics["outputs"]["obj_size_mb"],
        },
    )
    job_store.append_log(job_id, "[mock] reconstruction finished")
    return metrics


def run_mock_tryon(job_id: str, person_image_path: Path, garment_image_path: Path) -> dict:
    """Mock 试穿：把人像图复制成 result.png，并写水印文字。"""
    job_dir = config.OUTPUT_DIR / job_id
    out_dir = job_dir / "tryon"
    out_dir.mkdir(parents=True, exist_ok=True)

    job_store.update_job(job_id, status="running", stage="prepare_inputs", progress=0.2)
    job_store.append_log(job_id, "[mock] start try-on")

    person_target = out_dir / ("person" + person_image_path.suffix.lower())
    garment_target = out_dir / ("garment" + garment_image_path.suffix.lower())
    shutil.copy2(person_image_path, person_target)
    shutil.copy2(garment_image_path, garment_target)

    result_path = out_dir / "result.png"
    drew = False
    try:
        from PIL import Image, ImageDraw, ImageFont  # type: ignore

        person_img = Image.open(person_target).convert("RGB")
        garment_img = Image.open(garment_target).convert("RGB")

        # 拼接 person + garment + watermark，做一个简单的"假"试穿
        target_h = max(person_img.height, garment_img.height)
        person_resized = person_img.resize((int(person_img.width * target_h / person_img.height), target_h))
        garment_resized = garment_img.resize((int(garment_img.width * target_h / garment_img.height), target_h))

        canvas = Image.new("RGB",
                           (person_resized.width + garment_resized.width // 2, target_h),
                           (245, 245, 245))
        canvas.paste(person_resized, (0, 0))
        # 把服装图缩小后叠到人像中央位置
        overlay = garment_resized.resize(
            (garment_resized.width // 2, garment_resized.height // 2),
        )
        offset_x = max(0, person_resized.width // 2 - overlay.width // 2)
        offset_y = max(0, target_h // 3)
        canvas.paste(overlay, (offset_x, offset_y))

        draw = ImageDraw.Draw(canvas)
        text = "Mock Try-On Result"
        try:
            font = ImageFont.truetype("arial.ttf", size=max(20, target_h // 24))
        except Exception:
            font = ImageFont.load_default()
        draw.rectangle([(0, 0), (canvas.width, max(36, target_h // 16))], fill=(20, 20, 20))
        draw.text((10, 6), text, fill=(255, 255, 255), font=font)
        canvas.save(result_path)
        drew = True
    except Exception:
        # 退化方案：直接复制人像
        shutil.copy2(person_target, result_path)

    job_store.update_job(job_id, stage="run_catvton", progress=0.7)
    time.sleep(0.05)  # 让前端能看到状态变化

    preview_url = f"{config.STATIC_URL_PREFIX}/jobs/{job_id}/tryon/result.png"
    job_store.update_job(
        job_id,
        status="success",
        stage="finished",
        progress=1.0,
        outputs={
            "tryon_person": str(person_target),
            "tryon_garment": str(garment_target),
            "tryon_result": str(result_path),
            "preview_url": preview_url,
        },
    )
    job_store.append_log(job_id, f"[mock] try-on finished (drew={drew})")
    return {"result": str(result_path), "preview_url": preview_url}
