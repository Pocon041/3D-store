"""资产优化管线：OBJ -> GLB 转换、GLB Draco 压缩、texture resize。

Blender / glTF Transform 都通过 subprocess 调用，且命令模板放到 config.py。
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

from .. import config
from ..utils.metrics import file_size_mb, compression_ratio
from ..utils.process_utils import command_exists, run_command


def convert_obj_to_glb(
    obj_path: Path,
    glb_path: Path,
    log_path: Optional[Path] = None,
) -> Path:
    """优先用 Blender CLI；不可用时回退到 trimesh。"""
    glb_path.parent.mkdir(parents=True, exist_ok=True)

    blender_script = config.PROJECT_ROOT / "scripts" / "convert_obj_to_glb.py"
    if command_exists("blender") and blender_script.exists():
        cmd = [
            "blender",
            "--background",
            "--python",
            str(blender_script),
            "--",
            "--input",
            str(obj_path),
            "--output",
            str(glb_path),
        ]
        run_command(cmd, log_path=log_path)
        if glb_path.exists():
            return glb_path

    # 回退：trimesh
    try:
        import trimesh  # type: ignore
        mesh = trimesh.load(obj_path, force="mesh")
        mesh.export(glb_path)
        return glb_path
    except Exception as e:
        raise RuntimeError(f"无法把 OBJ 转 GLB（Blender 不可用且 trimesh 失败）：{e}") from e


def compress_glb_with_draco(
    src_glb: Path,
    dst_glb: Path,
    log_path: Optional[Path] = None,
) -> Path:
    """用 glTF Transform CLI 做 Draco 压缩。"""
    dst_glb.parent.mkdir(parents=True, exist_ok=True)
    if not command_exists("gltf-transform"):
        # 不可用则直接复制一份，调用方自行决定是否报错
        shutil.copy2(src_glb, dst_glb)
        return dst_glb

    cmd = [
        "gltf-transform",
        "draco",
        str(src_glb),
        str(dst_glb),
        "--method",
        "edgebreaker",
    ]
    run_command(cmd, log_path=log_path)
    return dst_glb


def resize_textures(
    src_glb: Path,
    dst_glb: Path,
    width: int = 1024,
    height: int = 1024,
    log_path: Optional[Path] = None,
) -> Path:
    """用 glTF Transform 重置贴图尺寸。"""
    dst_glb.parent.mkdir(parents=True, exist_ok=True)
    if not command_exists("gltf-transform"):
        shutil.copy2(src_glb, dst_glb)
        return dst_glb
    cmd = [
        "gltf-transform",
        "resize",
        str(src_glb),
        str(dst_glb),
        "--width",
        str(width),
        "--height",
        str(height),
    ]
    run_command(cmd, log_path=log_path)
    return dst_glb


def optimize_pipeline(
    obj_path: Optional[Path],
    out_dir: Path,
    log_path: Optional[Path] = None,
) -> dict:
    """完整的优化管线：OBJ -> GLB -> Draco -> resize。

    返回各阶段产物路径与大小指标。
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    info: dict = {}
    if obj_path is None or not obj_path.exists():
        raise RuntimeError("OBJ 不存在，无法继续 GLB 转换")

    glb_path = out_dir / "model.glb"
    convert_obj_to_glb(obj_path, glb_path, log_path=log_path)
    info["glb"] = str(glb_path)
    info["glb_size_mb"] = file_size_mb(glb_path)

    draco_path = out_dir / "model.draco.glb"
    compress_glb_with_draco(glb_path, draco_path, log_path=log_path)
    info["draco"] = str(draco_path)
    info["draco_size_mb"] = file_size_mb(draco_path)

    optimized_path = out_dir / "model.optimized.glb"
    resize_textures(draco_path, optimized_path, log_path=log_path)
    info["optimized_glb"] = str(optimized_path)
    info["optimized_glb_size_mb"] = file_size_mb(optimized_path)

    info["compression_ratio"] = compression_ratio(info["glb_size_mb"], info["optimized_glb_size_mb"])
    return info
