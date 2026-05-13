"""3D 重建主管线：包装 Nerfstudio + COLMAP + FFmpeg。

执行步骤：
1. 保存原始输入到 data/raw/jobs/{job_id}/
2. 视频抽帧 (ffmpeg)
3. 图片简单筛选 (validators)
4. ns-process-data images
5. ns-train splatfacto
6. 找最新 config.yml
7. ns-export gaussian-splat
8. ns-export poisson / marching-cubes
9. OBJ -> GLB 转换
10. glTF Transform Draco 压缩

通过 mock=True 跳过所有外部命令，复制示例资产。
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Optional

from .. import config
from ..job_store import job_store
from ..utils.file_utils import generate_job_id, list_files
from ..utils.metrics import Timer, dir_size_mb, file_size_mb, compression_ratio
from ..utils.process_utils import CommandError, command_exists, run_command
from ..utils.validators import filter_image_files, filter_blurry_images
from . import mock_pipeline, optimize_asset


def _job_log_path(job_id: str) -> Path:
    return config.OUTPUT_DIR / job_id / "job.log"


def _extract_frames(video_path: Path, out_dir: Path, log_path: Path) -> int:
    """用 FFmpeg 抽帧，返回最终图片数。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    pattern = str(out_dir / "frame_%05d.jpg")
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vf",
        config.FFMPEG_EXTRACT_VF,
        pattern,
    ]
    run_command(cmd, log_path=log_path)
    return len(list(out_dir.glob("frame_*.jpg")))


def _ns_process_data(images_dir: Path, processed_dir: Path, log_path: Path) -> Path:
    """调用 ns-process-data images，返回处理后的目录。"""
    processed_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        *config.nerfstudio_cmd_prefix(),
        "ns-process-data",
        "images",
        "--data",
        str(images_dir),
        "--output-dir",
        str(processed_dir),
    ]
    run_command(cmd, log_path=log_path)
    transforms = processed_dir / "transforms.json"
    if not transforms.exists():
        raise RuntimeError(
            "COLMAP failed. Please provide more overlapping, non-blurry images."
        )
    return processed_dir


def _ns_train_splatfacto(
    processed_dir: Path,
    output_dir: Path,
    quality: str,
    log_path: Path,
) -> None:
    """调用 ns-train splatfacto。质量档位映射在 config 里。"""
    cfg = config.QUALITY_CONFIG.get(quality, config.QUALITY_CONFIG["balanced"])
    method = cfg["method"]
    max_iters = int(cfg["max_iterations"])

    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        *config.nerfstudio_cmd_prefix(),
        "ns-train",
        method,
        "--data",
        str(processed_dir),
        "--output-dir",
        str(output_dir),
        "--max-num-iterations",
        str(max_iters),
        "--viewer.quit-on-train-completion",
        "True",
    ]
    run_command(cmd, log_path=log_path)


def find_latest_nerfstudio_config(job_output_dir: Path) -> Optional[Path]:
    """在 Nerfstudio 输出目录中递归找最新的 config.yml。"""
    if not job_output_dir.exists():
        return None
    candidates = list(job_output_dir.rglob("config.yml"))
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def _ns_export_gaussian_splat(config_yml: Path, out_dir: Path, log_path: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        *config.nerfstudio_cmd_prefix(),
        "ns-export",
        "gaussian-splat",
        "--load-config",
        str(config_yml),
        "--output-dir",
        str(out_dir),
    ]
    run_command(cmd, log_path=log_path)


def _ns_export_mesh(config_yml: Path, out_dir: Path, log_path: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    poisson_cmd = [
        *config.nerfstudio_cmd_prefix(),
        "ns-export",
        "poisson",
        "--load-config",
        str(config_yml),
        "--output-dir",
        str(out_dir),
    ]
    try:
        run_command(poisson_cmd, log_path=log_path)
        return
    except CommandError:
        pass
    marching_cmd = [
        *config.nerfstudio_cmd_prefix(),
        "ns-export",
        "marching-cubes",
        "--load-config",
        str(config_yml),
        "--output-dir",
        str(out_dir),
    ]
    run_command(marching_cmd, log_path=log_path)


def run_reconstruction_job(
    job_id: str,
    input_paths: list[str],
    input_mode: str = "images",
    quality: str = "balanced",
    export_glb: bool = True,
    mock: bool = False,
) -> dict:
    """3D 重建主入口。被 FastAPI 后台任务调用，也可以命令行直接调用。"""

    job_dir = config.OUTPUT_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = config.RAW_DIR / job_id
    images_dir = raw_dir / "images"
    video_dir = raw_dir / "video"
    log_path = _job_log_path(job_id)

    job_store.update_job(
        job_id,
        status="running",
        stage="received",
        progress=0.05,
        params={"mode": input_mode, "quality": quality, "export_glb": export_glb, "mock": mock},
    )

    timings: dict[str, float] = {}

    # ---------- Step 1: 准备图片 ----------
    if input_mode == "video":
        # input_paths 应当只有一个视频
        if not input_paths:
            raise RuntimeError("video 模式下未收到任何文件")
        video_path = Path(input_paths[0])
        with Timer() as t_extract:
            num_frames = _extract_frames(video_path, images_dir, log_path)
        timings["frame_extract"] = t_extract.seconds
        job_store.update_job(job_id, stage="extract_frames", progress=0.15)
        job_store.append_log(job_id, f"[ffmpeg] extracted {num_frames} frames")
    else:
        images_dir.mkdir(parents=True, exist_ok=True)
        # input_paths 已经在 main.py 里被保存到 raw_dir/images
        # 这里只确认目录存在
        pass

    # ---------- Step 2: 图片筛选 ----------
    raw_images = list_files(images_dir, extensions=config.IMAGE_EXTENSIONS)
    images = filter_image_files(raw_images)
    images, blurry = filter_blurry_images(images)
    raw_size_mb = round(sum(file_size_mb(p) for p in images), 3)
    job_store.update_job(
        job_id,
        stage="prepare_images",
        progress=0.2,
        metrics={"num_input_files": len(images), "raw_size_mb": raw_size_mb},
    )
    job_store.append_log(job_id,
                         f"[validate] kept {len(images)}, blurry {len(blurry)}, raw_size_mb {raw_size_mb}")

    # ---------- Mock 分支 ----------
    if mock:
        job_store.append_log(job_id, "[mock] mock=True，跳过 Nerfstudio")
        return mock_pipeline.run_mock_reconstruct(job_id, len(images), raw_size_mb)

    if not images:
        raise RuntimeError("没有可用的输入图片")

    if not command_exists("ns-process-data") or not command_exists("ns-train"):
        if config.ALLOW_MISSING_TOOLS_FALLBACK_TO_MOCK:
            job_store.append_log(job_id, "[fallback] Nerfstudio 不可用，回退 mock")
            return mock_pipeline.run_mock_reconstruct(job_id, len(images), raw_size_mb)
        raise RuntimeError(
            "Nerfstudio 命令未在 PATH 中检测到。请先安装 nerfstudio，或设置 ALLOW_MISSING_TOOLS_FALLBACK_TO_MOCK=true。"
        )

    # ---------- Step 3: ns-process-data ----------
    processed_dir = config.PROCESSED_DIR / job_id
    job_store.update_job(job_id, stage="ns_process_data", progress=0.3)
    with Timer() as t_proc:
        _ns_process_data(images_dir, processed_dir, log_path)
    timings["ns_process_data"] = t_proc.seconds
    job_store.update_job(job_id, outputs={"processed_data_dir": str(processed_dir)},
                         metrics={"process_time_sec": t_proc.seconds})

    # ---------- Step 4: ns-train ----------
    nerfstudio_outputs = job_dir / "nerfstudio"
    job_store.update_job(job_id, stage="train_splatfacto", progress=0.5)
    with Timer() as t_train:
        _ns_train_splatfacto(processed_dir, nerfstudio_outputs, quality, log_path)
    timings["training"] = t_train.seconds
    job_store.update_job(job_id, metrics={"train_time_sec": t_train.seconds})

    # ---------- Step 5: 找 config.yml ----------
    config_yml = find_latest_nerfstudio_config(nerfstudio_outputs)
    if config_yml is None:
        raise RuntimeError("未找到 Nerfstudio 训练产物 config.yml")
    job_store.update_job(job_id, outputs={"config_yml": str(config_yml)})

    # ---------- Step 6: 导出 splat ----------
    splat_dir = job_dir / "exports" / "splat"
    job_store.update_job(job_id, stage="export_gaussian_splat", progress=0.7)
    with Timer() as t_splat:
        _ns_export_gaussian_splat(config_yml, splat_dir, log_path)
    timings["export_splat"] = t_splat.seconds
    splats = list_files(splat_dir, extensions={".ply", ".splat"})
    splat_path = splats[0] if splats else None
    if splat_path is not None:
        job_store.update_job(job_id, outputs={"splat": str(splat_path), "ply": str(splat_path)},
                             metrics={"splat_size_mb": file_size_mb(splat_path)})

    # ---------- Step 7: 导出 mesh ----------
    mesh_dir = job_dir / "exports" / "mesh"
    job_store.update_job(job_id, stage="export_mesh", progress=0.8)
    with Timer() as t_mesh:
        try:
            _ns_export_mesh(config_yml, mesh_dir, log_path)
        except CommandError as e:
            job_store.append_log(job_id, f"[mesh] export failed: {e.returncode}")
    timings["export_mesh"] = t_mesh.seconds
    objs = list_files(mesh_dir, extensions={".obj"})
    obj_path = objs[0] if objs else None
    if obj_path is not None:
        job_store.update_job(job_id, outputs={"obj": str(obj_path)},
                             metrics={"obj_size_mb": file_size_mb(obj_path)})

    # ---------- Step 8: GLB ----------
    glb_dir = job_dir / "exports" / "glb"
    glb_metrics: dict = {}
    if export_glb and obj_path is not None:
        try:
            job_store.update_job(job_id, stage="convert_glb", progress=0.9)
            with Timer() as t_glb:
                glb_metrics = optimize_asset.optimize_pipeline(obj_path, glb_dir, log_path=log_path)
            timings["convert_glb"] = t_glb.seconds
            job_store.update_job(
                job_id,
                outputs={
                    "glb": glb_metrics.get("glb"),
                    "optimized_glb": glb_metrics.get("optimized_glb"),
                },
                metrics={
                    "glb_size_mb": glb_metrics.get("glb_size_mb"),
                    "optimized_glb_size_mb": glb_metrics.get("optimized_glb_size_mb"),
                    "compression_ratio": glb_metrics.get("compression_ratio"),
                    "convert_time_sec": t_glb.seconds,
                },
            )
        except Exception as e:
            job_store.append_log(job_id, f"[glb] optimize failed: {e}")

    # ---------- Step 9: 写 metrics.json ----------
    metrics = {
        "job_id": job_id,
        "input": {
            "mode": input_mode,
            "num_images": len(images),
            "raw_size_mb": raw_size_mb,
        },
        "timing": {
            **{k: round(v, 3) for k, v in timings.items()},
            "total_sec": round(sum(timings.values()), 3),
        },
        "outputs": {
            "splat_size_mb": file_size_mb(splat_path) if splat_path else 0.0,
            "obj_size_mb": file_size_mb(obj_path) if obj_path else 0.0,
            "glb_size_mb": glb_metrics.get("glb_size_mb", 0.0),
            "optimized_glb_size_mb": glb_metrics.get("optimized_glb_size_mb", 0.0),
            "compression_ratio": glb_metrics.get("compression_ratio", 0.0),
        },
    }
    (job_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    preview_target = glb_metrics.get("optimized_glb") or glb_metrics.get("glb") or splat_path
    preview_url = None
    if preview_target is not None:
        # 把绝对路径转成 /static/jobs/... 形式
        rel = Path(str(preview_target)).resolve().relative_to(config.OUTPUT_DIR.resolve())
        preview_url = f"{config.STATIC_URL_PREFIX}/jobs/{rel.as_posix()}"

    job_store.update_job(
        job_id,
        status="success",
        stage="finished",
        progress=1.0,
        outputs={"preview_url": preview_url} if preview_url else None,
    )
    job_store.append_log(job_id, "[reconstruct] finished")
    return metrics


# ---------- 命令行入口（用于本地调试） ----------
def _main() -> None:
    parser = argparse.ArgumentParser(description="本地直跑 3D 重建管线")
    parser.add_argument("--job-id", default=None)
    parser.add_argument("--input", required=True, help="图片目录或视频文件路径")
    parser.add_argument("--mode", choices=["images", "video"], default="images")
    parser.add_argument("--quality", choices=list(config.QUALITY_CONFIG.keys()), default="fast")
    parser.add_argument("--export-glb", action="store_true")
    parser.add_argument("--mock", action="store_true")
    args = parser.parse_args()

    job_id = args.job_id or generate_job_id("recon")
    job_store.create_job(job_id, "reconstruct",
                         params={"mode": args.mode, "quality": args.quality, "mock": args.mock})

    raw_dir = config.RAW_DIR / job_id
    if args.mode == "video":
        video_dir = raw_dir / "video"
        video_dir.mkdir(parents=True, exist_ok=True)
        target = video_dir / Path(args.input).name
        shutil.copy2(args.input, target)
        input_paths = [str(target)]
    else:
        images_dir = raw_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        src = Path(args.input)
        if src.is_dir():
            for p in src.rglob("*"):
                if p.is_file() and p.suffix.lower() in config.IMAGE_EXTENSIONS:
                    shutil.copy2(p, images_dir / p.name)
        else:
            shutil.copy2(src, images_dir / src.name)
        input_paths = [str(images_dir)]

    try:
        run_reconstruction_job(
            job_id=job_id,
            input_paths=input_paths,
            input_mode=args.mode,
            quality=args.quality,
            export_glb=args.export_glb,
            mock=args.mock,
        )
        print(f"[ok] job={job_id} status=success")
    except Exception as e:
        job_store.update_job(job_id, status="failed", error=str(e))
        print(f"[fail] job={job_id} error={e}")
        raise


if __name__ == "__main__":
    _main()
