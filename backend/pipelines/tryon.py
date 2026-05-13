"""二维试穿管线：包装 external/CatVTON 推理脚本。

mock 模式直接产生占位结果，用于无 GPU / 未克隆 CatVTON 的场景。
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import Optional

from .. import config
from ..job_store import job_store
from ..utils.file_utils import generate_job_id
from ..utils.process_utils import command_exists, run_command
from . import mock_pipeline


def _job_log_path(job_id: str) -> Path:
    return config.OUTPUT_DIR / job_id / "job.log"


def _format_command(template: list[str], **kwargs: str) -> list[str]:
    return [arg.format(**kwargs) for arg in template]


def run_tryon_job(
    job_id: str,
    person_image_path: str,
    garment_image_path: str,
    category: str = "upper",
    mock: bool = False,
) -> dict:
    """二维试穿主入口。"""
    job_dir = config.OUTPUT_DIR / job_id
    out_dir = job_dir / "tryon"
    out_dir.mkdir(parents=True, exist_ok=True)

    person_path = Path(person_image_path)
    garment_path = Path(garment_image_path)
    if not person_path.exists() or not garment_path.exists():
        raise RuntimeError("人像图或服装图不存在")

    job_store.update_job(
        job_id,
        status="running",
        stage="received",
        progress=0.1,
        params={"category": category, "mock": mock},
    )

    if mock:
        return mock_pipeline.run_mock_tryon(job_id, person_path, garment_path)

    # 真实模式：拷贝输入到任务目录，执行 CatVTON 推理脚本
    person_target = out_dir / ("person" + person_path.suffix.lower())
    garment_target = out_dir / ("garment" + garment_path.suffix.lower())
    shutil.copy2(person_path, person_target)
    shutil.copy2(garment_path, garment_target)
    job_store.update_job(job_id, stage="prepare_inputs", progress=0.3)

    if not config.CATVTON_DIR.exists():
        if config.ALLOW_MISSING_TOOLS_FALLBACK_TO_MOCK:
            job_store.append_log(job_id, "[fallback] CatVTON 目录不存在，回退 mock")
            return mock_pipeline.run_mock_tryon(job_id, person_path, garment_path)
        raise RuntimeError(f"未找到 CatVTON 目录：{config.CATVTON_DIR}")

    if config.USE_CONDA_WRAPPER:
        if not command_exists("conda"):
            raise RuntimeError("启用 USE_CONDA_WRAPPER 后需要 conda 命令在 PATH 中")
    elif not command_exists("python"):
        raise RuntimeError("python 命令不在 PATH 中")

    result_path = out_dir / "result.png"
    cmd_template = config.catvton_cmd_prefix() + config.CATVTON_COMMAND_TEMPLATE
    cmd = _format_command(
        cmd_template,
        person_image=str(person_target.resolve()),
        garment_image=str(garment_target.resolve()),
        output_image=str(result_path.resolve()),
        category=category,
    )

    job_store.update_job(job_id, stage="run_catvton", progress=0.6)
    job_store.append_log(job_id, "[catvton] start single-image virtual try-on")
    log_path = _job_log_path(job_id)
    try:
        run_command(cmd, cwd=str(config.CATVTON_DIR), log_path=log_path)
    except Exception as e:
        job_store.update_job(job_id, status="failed", error=str(e))
        raise

    if not result_path.exists():
        raise RuntimeError("CatVTON 未生成结果图，请检查日志")

    compare_path = out_dir / "compare.png"
    preview_url = f"{config.STATIC_URL_PREFIX}/jobs/{job_id}/tryon/result.png"
    compare_url = (
        f"{config.STATIC_URL_PREFIX}/jobs/{job_id}/tryon/compare.png"
        if compare_path.exists()
        else None
    )
    job_store.update_job(
        job_id,
        status="success",
        stage="finished",
        progress=1.0,
        outputs={
            "tryon_person": str(person_target),
            "tryon_garment": str(garment_target),
            "tryon_result": str(result_path),
            "tryon_compare": str(compare_path) if compare_path.exists() else None,
            "preview_url": preview_url,
        },
    )
    job_store.append_log(job_id, "[catvton] finished")
    return {
        "result": str(result_path),
        "preview_url": preview_url,
        "compare_url": compare_url,
    }


def _main() -> None:
    parser = argparse.ArgumentParser(description="本地直跑试穿管线")
    parser.add_argument("--person", required=True)
    parser.add_argument("--garment", required=True)
    parser.add_argument("--category", default="upper")
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--job-id", default=None)
    args = parser.parse_args()

    job_id = args.job_id or generate_job_id("tryon")
    job_store.create_job(job_id, "tryon", params={"category": args.category, "mock": args.mock})
    try:
        run_tryon_job(job_id, args.person, args.garment, args.category, args.mock)
        print(f"[ok] job={job_id} status=success")
    except Exception as e:
        job_store.update_job(job_id, status="failed", error=str(e))
        print(f"[fail] job={job_id} error={e}")
        raise


if __name__ == "__main__":
    _main()
