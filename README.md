# AIGC 3D Mall

面向“AI 与数字经济”课程期末作业的 3D 电商原型：用户可以浏览可旋转的 3D 商品，商家可以用单张商品图或 1-4 张多视角图生成 3D 资产，并把生成结果一键上架到商城。项目默认使用 mock 管线保证本地可跑通；配置 Tripo3D API Key 后可切换到真实图生 3D。

## 当前功能

- 3D 商城：首页商品流、分类筛选、搜索、商品详情、购物车。
- 3D 展示：基于 `<model-viewer>` 加载 GLB，支持旋转、缩放和商品详情预览。
- 图生 3D：上传单张商品图，生成可展示的 GLB 资产；支持 mock / Tripo3D provider。
- 多视角生 3D：按正面、背面、左侧、右侧上传 1-4 张图，前端以 2x2 四宫格展示素材，调用多视角生成任务。
- 3D 假人换装台：Three.js 真实比例人台、服装几何预设、材质切换、体型调节、商城商品 GLB 叠穿和手动对齐。
- 商家工作台：查看任务状态、预览结果、下载文件、将成功任务发布为商品。
- 二维虚拟试穿：上传人像和服装图，支持 mock 或外部 CatVTON 管线。
- 任务历史：保存最近任务、日志、指标和生成产物。

## 技术栈

- 前端：Vite + React + Three.js + `@google/model-viewer`
- 后端：FastAPI + Pydantic + Uvicorn
- 3D / 图像处理：trimesh、Pillow、OpenCV、NumPy
- 可选真实管线：Tripo3D、Nerfstudio、COLMAP、FFmpeg、glTF Transform、CatVTON

## 项目结构

```text
aigc-3d-commerce-demo/
├── backend/              FastAPI 接口、商品数据、任务管线
├── frontend/             React 商城与商家工作台
├── data/                 示例输入与本地商品资产
├── docs/                 设计与实验文档
├── external/             第三方仓库，例如 CatVTON
├── outputs/              任务输出目录
├── scripts/              启动、下载、环境配置脚本
├── tests/                后端单元测试与 API 集成测试
├── requirements.txt      Python 依赖
└── README.md
```

## 快速开始

### 1. 安装后端依赖

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

macOS / Linux:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 安装前端依赖

```powershell
cd frontend
npm install
cd ..
```

### 3. 启动项目

Windows 推荐使用一键脚本：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start.ps1 -Restart
```

脚本会启动后端 `http://127.0.0.1:8000` 和前端 `http://localhost:5173`，日志写入 `logs/`，并把 Hugging Face / torch / pip / npm 等缓存导向项目内 `.cache/`。停止服务：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\stop.ps1
```

也可以手动启动：

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

另开一个终端：

```powershell
cd frontend
npm run dev
```

如需在当前终端里手动安装依赖，也可以先把缓存环境变量写入当前会话：

```powershell
. .\scripts\cache_env.ps1
```

打开 `http://localhost:5173`，默认进入商城；商家工作台在 `http://localhost:5173/#/studio`，3D 假人换装台在 `http://localhost:5173/#/avatar-tryon`。

## 图生 3D Provider

默认 provider 是 `mock`，不需要 API Key，会生成占位 GLB，适合课堂演示和本地开发。

如需调用 Tripo3D，将 `scripts/.env.example` 复制为 `scripts/.env.local`，并填写：

```powershell
Copy-Item scripts\.env.example scripts\.env.local
```

```dotenv
IMAGE3D_PROVIDER=tripo
TRIPO_API_KEY=你的 Tripo3D Bearer Token
TRIPO_MODEL_VERSION=auto
```

再重新运行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start.ps1 -Restart
```

说明：

- 单图生 3D 使用 `/api/image-to-3d`。
- 多视角生 3D 使用 `/api/multiview-to-3d`，上传顺序为正面、背面、左侧、右侧。
- 如果 Tripo3D 任务已创建但本地拉取失败，可以通过 `/api/image-to-3d/resume` 用已有 task id 恢复下载。

## 示例资产与 Git

仓库不会提交大体积或生成型 3D 文件，相关路径已写入 `.gitignore`：

```text
outputs/jobs/
data/polyhaven_products.json
data/samples/glb/
data/samples/polyhaven/
data/samples/thumb/
data/samples/*.glb
external/CatVTON/
```

克隆后即使没有这些文件，mock 流程和远程 Khronos 示例商品仍可运行。如需补充本地 3D 商品素材，可按需执行：

```powershell
.\.venv\Scripts\python.exe scripts\fetch_demo_models.py
.\.venv\Scripts\python.exe scripts\fetch_polyhaven_models.py --count 84
```

这些脚本会下载模型和缩略图到 `data/samples/`，文件体积较大，不建议上传 GitHub。

## API 一览

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/health` | 后端健康检查 |
| GET | `/api/products` | 商品列表、分类与搜索 |
| GET | `/api/products/{product_id}` | 商品详情 |
| DELETE | `/api/products/{product_id}` | 删除用户自定义商品 |
| POST | `/api/products/publish/{job_id}` | 将成功的 3D 任务发布为商品 |
| POST | `/api/image-to-3d` | 单图生成 3D |
| POST | `/api/multiview-to-3d` | 多视角生成 3D |
| GET | `/api/image-to-3d/providers` | 查询可用 provider |
| POST | `/api/image-to-3d/resume` | 恢复 Tripo3D 已有任务 |
| POST | `/api/reconstruct` | 高级 NeRF / 3DGS 重建入口 |
| POST | `/api/tryon` | 虚拟试穿任务 |
| GET | `/api/jobs` | 最近任务列表 |
| GET | `/api/jobs/{job_id}` | 单个任务状态 |
| GET | `/api/jobs/{job_id}/files` | 任务输出文件列表 |
| GET | `/api/metrics/{job_id}` | 实验指标 |
| GET | `/static/jobs/...` | 生成资产静态访问 |
| GET | `/viewer?src=...` | 独立 3D 预览页 |

## 常用检查

前端构建：

```powershell
cd frontend
npm run build
```

后端测试：

```powershell
.\.venv\Scripts\python.exe -m pip install pytest
.\.venv\Scripts\python.exe -m pytest tests -v
```

## 可选真实重建与试穿

高级重建管线包装了 Nerfstudio + COLMAP + FFmpeg + glTF Transform，二维试穿可包装 CatVTON。重建环境配置见 `scripts/setup_env.md`，CatVTON 本地试穿配置见 `scripts/setup_catvton.md`。

常用环境变量：

```dotenv
USE_CONDA_WRAPPER=false
NERFSTUDIO_CONDA_ENV=nerfstudio
CATVTON_CONDA_ENV=catvton
ALLOW_MISSING_TOOLS_FALLBACK_TO_MOCK=true
```

如果未安装真实工具，保持 mock 模式即可完成课堂演示。

## 课程作业定位

这个 Demo 展示的是“AI 生成式资产如何进入数字商品流通”的最小闭环：商品图片被转化为 3D 数字资产，资产进入电商货架，用户在浏览、试穿和交互预览中获得更接近真实商品的体验。它适合作为数字经济学课程中关于 AIGC、数字商品、平台供给效率和沉浸式消费的实验型展示。
