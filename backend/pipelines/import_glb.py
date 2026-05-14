"""Direct GLB import pipeline.

This path is for merchant-supplied GLB files that do not need image-to-3D or
reconstruction. It normalizes the artifact layout to the same job directory
shape used by generated 3D assets, renders a thumbnail, and marks the job ready
for product listing.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .. import config
from ..job_store import job_store
from ..utils.metrics import Timer, file_size_mb


def _is_glb(path: Path) -> bool:
    if path.suffix.lower() != ".glb":
        return False
    try:
        with path.open("rb") as f:
            return f.read(4) == b"glTF"
    except OSError:
        return False


def _make_placeholder_thumbnail(target: Path, label: str = "GLB") -> None:
    try:
        from PIL import Image, ImageDraw

        target.parent.mkdir(parents=True, exist_ok=True)
        img = Image.new("RGB", (768, 768), (246, 247, 249))
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle((132, 218, 636, 550), radius=28, outline=(180, 190, 202), width=4)
        draw.text((336, 370), label[:12], fill=(70, 80, 96))
        img.save(target)
    except Exception:
        # Thumbnail is helpful but not required for the GLB to be usable.
        pass


def _render_thumbnail(glb_path: Path, target: Path, job_id: str) -> bool:
    script = config.PROJECT_ROOT / "scripts" / "render_glb_thumbnail_single.mjs"
    if not script.exists():
        job_store.append_log(job_id, "[import-glb] thumbnail script not found")
        return False

    cmd = [
        "node",
        str(script),
        "--src",
        str(glb_path),
        "--out",
        str(target),
    ]
    try:
        result = subprocess.run(
            cmd,
            cwd=str(config.PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
    except Exception as e:
        job_store.append_log(job_id, f"[import-glb] thumbnail render failed: {e}")
        return False

    if result.stdout.strip():
        job_store.append_log(job_id, result.stdout.strip())
    if result.stderr.strip():
        job_store.append_log(job_id, result.stderr.strip())
    if result.returncode != 0:
        job_store.append_log(job_id, f"[import-glb] thumbnail render exit={result.returncode}")
        return False
    return target.exists() and target.stat().st_size > 0


def run_import_glb_job(
    *,
    job_id: str,
    glb_path: str,
    thumbnail_path: str | None = None,
) -> dict:
    job_dir = config.OUTPUT_DIR / job_id
    glb = Path(glb_path)
    thumb = Path(thumbnail_path) if thumbnail_path else None
    final_thumb = job_dir / "thumbnail.png"

    with Timer() as timer:
        job_store.update_job(job_id, status="running", stage="post_process", progress=0.25)
        job_store.append_log(job_id, f"[import-glb] validating {glb.name}")

        if not glb.exists() or not _is_glb(glb):
            raise RuntimeError("上传文件不是有效的二进制 GLB")

        if thumb and thumb.exists() and thumb.stat().st_size > 0:
            final_thumb.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(thumb, final_thumb)
            job_store.append_log(job_id, "[import-glb] using uploaded thumbnail")
        else:
            job_store.update_job(job_id, stage="post_process", progress=0.55)
            ok = _render_thumbnail(glb, final_thumb, job_id)
            if not ok:
                _make_placeholder_thumbnail(final_thumb)

    preview_url = f"{config.STATIC_URL_PREFIX}/jobs/{job_id}/exports/glb/model.glb"
    thumbnail_abs = str(final_thumb) if final_thumb.exists() else None
    thumbnail_url = f"{config.STATIC_URL_PREFIX}/jobs/{job_id}/thumbnail.png" if thumbnail_abs else None
    glb_size = file_size_mb(glb)

    outputs = {
        "glb": str(glb),
        "preview_url": preview_url,
        "thumbnail": thumbnail_abs,
        "thumbnail_url": thumbnail_url,
        "provider": "manual-glb",
    }
    metrics = {
        "glb_size_mb": glb_size,
        "process_time_sec": timer.seconds,
    }
    job_store.update_job(
        job_id,
        status="success",
        stage="finished",
        progress=1.0,
        outputs=outputs,
        metrics=metrics,
    )
    job_store.append_log(job_id, f"[import-glb] done glb={glb_size:.2f}MB")
    return {"outputs": outputs, "metrics": metrics}
