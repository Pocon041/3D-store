# 常用命令参考

## 启动

```bash
bash scripts/run_backend.sh        # 后端 :8000
bash scripts/run_frontend.sh       # 前端 :5173
```

Windows PowerShell：

```powershell
powershell -File scripts/run_backend.ps1
powershell -File scripts/run_frontend.ps1
```

## 健康检查

```bash
curl http://localhost:8000/api/health
```

## Mock 全链路（无需 GPU / Nerfstudio）

```bash
# 任意上传一张图
curl -X POST http://localhost:8000/api/reconstruct \
  -F "files=@data/samples/dummy.png" \
  -F "mode=images" -F "quality=fast" -F "export_glb=true" -F "mock=true"

# 复制返回的 job_id 后查看状态
curl http://localhost:8000/api/jobs/<job_id>
```

## 真实 Nerfstudio

```bash
conda activate nerfstudio
USE_CONDA_WRAPPER=false bash scripts/run_backend.sh

# 或者上层用 conda run 包装
USE_CONDA_WRAPPER=true bash scripts/run_backend.sh
```

## 命令行直接跑 mock 重建

```bash
python -m backend.pipelines.reconstruct \
  --job-id local_mock --input data/samples/product_images \
  --mode images --quality fast --export-glb --mock
```

## 命令行直接跑 mock 试穿

```bash
python -m backend.pipelines.tryon \
  --person data/samples/tryon/person.jpg \
  --garment data/samples/tryon/garment.jpg \
  --category upper --mock
```

## glTF Transform 压缩示例

```bash
gltf-transform inspect outputs/jobs/<job_id>/exports/glb/model.glb
gltf-transform draco \
  outputs/jobs/<job_id>/exports/glb/model.glb \
  outputs/jobs/<job_id>/exports/glb/model.draco.glb \
  --method edgebreaker
```
