"""FastAPI 入口。

- 提供 /api/health 健康检查
- 提供 /api/reconstruct 上传图片或视频触发 3D 重建
- 提供 /api/tryon 上传人像和服装图触发二维试穿
- 提供 /api/jobs 状态轮询
- 挂载 /static/jobs 静态目录用于 model-viewer 直接加载结果资产
"""
from __future__ import annotations

import json
import mimetypes
import threading
import traceback
from pathlib import Path
from typing import Optional

from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config, products
from .job_store import job_store
from .pipelines.image_to_3d import (
    list_providers,
    run_image_to_3d_job,
    run_image_to_3d_resume,
    run_multiview_to_3d_job,
)
from .pipelines.import_glb import run_import_glb_job
from .pipelines.reconstruct import run_reconstruction_job
from .pipelines.tryon import run_tryon_job
from .schemas import CreateJobResponse, HealthResponse
from .utils.file_utils import generate_job_id, save_upload_file


config.ensure_runtime_dirs()

# 启动横幅：把 Provider / Key 加载状态写到 stdout，便于在 logs/backend.log 一眼看到。
# tripo_configured 同时也通过 /api/image-to-3d/providers 暴露给前端。
print(
    "[image3d] provider={prov} tripo_key={tk} loaded_env_keys={ek}".format(
        prov=config.IMAGE3D_PROVIDER,
        tk="SET" if config.TRIPO_API_KEY else "MISSING",
        ek=",".join(config._LOADED_ENV_KEYS) or "(none)",
    ),
    flush=True,
)

# 注册 3D 资产的 MIME 类型，确保 model-viewer 能正确识别响应
mimetypes.add_type("model/gltf-binary", ".glb")
mimetypes.add_type("model/gltf+json", ".gltf")
mimetypes.add_type("application/octet-stream", ".ply")
mimetypes.add_type("application/octet-stream", ".splat")
mimetypes.add_type("application/octet-stream", ".obj")

app = FastAPI(title="AIGC 3D Commerce Demo", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态资源挂载
# /static/jobs -> outputs/jobs（资产文件）
app.mount(
    f"{config.STATIC_URL_PREFIX}/jobs",
    StaticFiles(directory=str(config.OUTPUT_DIR), check_dir=False),
    name="job-files",
)
# /static/samples -> data/samples
app.mount(
    f"{config.STATIC_URL_PREFIX}/samples",
    StaticFiles(directory=str(config.SAMPLES_DIR), check_dir=False),
    name="samples",
)
# /static/assets -> backend/static
_static_root = Path(__file__).resolve().parent / "static"
_static_root.mkdir(parents=True, exist_ok=True)
app.mount(
    f"{config.STATIC_URL_PREFIX}/assets",
    StaticFiles(directory=str(_static_root), check_dir=False),
    name="assets",
)


# --------------------- 后台任务封装 ---------------------
def _run_in_thread(target, *args, **kwargs) -> None:
    """把耗时任务丢到线程里执行，避免阻塞 uvicorn 事件循环。"""
    def _wrapper():
        job_id = kwargs.get("job_id") or (args[0] if args else None)
        try:
            target(*args, **kwargs)
        except Exception as e:
            tb = traceback.format_exc()
            if job_id:
                job_store.append_log(job_id, tb)
                job_store.update_job(job_id, status="failed", error=str(e))
    th = threading.Thread(target=_wrapper, daemon=True)
    th.start()


# --------------------- 路由 ---------------------
@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@app.get("/api/jobs")
def list_jobs(limit: int = 20):
    records = job_store.list_jobs()[:limit]
    return [r.model_dump() for r in records]


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    record = job_store.get_job(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="job not found")
    return record.model_dump()


@app.get("/api/jobs/{job_id}/files")
def list_job_files(job_id: str):
    job_dir = config.OUTPUT_DIR / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail="job not found")
    files = []
    for p in job_dir.rglob("*"):
        if p.is_file():
            rel = p.resolve().relative_to(config.OUTPUT_DIR.resolve())
            files.append({
                "name": p.name,
                "path": str(p),
                "url": f"{config.STATIC_URL_PREFIX}/jobs/{rel.as_posix()}",
                "size": p.stat().st_size,
            })
    return files


@app.get("/api/products")
def api_list_products(category: Optional[str] = None, q: Optional[str] = None):
    items = products.list_products()
    if category and category != "all":
        items = [p for p in items if p.get("category") == category]
    if q:
        items = products.search_products(items, q)
    return {"items": items, "categories": products.CATEGORIES}


@app.get("/api/products/{product_id}")
def api_get_product(product_id: str):
    p = products.get_product(product_id)
    if p is None:
        raise HTTPException(status_code=404, detail="product not found")
    return p


@app.delete("/api/products/{product_id}")
def api_delete_product(product_id: str):
    """删除用户自定义商品；内置 / Poly Haven 商品不可删除。"""
    p = products.get_product(product_id)
    if p is None:
        raise HTTPException(status_code=404, detail="product not found")
    if p.get("source") != "user":
        raise HTTPException(status_code=400, detail="only user products can be deleted")
    if not products.delete_user_product(product_id):
        raise HTTPException(status_code=404, detail="product not found")
    return {
        "deleted": True,
        "product_id": product_id,
        "job_id": p.get("job_id"),
    }


class PublishPayload(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = None
    category: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[list[str]] = None
    stock: Optional[int] = None


@app.post("/api/products/publish/{job_id}")
def api_publish_product(job_id: str, payload: Optional[PublishPayload] = None):
    """把 image_to_3d / reconstruct 成功的任务上架成正式商品。

    payload 字段全部可选；缺省时会用任务自带的默认值（自动标题、user-uploads 分类）。
    """
    body = payload or PublishPayload()
    product = products.publish_job_as_product(
        job_id,
        name=body.name,
        price=body.price,
        category=body.category,
        description=body.description,
        tags=body.tags,
        stock=body.stock,
    )
    if product is None:
        raise HTTPException(status_code=404, detail="job not found or not succeeded")
    return product


@app.get("/api/metrics/{job_id}")
def get_metrics(job_id: str):
    metrics_path = config.OUTPUT_DIR / job_id / "metrics.json"
    if not metrics_path.exists():
        raise HTTPException(status_code=404, detail="metrics not ready")
    return JSONResponse(content=json.loads(metrics_path.read_text(encoding="utf-8")))


@app.post("/api/reconstruct", response_model=CreateJobResponse)
async def create_reconstruct_job(
    files: list[UploadFile] = File(...),
    mode: str = Form("images"),
    quality: str = Form("balanced"),
    export_glb: bool = Form(True),
    mock: bool = Form(False),
) -> CreateJobResponse:
    if mode not in {"images", "video"}:
        raise HTTPException(status_code=400, detail="mode must be images or video")
    if quality not in config.QUALITY_CONFIG:
        raise HTTPException(status_code=400, detail=f"quality must be one of {list(config.QUALITY_CONFIG)}")

    job_id = generate_job_id("recon")
    raw_dir = config.RAW_DIR / job_id
    images_dir = raw_dir / "images"
    video_dir = raw_dir / "video"

    if mode == "video":
        if len(files) != 1:
            raise HTTPException(status_code=400, detail="video 模式只接受单个视频文件")
        suffix = Path(files[0].filename or "").suffix.lower()
        if suffix not in config.VIDEO_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"不支持的视频后缀：{suffix}")
        target = await save_upload_file(files[0], video_dir, filename=f"input{suffix}")
        input_paths = [str(target)]
    else:
        input_paths = []
        for f in files:
            suffix = Path(f.filename or "").suffix.lower()
            if suffix not in config.IMAGE_EXTENSIONS:
                continue
            saved = await save_upload_file(f, images_dir)
            input_paths.append(str(saved))
        if not input_paths:
            raise HTTPException(status_code=400, detail="未收到任何有效图片")

    job_store.create_job(
        job_id,
        "reconstruct",
        params={"mode": mode, "quality": quality, "export_glb": export_glb, "mock": mock},
    )

    _run_in_thread(
        run_reconstruction_job,
        job_id=job_id,
        input_paths=input_paths,
        input_mode=mode,
        quality=quality,
        export_glb=export_glb,
        mock=mock,
    )

    return CreateJobResponse(job_id=job_id, status="queued", message="Reconstruction job created.")


@app.post("/api/tryon", response_model=CreateJobResponse)
async def create_tryon_job(
    person_image: UploadFile = File(...),
    garment_image: UploadFile = File(...),
    category: str = Form("upper"),
    mock: bool = Form(False),
) -> CreateJobResponse:
    if category not in {"upper", "lower", "dress"}:
        raise HTTPException(status_code=400, detail="category must be upper / lower / dress")

    job_id = generate_job_id("tryon")
    job_store.create_job(job_id, "tryon", params={"category": category, "mock": mock})

    in_dir = config.OUTPUT_DIR / job_id / "tryon" / "_inputs"
    person_path = await save_upload_file(person_image, in_dir, filename=f"person{Path(person_image.filename or '').suffix or '.png'}")
    garment_path = await save_upload_file(garment_image, in_dir, filename=f"garment{Path(garment_image.filename or '').suffix or '.png'}")

    _run_in_thread(
        run_tryon_job,
        job_id=job_id,
        person_image_path=str(person_path),
        garment_image_path=str(garment_path),
        category=category,
        mock=mock,
    )

    return CreateJobResponse(job_id=job_id, status="queued", message="Try-on job created.")


@app.get("/api/tryon/capabilities")
def api_tryon_capabilities():
    catvton_python = Path(config.CATVTON_PYTHON)
    base_model = Path(config.CATVTON_BASE_MODEL_PATH)
    resume_path = Path(config.CATVTON_RESUME_PATH)
    ready = (
        config.CATVTON_DIR.exists()
        and catvton_python.exists()
        and base_model.exists()
        and resume_path.exists()
    )
    return {
        "ready": ready,
        "default_mock": not ready,
        "catvton_dir": str(config.CATVTON_DIR),
        "catvton_python": str(catvton_python),
        "base_model_path": str(config.CATVTON_BASE_MODEL_PATH),
        "resume_path": str(config.CATVTON_RESUME_PATH),
        "width": config.CATVTON_WIDTH,
        "height": config.CATVTON_HEIGHT,
        "steps": config.CATVTON_STEPS,
    }


@app.get("/api/image-to-3d/providers")
def api_image_to_3d_providers():
    """前端发现可用的图生 3D Provider；同时返回当前默认值。"""
    return {
        "default": config.IMAGE3D_PROVIDER,
        "available": list_providers(),
        "tripo_configured": bool(config.TRIPO_API_KEY),
    }


@app.post("/api/import-glb", response_model=CreateJobResponse)
async def create_import_glb_job(
    model: UploadFile = File(...),
    thumbnail: Optional[UploadFile] = File(None),
    name: Optional[str] = Form(None),
    price: Optional[float] = Form(0.0),
    stock: Optional[int] = Form(1),
    category: str = Form("apparel"),
    garment_slot: str = Form("upper"),
) -> CreateJobResponse:
    """直接导入商家已有 GLB，并自动上架为商品。

    产物布局与 image_to_3d/reconstruct 保持一致：
    outputs/jobs/<job_id>/exports/glb/model.glb + thumbnail.png。
    """
    suffix = Path(model.filename or "").suffix.lower()
    if suffix != ".glb":
        raise HTTPException(status_code=400, detail="只支持上传 .glb 二进制模型")
    if garment_slot not in {"upper", "lower", "full", "shoes"}:
        raise HTTPException(status_code=400, detail="garment_slot must be upper / lower / full / shoes")

    job_id = generate_job_id("glb")
    glb_dir = config.OUTPUT_DIR / job_id / "exports" / "glb"
    glb_path = await save_upload_file(model, glb_dir, filename="model.glb")

    thumb_path = None
    if thumbnail is not None and thumbnail.filename:
        thumb_suffix = Path(thumbnail.filename or "").suffix.lower() or ".png"
        if thumb_suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
            raise HTTPException(status_code=400, detail="thumbnail must be png / jpg / jpeg / webp")
        thumb_path = await save_upload_file(
            thumbnail,
            config.OUTPUT_DIR / job_id / "_input",
            filename=f"thumbnail{thumb_suffix}",
        )

    display_name = (name or Path(model.filename or "Imported GLB").stem).strip()
    job_store.create_job(
        job_id,
        "image_to_3d",
        params={
            "kind": "import_glb",
            "provider": "manual-glb",
            "filename": model.filename,
            "published": True,
            "product_name": display_name,
            "product_category": category or "apparel",
            "product_price": float(price or 0.0),
            "product_stock": int(stock or 1),
            "product_license": "Merchant Upload",
            "product_tags": ["GLB", "3D", "服装", garment_slot],
            "garment_slot": garment_slot,
            "product_tryonable": (category or "apparel") == "apparel",
        },
    )

    _run_in_thread(
        run_import_glb_job,
        job_id=job_id,
        glb_path=str(glb_path),
        thumbnail_path=str(thumb_path) if thumb_path else None,
    )

    return CreateJobResponse(job_id=job_id, status="queued", message="GLB import job created.")


@app.post("/api/image-to-3d", response_model=CreateJobResponse)
async def create_image_to_3d_job(
    image: UploadFile = File(...),
    provider: Optional[str] = Form(None),
) -> CreateJobResponse:
    """单图生成 3D 模型。

    - image: 单张图片（jpg/png/webp/bmp）
    - provider: 覆盖默认 provider；不传则用 IMAGE3D_PROVIDER 环境变量
    """
    suffix = Path(image.filename or "").suffix.lower()
    if suffix not in config.IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的图片格式 {suffix}；允许：{sorted(config.IMAGE_EXTENSIONS)}",
        )

    job_id = generate_job_id("img3d")
    in_dir = config.OUTPUT_DIR / job_id / "_input"
    image_path = await save_upload_file(image, in_dir, filename=f"source{suffix}")

    job_store.create_job(
        job_id,
        "image_to_3d",
        params={"provider": provider or config.IMAGE3D_PROVIDER, "filename": image.filename},
    )

    _run_in_thread(
        run_image_to_3d_job,
        job_id=job_id,
        image_path=str(image_path),
        provider_name=provider,
    )

    return CreateJobResponse(
        job_id=job_id,
        status="queued",
        message=f"Image-to-3D job created (provider={provider or config.IMAGE3D_PROVIDER}).",
    )


@app.post("/api/multiview-to-3d", response_model=CreateJobResponse)
async def create_multiview_to_3d_job(
    images: list[UploadFile] = File(...),
    provider: Optional[str] = Form(None),
) -> CreateJobResponse:
    """多视角图生 3D：传 1-4 张视图，按 [front, back, left, right] 顺序。"""
    if not images:
        raise HTTPException(status_code=400, detail="至少需要 1 张图片")
    if len(images) > 4:
        raise HTTPException(status_code=400, detail="最多支持 4 张视图")
    for img in images:
        suffix = Path(img.filename or "").suffix.lower()
        if suffix not in config.IMAGE_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的图片格式 {suffix}；允许：{sorted(config.IMAGE_EXTENSIONS)}",
            )

    job_id = generate_job_id("mv3d")
    in_dir = config.OUTPUT_DIR / job_id / "_input"
    saved: list[str] = []
    for i, img in enumerate(images):
        suffix = Path(img.filename or "").suffix.lower() or ".png"
        # 按视图位置命名：v0_front / v1_back / v2_left / v3_right
        view_names = ["v0_front", "v1_back", "v2_left", "v3_right"]
        view_name = view_names[i] if i < len(view_names) else f"v{i}"
        p = await save_upload_file(img, in_dir, filename=f"{view_name}{suffix}")
        saved.append(str(p))

    job_store.create_job(
        job_id,
        "image_to_3d",  # 复用同一任务类型，前端可通过 params.kind 区分
        params={
            "provider": provider or config.IMAGE3D_PROVIDER,
            "kind": "multiview",
            "num_views": len(saved),
        },
    )

    _run_in_thread(
        run_multiview_to_3d_job,
        job_id=job_id,
        image_paths=saved,
        provider_name=provider,
    )

    return CreateJobResponse(
        job_id=job_id,
        status="queued",
        message=f"Multi-view to 3D job created with {len(saved)} views (provider={provider or config.IMAGE3D_PROVIDER}).",
    )


class ResumeTripoPayload(BaseModel):
    tripo_task_id: str


@app.post("/api/image-to-3d/resume", response_model=CreateJobResponse)
def api_image_to_3d_resume(payload: ResumeTripoPayload) -> CreateJobResponse:
    """从已存在的 Tripo task_id 拉产物，避免因网络瞬时错误被 fallback 而重复扣费。"""
    if not config.TRIPO_API_KEY:
        raise HTTPException(
            status_code=400, detail="需要先配置 TRIPO_API_KEY 才能 resume Tripo 任务"
        )
    job_id = generate_job_id("img3d-resume")
    job_store.create_job(
        job_id,
        "image_to_3d",
        params={"provider": "tripo", "resumed_from": payload.tripo_task_id},
    )
    _run_in_thread(
        run_image_to_3d_resume,
        job_id=job_id,
        tripo_task_id=payload.tripo_task_id,
    )
    return CreateJobResponse(
        job_id=job_id,
        status="queued",
        message=f"Resume from tripo task {payload.tripo_task_id}.",
    )


@app.get("/")
def root():
    return {
        "name": "AIGC 3D Commerce Demo Backend",
        "endpoints": [
            "/api/health",
            "/api/products",
            "/api/products/{product_id}",
            "/api/reconstruct",
            "/api/tryon",
            "/api/tryon/capabilities",
            "/api/image-to-3d",
            "/api/image-to-3d/providers",
            "/api/image-to-3d/resume",
            "/api/import-glb",
            "/api/multiview-to-3d",
            "/api/jobs",
            "/api/jobs/{job_id}",
            "/api/jobs/{job_id}/files",
            "/api/metrics/{job_id}",
            "/static/jobs/...",
        ],
    }


@app.get("/viewer")
def viewer_page():
    """直接返回 model-viewer 静态页面，方便没有跑前端时也能看效果。"""
    page = _static_root / "viewer.html"
    if not page.exists():
        raise HTTPException(status_code=404, detail="viewer page not found")
    return FileResponse(page)
