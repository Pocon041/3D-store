"""Gradio 备选入口。

当 React 前端起不来时，可以用这个最小 UI 完成 demo。
"""
from __future__ import annotations

from pathlib import Path

import gradio as gr

from backend import config
from backend.job_store import job_store
from backend.pipelines.reconstruct import run_reconstruction_job
from backend.pipelines.tryon import run_tryon_job
from backend.utils.file_utils import generate_job_id


def _save_uploads_as_images(files, job_id: str) -> list[str]:
    images_dir = config.RAW_DIR / job_id / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    for f in files or []:
        src = Path(f.name) if hasattr(f, "name") else Path(str(f))
        dst = images_dir / src.name
        dst.write_bytes(src.read_bytes())
        paths.append(str(dst))
    return paths


def gradio_reconstruct(files, mode: str, quality: str, mock: bool):
    job_id = generate_job_id("recon")
    job_store.create_job(job_id, "reconstruct",
                         params={"mode": mode, "quality": quality, "mock": mock})
    if mode == "video":
        if not files:
            return job_id, "请上传一个视频", None
        src = Path(files[0].name)
        target_dir = config.RAW_DIR / job_id / "video"
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / src.name
        target.write_bytes(src.read_bytes())
        input_paths = [str(target)]
    else:
        input_paths = _save_uploads_as_images(files, job_id)
    try:
        run_reconstruction_job(job_id, input_paths, mode, quality=quality, export_glb=True, mock=mock)
    except Exception as e:
        return job_id, f"任务失败：{e}", None

    job = job_store.get_job(job_id)
    glb = job.outputs.optimized_glb or job.outputs.glb
    return job_id, f"任务完成：status={job.status}", glb


def gradio_tryon(person, garment, category: str, mock: bool):
    job_id = generate_job_id("tryon")
    job_store.create_job(job_id, "tryon", params={"category": category, "mock": mock})
    person_path = Path(person.name) if hasattr(person, "name") else Path(str(person))
    garment_path = Path(garment.name) if hasattr(garment, "name") else Path(str(garment))
    try:
        run_tryon_job(job_id, str(person_path), str(garment_path), category, mock)
    except Exception as e:
        return job_id, f"任务失败：{e}", None
    job = job_store.get_job(job_id)
    return job_id, f"任务完成：status={job.status}", job.outputs.tryon_result


def build_app() -> gr.Blocks:
    with gr.Blocks(title="AIGC 3D Commerce Demo") as demo:
        gr.Markdown("# AIGC 3D 商品工作台（Gradio 备选）")
        with gr.Tab("3D 重建"):
            with gr.Row():
                files = gr.Files(label="上传图片或视频")
                mode = gr.Radio(["images", "video"], value="images", label="输入模式")
            quality = gr.Radio(list(config.QUALITY_CONFIG.keys()), value="fast", label="质量档位")
            mock = gr.Checkbox(value=True, label="mock 模式")
            run_btn = gr.Button("开始重建", variant="primary")
            job_id_out = gr.Textbox(label="job_id")
            status_out = gr.Textbox(label="状态")
            model_out = gr.Model3D(label="3D 资产预览")
            run_btn.click(
                gradio_reconstruct,
                inputs=[files, mode, quality, mock],
                outputs=[job_id_out, status_out, model_out],
            )
        with gr.Tab("二维试穿"):
            person = gr.Image(label="人像图", type="filepath")
            garment = gr.Image(label="服装图", type="filepath")
            category = gr.Radio(["upper", "lower", "dress"], value="upper", label="类别")
            tryon_mock = gr.Checkbox(value=True, label="mock 模式")
            tryon_btn = gr.Button("生成试穿图", variant="primary")
            tryon_job = gr.Textbox(label="job_id")
            tryon_status = gr.Textbox(label="状态")
            tryon_result = gr.Image(label="结果")
            tryon_btn.click(
                gradio_tryon,
                inputs=[person, garment, category, tryon_mock],
                outputs=[tryon_job, tryon_status, tryon_result],
            )
    return demo


if __name__ == "__main__":
    config.ensure_runtime_dirs()
    build_app().launch()
