"""集中配置：路径、外部命令模板、质量档位。

所有可能因环境变化的命令字符串都集中在这里，避免散落到多个文件。
"""
from __future__ import annotations

import os
from pathlib import Path

# 项目根目录（aigc-3d-commerce-demo/）
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# 数据目录
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw" / "jobs"
PROCESSED_DIR = DATA_DIR / "processed" / "nerfstudio"
SAMPLES_DIR = DATA_DIR / "samples"

# 输出目录
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "jobs"
EXPORT_DIR = PROJECT_ROOT / "outputs" / "exports"
REPORT_DIR = PROJECT_ROOT / "outputs" / "reports"

# 外部依赖目录
EXTERNAL_DIR = PROJECT_ROOT / "external"
CATVTON_DIR = EXTERNAL_DIR / "CatVTON"

# 静态资源 URL 前缀（FastAPI 挂载点）
STATIC_URL_PREFIX = "/static"

# Conda 环境名（如果系统环境直接可用，可在脚本里覆盖为空字符串）
NERFSTUDIO_CONDA_ENV = os.environ.get("NERFSTUDIO_CONDA_ENV", "nerfstudio")
CATVTON_CONDA_ENV = os.environ.get("CATVTON_CONDA_ENV", "catvton")

# 是否走 conda run 包装。如果 ns-train / python 已在 PATH 中，可以设为 False。
USE_CONDA_WRAPPER = os.environ.get("USE_CONDA_WRAPPER", "false").lower() == "true"

# 命令存在性的回退处理：当 ns-train 等不存在且未启用 mock 时直接报错。
ALLOW_MISSING_TOOLS_FALLBACK_TO_MOCK = (
    os.environ.get("ALLOW_MISSING_TOOLS_FALLBACK_TO_MOCK", "false").lower() == "true"
)

# 质量档位 -> Nerfstudio 训练参数
QUALITY_CONFIG = {
    "fast": {
        "method": "splatfacto",
        "max_iterations": 3000,
    },
    "balanced": {
        "method": "splatfacto",
        "max_iterations": 7000,
    },
    "high": {
        "method": "splatfacto-big",
        "max_iterations": 15000,
    },
}

# FFmpeg 视频抽帧参数
FFMPEG_EXTRACT_VF = "fps=2,scale=1280:-1"

# CatVTON 推理命令模板（占位符将在 tryon.py 中被替换）
# 真实接入时请按 external/CatVTON 仓库的 inference 脚本实参对齐
CATVTON_COMMAND_TEMPLATE = [
    "python",
    "inference.py",
    "--person",
    "{person_image}",
    "--cloth",
    "{garment_image}",
    "--output",
    "{output_image}",
]

# Nerfstudio 命令前缀（启用 conda 包装时使用）
def _conda_run(env: str) -> list[str]:
    return ["conda", "run", "-n", env, "--no-capture-output"]


def nerfstudio_cmd_prefix() -> list[str]:
    if USE_CONDA_WRAPPER:
        return _conda_run(NERFSTUDIO_CONDA_ENV)
    return []


def catvton_cmd_prefix() -> list[str]:
    if USE_CONDA_WRAPPER:
        return _conda_run(CATVTON_CONDA_ENV)
    return []


# 后端服务地址
BACKEND_HOST = os.environ.get("BACKEND_HOST", "0.0.0.0")
BACKEND_PORT = int(os.environ.get("BACKEND_PORT", "8000"))

# 允许的图片扩展名
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".avi", ".mkv"}

# 模糊度阈值（Laplacian 方差，越小越模糊；低于此值被判为模糊）
BLUR_VAR_THRESHOLD = float(os.environ.get("BLUR_VAR_THRESHOLD", "30.0"))

# -------- 图生 3D Provider 配置 --------
# 可选值: mock / tripo / hunyuan / meshy / triposr
# 没设或值非法时使用 mock，保证无 key 也能跑通 UX 全流程
IMAGE3D_PROVIDER = os.environ.get("IMAGE3D_PROVIDER", "mock").lower()

# Tripo3D API
TRIPO_API_KEY = os.environ.get("TRIPO_API_KEY", "")
TRIPO_API_BASE = os.environ.get("TRIPO_API_BASE", "https://api.tripo3d.ai/v2/openapi")
# 设为 "auto" 让服务端自行选择默认版本，避免触发某些 tier key 不支持的版本
TRIPO_MODEL_VERSION = os.environ.get("TRIPO_MODEL_VERSION", "auto")

# 腾讯混元 3D（占位，后续接入）
HUNYUAN_SECRET_ID = os.environ.get("HUNYUAN_SECRET_ID", "")
HUNYUAN_SECRET_KEY = os.environ.get("HUNYUAN_SECRET_KEY", "")

# Meshy（占位）
MESHY_API_KEY = os.environ.get("MESHY_API_KEY", "")

# 图生 3D 轮询参数
IMAGE3D_POLL_INTERVAL_SEC = float(os.environ.get("IMAGE3D_POLL_INTERVAL_SEC", "3"))
IMAGE3D_POLL_TIMEOUT_SEC = float(os.environ.get("IMAGE3D_POLL_TIMEOUT_SEC", "300"))


def ensure_runtime_dirs() -> None:
    """启动时确保运行期需要的目录都已存在。"""
    for p in [DATA_DIR, RAW_DIR, PROCESSED_DIR, SAMPLES_DIR,
              OUTPUT_DIR, EXPORT_DIR, REPORT_DIR, EXTERNAL_DIR]:
        p.mkdir(parents=True, exist_ok=True)
