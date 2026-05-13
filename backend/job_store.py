"""任务存储：基于本地 JSON 文件的轻量 store，避免引入数据库。

每个任务对应 outputs/jobs/{job_id}/job.json
"""
from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from . import config
from .schemas import JobMetrics, JobOutputs, JobRecord


_LOCK = threading.RLock()


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _job_dir(job_id: str) -> Path:
    return config.OUTPUT_DIR / job_id


def _job_file(job_id: str) -> Path:
    return _job_dir(job_id) / "job.json"


def _log_file(job_id: str) -> Path:
    return _job_dir(job_id) / "job.log"


class JobStore:
    """简单的文件 JobStore。

    不追求高并发正确性，仅适合本地原型。
    """

    def __init__(self) -> None:
        config.ensure_runtime_dirs()

    # --------- 基础 CRUD ---------
    def create_job(
        self,
        job_id: str,
        task_type: str,
        params: dict[str, Any] | None = None,
    ) -> JobRecord:
        with _LOCK:
            now = _now_iso()
            record = JobRecord(
                job_id=job_id,
                task_type=task_type,  # type: ignore[arg-type]
                status="queued",
                stage="received",
                progress=0.0,
                created_at=now,
                updated_at=now,
                error=None,
                params=params or {},
                outputs=JobOutputs(),
                metrics=JobMetrics(),
                log_tail=[],
            )
            _job_dir(job_id).mkdir(parents=True, exist_ok=True)
            self._write(record)
            return record

    def get_job(self, job_id: str) -> Optional[JobRecord]:
        path = _job_file(job_id)
        if not path.exists():
            return None
        with _LOCK:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                return JobRecord.model_validate(data)
            except Exception:
                return None

    def update_job(self, job_id: str, **fields: Any) -> Optional[JobRecord]:
        with _LOCK:
            record = self.get_job(job_id)
            if record is None:
                return None
            data = record.model_dump()
            outputs_patch = fields.pop("outputs", None)
            metrics_patch = fields.pop("metrics", None)
            data.update(fields)
            if outputs_patch:
                data["outputs"].update({k: v for k, v in outputs_patch.items() if v is not None})
            if metrics_patch:
                data["metrics"].update({k: v for k, v in metrics_patch.items() if v is not None})
            data["updated_at"] = _now_iso()
            new_record = JobRecord.model_validate(data)
            self._write(new_record)
            return new_record

    def list_jobs(self) -> list[JobRecord]:
        if not config.OUTPUT_DIR.exists():
            return []
        records: list[JobRecord] = []
        for d in sorted(config.OUTPUT_DIR.iterdir(), reverse=True):
            if not d.is_dir():
                continue
            r = self.get_job(d.name)
            if r is not None:
                records.append(r)
        return records

    def append_log(self, job_id: str, line: str) -> None:
        log_path = _log_file(job_id)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with _LOCK:
            with log_path.open("a", encoding="utf-8") as f:
                f.write(line.rstrip("\n") + "\n")
            # 同时把最后 30 行追加到 log_tail 字段
            record = self.get_job(job_id)
            if record is None:
                return
            tail = record.log_tail + [line.rstrip("\n")]
            tail = tail[-30:]
            self.update_job(job_id, log_tail=tail)

    # --------- 内部 ---------
    def _write(self, record: JobRecord) -> None:
        path = _job_file(record.job_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(record.model_dump(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


# 全局单例
job_store = JobStore()
