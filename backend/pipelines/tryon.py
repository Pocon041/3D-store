"""二维试穿管线：包装 external/CatVTON 推理脚本。

mock 模式直接产生占位结果，用于无 GPU / 未克隆 CatVTON 的场景。
"""
from __future__ import annotations

import argparse
import os
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


def _project_path_env(env: dict[str, str], name: str, rel_path: str) -> None:
    value = env.get(name)
    path = Path(value) if value else config.PROJECT_ROOT / rel_path
    if not path.is_absolute():
        path = config.PROJECT_ROOT / path
    path.mkdir(parents=True, exist_ok=True)
    env[name] = str(path)


def _catvton_runtime_env() -> dict[str, str]:
    env = os.environ.copy()
    for name, rel_path in {
        "XDG_CACHE_HOME": ".cache",
        "HF_HOME": ".cache/huggingface",
        "HF_HUB_CACHE": ".cache/huggingface/hub",
        "HUGGINGFACE_HUB_CACHE": ".cache/huggingface/hub",
        "HF_DATASETS_CACHE": ".cache/huggingface/datasets",
        "TRANSFORMERS_CACHE": ".cache/huggingface/transformers",
        "DIFFUSERS_CACHE": ".cache/huggingface/diffusers",
        "TORCH_HOME": ".cache/torch",
        "MPLCONFIGDIR": ".cache/matplotlib",
        "CONDA_PKGS_DIRS": ".cache/conda/pkgs",
        "CONDA_ENVS_PATH": ".conda/envs",
        "TEMP": ".cache/tmp",
        "TMP": ".cache/tmp",
    }.items():
        _project_path_env(env, name, rel_path)
    env.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    env.setdefault("HF_HUB_DISABLE_XET", "1")
    env.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
    env.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "20")
    env.setdefault("TOKENIZERS_PARALLELISM", "false")
    # Bypass Windows IE proxy (127.0.0.1:10808 etc.) for HF / mirrors so the
    # subprocess does not deadlock on TLS handshake when fetching model weights.
    bypass_hosts = [
        "huggingface.co",
        "hf-mirror.com",
        "cdn-lfs.huggingface.co",
        "pypi.tuna.tsinghua.edu.cn",
        "mirrors.ustc.edu.cn",
        "127.0.0.1",
        "localhost",
    ]
    existing = env.get("NO_PROXY", "")
    no_proxy = ",".join([existing] + bypass_hosts).strip(",")
    env["NO_PROXY"] = no_proxy
    env["no_proxy"] = no_proxy
    return env


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

    # CATVTON_PYTHON 应当指向 .conda/envs/catvton/python.exe（由 scripts/install_catvton_env.ps1 创建）。
    # 如果不存在，提示用户先跑安装脚本，而不是用一个错的 PATH python 跑。
    catvton_py = Path(config.CATVTON_PYTHON)
    if not catvton_py.exists():
        msg = (
            f"CatVTON Python 解释器不存在：{catvton_py}\n"
            f"请先运行 scripts/install_catvton_env.ps1 创建 conda 环境，"
            f"或用 CATVTON_PYTHON 环境变量指向已有的 python.exe。"
        )
        if config.ALLOW_MISSING_TOOLS_FALLBACK_TO_MOCK:
            job_store.append_log(job_id, f"[fallback] {msg}")
            return mock_pipeline.run_mock_tryon(job_id, person_path, garment_path)
        raise RuntimeError(msg)

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
        run_command(cmd, cwd=str(config.CATVTON_DIR), env=_catvton_runtime_env(), log_path=log_path)
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
