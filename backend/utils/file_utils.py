"""文件相关工具：保存上传文件、生成 job_id、安全文件名等。"""
from __future__ import annotations

import hashlib
import re
import secrets
import shutil
from datetime import datetime
from pathlib import Path
from typing import Iterable

from fastapi import UploadFile


_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def generate_job_id(prefix: str = "") -> str:
    """生成形如 20260511_213000_abcd1234 的 job_id。"""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = secrets.token_hex(4)
    if prefix:
        return f"{ts}_{prefix}_{suffix}"
    return f"{ts}_{suffix}"


def safe_filename(name: str) -> str:
    """规范化文件名，避免路径穿越或非法字符。"""
    name = Path(name).name  # 仅保留文件名
    cleaned = _SAFE_NAME_RE.sub("_", name)
    return cleaned[:200] or "file"


async def save_upload_file(upload: UploadFile, target_dir: Path, filename: str | None = None) -> Path:
    """把 UploadFile 落盘到 target_dir 下，返回最终路径。"""
    target_dir.mkdir(parents=True, exist_ok=True)
    final_name = safe_filename(filename or upload.filename or "upload.bin")
    final_path = target_dir / final_name
    # 防止重名覆盖
    counter = 1
    while final_path.exists():
        stem, suffix = final_path.stem, final_path.suffix
        final_path = target_dir / f"{stem}_{counter}{suffix}"
        counter += 1
    with final_path.open("wb") as f:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)
    return final_path


def file_md5(path: Path, chunk_size: int = 1 << 20) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def list_files(directory: Path, extensions: Iterable[str] | None = None) -> list[Path]:
    if not directory.exists():
        return []
    results: list[Path] = []
    for p in sorted(directory.rglob("*")):
        if not p.is_file():
            continue
        if extensions is not None and p.suffix.lower() not in {e.lower() for e in extensions}:
            continue
        results.append(p)
    return results


def copy_to(src: Path, dst: Path) -> Path:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return dst
