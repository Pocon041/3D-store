# 环境安装步骤

## 1. 系统依赖（Linux 示例）

```bash
sudo apt update
sudo apt install -y ffmpeg colmap blender
```

Windows：

- `ffmpeg`：到 https://www.gyan.dev/ffmpeg/builds/ 下载并加入 PATH
- `colmap`：到 https://github.com/colmap/colmap/releases 下载安装
- `blender`：https://www.blender.org/download/

## 2. Nerfstudio 环境（用于真实 3D 重建）

```bash
conda create -n nerfstudio python=3.10 -y
conda activate nerfstudio
pip install nerfstudio
```

如果已在 PATH 中可直接调用 `ns-train`，可设置环境变量：

```bash
export USE_CONDA_WRAPPER=false
```

## 3. CatVTON 环境（用于真实试穿）

```bash
git clone https://github.com/Zheng-Chong/CatVTON external/CatVTON
conda create -n catvton python=3.10 -y
conda activate catvton
cd external/CatVTON
pip install -r requirements.txt
```

## 4. 后端依赖

```bash
pip install -r requirements.txt
```

## 5. 前端依赖

```bash
cd frontend
npm install
```

## 6. glTF Transform CLI

```bash
npm install --global @gltf-transform/cli
```

## 7. （可选）回退到 mock

如果某些工具未装，但希望不报错，可设置：

```bash
export ALLOW_MISSING_TOOLS_FALLBACK_TO_MOCK=true
```

此时管线在检测到工具缺失时会自动走 mock。
