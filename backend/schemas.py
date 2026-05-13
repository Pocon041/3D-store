"""Pydantic 数据模型。

集中管理 API 的请求/响应结构与任务状态枚举。
"""
from __future__ import annotations

from typing import Any, Literal, Optional
from pydantic import BaseModel, Field


JobStatus = Literal["queued", "running", "success", "failed"]
TaskType = Literal["reconstruct", "tryon", "image_to_3d"]

ReconstructStage = Literal[
    "received",
    "extract_frames",
    "prepare_images",
    "ns_process_data",
    "train_splatfacto",
    "export_gaussian_splat",
    "export_mesh",
    "convert_glb",
    "optimize_glb",
    "finished",
]

TryOnStage = Literal[
    "received",
    "prepare_inputs",
    "run_catvton",
    "save_result",
    "finished",
]

ImageTo3DStage = Literal[
    "received",
    "validate_image",
    "upload_to_provider",
    "submit_task",
    "polling",
    "download_glb",
    "post_process",
    "finished",
]


class JobOutputs(BaseModel):
    processed_data_dir: Optional[str] = None
    config_yml: Optional[str] = None
    ply: Optional[str] = None
    splat: Optional[str] = None
    obj: Optional[str] = None
    glb: Optional[str] = None
    optimized_glb: Optional[str] = None
    preview_url: Optional[str] = None
    tryon_result: Optional[str] = None
    tryon_compare: Optional[str] = None
    tryon_person: Optional[str] = None
    tryon_garment: Optional[str] = None
    # 图生 3D 专有字段
    source_image: Optional[str] = None
    thumbnail: Optional[str] = None
    provider: Optional[str] = None
    provider_task_id: Optional[str] = None


class JobMetrics(BaseModel):
    num_input_files: Optional[int] = None
    raw_size_mb: Optional[float] = None
    process_time_sec: Optional[float] = None
    train_time_sec: Optional[float] = None
    export_time_sec: Optional[float] = None
    convert_time_sec: Optional[float] = None
    optimize_time_sec: Optional[float] = None
    splat_size_mb: Optional[float] = None
    obj_size_mb: Optional[float] = None
    glb_size_mb: Optional[float] = None
    optimized_glb_size_mb: Optional[float] = None
    compression_ratio: Optional[float] = None


class JobRecord(BaseModel):
    """job.json 的内存模型。"""
    job_id: str
    task_type: TaskType
    status: JobStatus = "queued"
    stage: Optional[str] = None
    progress: float = 0.0
    created_at: str
    updated_at: str
    error: Optional[str] = None
    params: dict[str, Any] = Field(default_factory=dict)
    outputs: JobOutputs = Field(default_factory=JobOutputs)
    metrics: JobMetrics = Field(default_factory=JobMetrics)
    log_tail: list[str] = Field(default_factory=list)


class CreateJobResponse(BaseModel):
    job_id: str
    status: JobStatus
    message: str


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"
