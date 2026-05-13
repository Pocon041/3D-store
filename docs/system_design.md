# 系统设计

## 模块边界

```
+-----------------------------+        +-----------------------------+
|  React Frontend (Vite)      |  HTTP  |  FastAPI Backend            |
|  - Upload3D / TryOnPanel    +<------>+  - /api/reconstruct         |
|  - JobStatus / ModelViewer  |        |  - /api/tryon               |
|  - MetricsTable             |        |  - /api/jobs                |
+-----------------------------+        +--------------+--------------+
                                                      |
                              +-----------------------+----------------------+
                              |                       |                      |
                       (subprocess)            (subprocess)            (file IO)
                              |                       |                      |
                      Nerfstudio CLI            CatVTON Python         JobStore (json)
                       ns-process-data            inference.py
                       ns-train splatfacto
                       ns-export
                              |
                              v
                       Blender / glTF Transform
                       (OBJ -> GLB -> Draco)
```

## 重建管线状态机

```
received -> extract_frames? -> prepare_images -> ns_process_data ->
train_splatfacto -> export_gaussian_splat -> export_mesh -> convert_glb -> optimize_glb -> finished
```

mock 模式下跳到 `convert_glb` 直接复制示例 GLB。

## 关键决策

1. **不引入数据库 / 队列**：本地原型，使用 `outputs/jobs/{job_id}/job.json` 即可。
2. **任务在线程中跑**：FastAPI BackgroundTasks 会阻塞响应链路；这里用 daemon 线程，避免影响前端轮询。
3. **mock 优先**：方案明确指出第一优先级是 mock 全链路跑通。无 GPU / 未装 Nerfstudio 仍可演示。
4. **静态资源直接挂载**：`/static/jobs/...` 直接指向 outputs/jobs，便于 model-viewer 加载。
5. **命令集中在 `config.py`**：所有可能因环境变化的命令模板都放这里，不散落到各管线文件。

## 已知风险

- `splatfacto` 训练耗时高（10 分钟到几小时不等），前端轮询要支持长任务。
- `ns-export poisson` 的 mesh 质量不稳定，方案要求允许 splat / glb 两条展示路径。
- Windows 下 Blender / COLMAP 需要手动安装；缺工具时通过 `ALLOW_MISSING_TOOLS_FALLBACK_TO_MOCK` 自动降级。
