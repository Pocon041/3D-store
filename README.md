# AIGC 3D Mall

面向"AI 与数字经济"课程的 3D 电商原型。包含 3D 商城、商家工作台、2D 虚拟试穿和带骨骼的 3D 人台换装台。整体围绕一条主线：**商品图 → 3D 资产 → 货架 → 试穿/换装**。

默认 mock 管线保证零配置即可跑通整套交互；配置真实 API Key 或本地模型后，可切换到 Tripo3D 图生 3D 与本地 CatVTON 真实试穿。

## 主要功能

| 模块 | 路由 | 说明 |
| --- | --- | --- |
| 3D 商城 | `#/shop` | 商品流、分类、搜索、详情、购物车，全部基于 `<model-viewer>` 渲染 GLB |
| 商家工作台 | `#/studio` | 单图 / 多视角生 3D、GLB 直接导入、任务历史、一键上架 |
| 2D 虚拟试穿 | `#/tryon` | 上传人像 + 服装图，mock 或本地 CatVTON 管线生成上身效果 |
| 3D 人台换装 | `#/avatar-tryon` | Three.js 骨骼动画人台，4 槽位（上装/下装/连衣裙/鞋）叠穿，姿态预设 + 30 个骨骼角度滑杆，姿态/贴合/服装/场景四 tab 控制面板 |
| 购物车 | `#/cart` | 本地存储购物车，支持下单流程占位 |

3D 人台换装台支持：

- 4 个穿搭槽位独立选择商城商品或导入自有 GLB
- 缩放 / 高度 / 左右 / 前后 / 旋转 五维微调
- 自然站姿、放松垂臂、A 字手臂、陈列侧身 4 套姿态预设
- 头身、手臂、腿脚 3 组骨骼细调
- 陶瓷 / 石墨 / 暖肤 / 工作室灰 4 种人台底色，半透明人台、参考线开关
- 支持导入自定义人台 GLB
- 一键导出搭配画面 PNG

## 技术栈

- 前端：Vite + React + Three.js + `@google/model-viewer`
- 后端：FastAPI + Pydantic + Uvicorn
- 3D / 图像处理：trimesh、Pillow、OpenCV、NumPy
- 可选真实管线：Tripo3D（图生 3D）、CatVTON（2D 试穿）、Nerfstudio + COLMAP + FFmpeg（高级重建）

## 项目结构

```text
aigc-3d-commerce-demo/
├── backend/              FastAPI 接口、商品数据、任务管线
│   ├── main.py           路由入口
│   ├── config.py         路径、Provider、CatVTON 命令模板
│   └── pipelines/        image_to_3d / reconstruct / tryon / import_glb / mock
├── frontend/             Vite + React 前端
│   ├── pages/            Shop / ProductDetail / Studio / TryOn / AvatarTryOn / Cart
│   └── components/       Upload3D / TryOnPanel / AvatarDressStage / JobResultCard 等
├── data/                 示例输入、商品资产、可选 CatVTON 模型权重
├── external/             第三方仓库（CatVTON 等，不入库）
├── outputs/              任务输出目录
├── scripts/              启动、安装、模型下载、缓存重定向脚本
├── tests/                后端单元测试与 API 集成测试
├── .cache/               所有缓存集中地（HF / torch / pip / npm，启动脚本会自动重定向）
├── .conda/               项目本地 conda 环境（CatVTON 等独立环境）
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

打开 `http://localhost:5173` 默认进入商城。其它页面：

- `#/studio` 商家工作台
- `#/tryon` 2D 虚拟试穿
- `#/avatar-tryon` 3D 人台换装
- `#/cart` 购物车

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
| POST | `/api/products/publish/{job_id}` | 将成功任务发布为商品 |
| POST | `/api/image-to-3d` | 单图生成 3D |
| POST | `/api/multiview-to-3d` | 多视角生成 3D |
| POST | `/api/import-glb` | 直接导入已有 GLB 入库 |
| GET | `/api/image-to-3d/providers` | 查询可用图生 3D Provider |
| POST | `/api/image-to-3d/resume` | 用已有 Tripo task id 恢复任务 |
| POST | `/api/reconstruct` | NeRF / 3DGS 高级重建入口 |
| POST | `/api/tryon` | 二维虚拟试穿任务 |
| GET | `/api/tryon/capabilities` | 检测 CatVTON 环境与权重是否就位 |
| GET | `/api/jobs` | 最近任务列表 |
| GET | `/api/jobs/{job_id}` | 单个任务状态 |
| GET | `/api/jobs/{job_id}/files` | 任务输出文件列表 |
| GET | `/api/metrics/{job_id}` | 实验指标 |
| GET | `/static/jobs/...` | 生成资产静态访问 |
| GET | `/viewer?src=...` | 独立 GLB 预览页 |

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

## 真实 CatVTON 试穿（可选）

`scripts/install_catvton_env.ps1` 会在 **项目内 `.conda/envs/catvton/`** 创建独立 Python 3.10 环境，安装 PyTorch 2.4.0 + cu124 与 CatVTON requirements，整个过程不污染 C 盘和 base 环境：

```powershell
git clone https://github.com/Zheng-Chong/CatVTON external/CatVTON
powershell -ExecutionPolicy Bypass -File scripts\install_catvton_env.ps1
```

下载 CatVTON 与 SD inpainting 权重到 `data/models/`（带断点续传，适合 GFW 网络）：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\fetch_models_bits.ps1
```

或用 huggingface_hub Python 接口：

```powershell
.\.venv\Scripts\python.exe scripts\fetch_catvton_models.py
```

权重就位后，`backend/config.py` 会自动把 `CATVTON_BASE_MODEL_PATH` / `CATVTON_RESUME_PATH` 指向本地路径。前端 `#/tryon` 取消勾选 mock 即可调用真实管线。详细参数见 `scripts/setup_catvton.md`。

## 高级 NeRF / 3DGS 重建（可选）

包装 Nerfstudio + COLMAP + FFmpeg + glTF Transform，参考 `scripts/setup_env.md`。常用环境变量：

```dotenv
USE_CONDA_WRAPPER=false
NERFSTUDIO_CONDA_ENV=nerfstudio
ALLOW_MISSING_TOOLS_FALLBACK_TO_MOCK=true
```

未安装真实工具时，保持 mock 模式。

## 课程作业定位

这个 Demo 展示的是"AI 生成式资产如何进入数字商品流通"的最小闭环：

1. 商品图被 AI 转成 3D 资产（Tripo3D 单图 / 多视角生 3D）
2. 资产进入电商货架（自动入库 + 一键上架）
3. 用户在浏览、虚拟试穿、3D 人台换装中获得接近真实商品的体验
