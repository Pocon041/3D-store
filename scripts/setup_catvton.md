# CatVTON 本地试穿配置

适合 RTX 4060 Laptop 的本地真实虚拟试穿方案。项目后端会调用：

```text
scripts/run_catvton_single.py -> external/CatVTON
```

## 1. 克隆 CatVTON

```powershell
git clone https://github.com/Zheng-Chong/CatVTON external/CatVTON
```

`external/CatVTON/` 已在 `.gitignore` 中，不会提交到 GitHub。

## 2. 创建环境

建议使用独立 conda 环境，避免和商城后端依赖混在一起。

```powershell
conda create -n catvton python=3.10 -y
conda activate catvton
. .\scripts\cache_env.ps1
```

安装 PyTorch CUDA 版本时，以 https://pytorch.org/get-started/locally/ 给出的命令为准。4060 Laptop 通常选择 CUDA 12.x wheel。

然后安装 CatVTON 依赖：

```powershell
cd external\CatVTON
pip install -r requirements.txt
cd ..\..
```

首次运行会从 Hugging Face 下载 `zhengchong/CatVTON` 权重，需要能访问 Hugging Face。

## 3. 配置项目环境

复制示例环境文件：

```powershell
Copy-Item scripts\.env.example scripts\.env.local
```

建议先用 4060 Laptop 默认档：

```dotenv
XDG_CACHE_HOME=.cache
HF_HOME=.cache/huggingface
HF_HUB_CACHE=.cache/huggingface/hub
HUGGINGFACE_HUB_CACHE=.cache/huggingface/hub
HF_DATASETS_CACHE=.cache/huggingface/datasets
TRANSFORMERS_CACHE=.cache/huggingface/transformers
DIFFUSERS_CACHE=.cache/huggingface/diffusers
TORCH_HOME=.cache/torch
PIP_CACHE_DIR=.cache/pip
NPM_CONFIG_CACHE=.cache/npm
USE_CONDA_WRAPPER=true
CATVTON_CONDA_ENV=catvton
CATVTON_WIDTH=768
CATVTON_HEIGHT=1024
CATVTON_MIXED_PRECISION=bf16
CATVTON_ALLOW_TF32=true
CATVTON_SKIP_SAFETY_CHECK=true
ALLOW_MISSING_TOOLS_FALLBACK_TO_MOCK=true
```

如果显存不足，降到：

```dotenv
CATVTON_WIDTH=512
CATVTON_HEIGHT=768
CATVTON_STEPS=30
```

`scripts/start.ps1` 会把这些相对路径解析到项目根目录下的 `.cache/`，避免 Hugging Face / torch / pip / npm 把缓存写到 C 盘用户目录。

## 4. 启动

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start.ps1 -Restart
```

前端进入 `#/tryon`，取消勾选 mock 模式，上传人像图和服装图。

## 5. 输出

每次任务输出到：

```text
outputs/jobs/<job_id>/tryon/
├── person.<ext>
├── garment.<ext>
├── result.png
└── compare.png
```

`result.png` 是最终试穿图，`compare.png` 是人像 mask / 服装 / 结果三联对比图。
