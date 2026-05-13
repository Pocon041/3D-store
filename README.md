# AIGC 3D Commerce Demo

本地原型：多视角商品 3D 重建 + 二维虚拟试穿。后端 FastAPI，前端 Vite + React，3D 展示用 `<model-viewer>`。
真实管线包装 Nerfstudio + COLMAP + FFmpeg + glTF Transform；试穿包装 CatVTON。所有真实工具都可缺省，对应任务可用 mock 模式跑通。

## 目录

```
aigc-3d-commerce-demo/
├── backend/             FastAPI 后端
├── frontend/            Vite + React 前端
├── scripts/             启动脚本与命令样例
├── external/            放置三方仓库（CatVTON 等）
├── data/                输入数据
├── outputs/             任务产物
└── docs/                设计与实验文档
```

## 快速开始（mock 全链路）

无需 GPU 也无需 Nerfstudio / CatVTON。

### 1. 安装后端依赖

```bash
python -m venv .venv
# Linux / macOS
source .venv/bin/activate
# Windows PowerShell
# .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. 启动后端

```bash
bash scripts/run_backend.sh
# 或 Windows
powershell -File scripts/run_backend.ps1
```

健康检查：

```bash
curl http://localhost:8000/api/health
# {"status":"ok","version":"0.1.0"}
```

### 3. 启动前端

```bash
bash scripts/run_frontend.sh
# 或 Windows
powershell -File scripts/run_frontend.ps1
```

打开 http://localhost:5173 ，勾选「mock 模式」，点击「开始重建」，几秒后 `<model-viewer>` 会显示一个立方体；试穿面板上传两张图也能立刻得到拼接的占位图。

### 4. 命令行直接跑 mock

```bash
python -m backend.pipelines.reconstruct \
  --job-id local_mock --input data/samples/product_images \
  --mode images --quality fast --export-glb --mock
```

输出：`outputs/jobs/local_mock/exports/glb/model.optimized.glb` 与 `metrics.json`。

## 真实管线

### 安装外部工具

参见 `scripts/setup_env.md`。Linux 下：

```bash
sudo apt install -y ffmpeg colmap blender
conda create -n nerfstudio python=3.10 -y
conda activate nerfstudio
pip install nerfstudio
npm install -g @gltf-transform/cli
```

CatVTON：

```bash
git clone https://github.com/Zheng-Chong/CatVTON external/CatVTON
```

### 启动方式

后端默认假设当前 shell 已经 `conda activate nerfstudio`。如果想让后端进程内部用 `conda run` 包装，设置：

```bash
export USE_CONDA_WRAPPER=true
```

如果某些工具未装，但希望任务在缺工具时自动降级到 mock：

```bash
export ALLOW_MISSING_TOOLS_FALLBACK_TO_MOCK=true
```

### 触发真实重建

前端取消勾选「mock 模式」即可。或命令行：

```bash
python -m backend.pipelines.reconstruct \
  --job-id real_demo --input data/samples/product_images \
  --mode images --quality fast --export-glb
```

## 架构与任务状态

参见 `docs/system_design.md`。任务状态文件统一在：

```
outputs/jobs/<job_id>/job.json    # 状态与输出路径
outputs/jobs/<job_id>/job.log     # 命令日志
outputs/jobs/<job_id>/metrics.json # 实验指标
```

## API 一览

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/api/health` | 健康检查 |
| POST | `/api/reconstruct` | 上传图片 / 视频，创建重建任务 |
| POST | `/api/tryon` | 上传人像 + 服装图，创建试穿任务 |
| GET  | `/api/jobs` | 任务列表 |
| GET  | `/api/jobs/{job_id}` | 单任务状态 |
| GET  | `/api/jobs/{job_id}/files` | 输出文件列表 |
| GET  | `/api/metrics/{job_id}` | metrics.json |
| GET  | `/static/jobs/...` | 输出目录直挂载 |
| GET  | `/viewer?src=...` | 直接的 model-viewer 页面 |

## 常用命令

参见 `scripts/sample_commands.md`。

## Gradio 备选

如果 React 前端出问题：

```bash
python demo_gradio.py
```

会启动一个最小 Gradio 应用，复用相同的后端管线代码。

## 已知限制

- 任务在 daemon 线程里执行，进程重启会丢失正在跑的任务。生产场景请换 Celery/RQ。
- COLMAP 依赖图片有充分重叠，否则 `transforms.json` 不会生成。
- `splatfacto` 在 CPU 上不可用，需要支持 CUDA 的 GPU。
- `<model-viewer>` 加载 PLY 不如 GLB 稳定，方案保留两条展示路径。

.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --no-access-log

npm run dev