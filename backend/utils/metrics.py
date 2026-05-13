"""指标统计工具。"""
from __future__ import annotations

import time
from pathlib import Path


def file_size_mb(path: str | Path) -> float:
    p = Path(path)
    if not p.exists() or not p.is_file():
        return 0.0
    return round(p.stat().st_size / (1024 * 1024), 3)


def dir_size_mb(path: str | Path) -> float:
    p = Path(path)
    if not p.exists() or not p.is_dir():
        return 0.0
    total = 0
    for sub in p.rglob("*"):
        if sub.is_file():
            total += sub.stat().st_size
    return round(total / (1024 * 1024), 3)


def compression_ratio(before_mb: float, after_mb: float) -> float:
    """压缩率 = 1 - after/before。值越大表示压缩越多。"""
    if before_mb <= 0:
        return 0.0
    return round(1.0 - (after_mb / before_mb), 4)


class Timer:
    """简易计时器，配合 with 使用。

        with Timer() as t:
            ...
        t.seconds
    """

    def __init__(self) -> None:
        self.start: float = 0.0
        self.end: float = 0.0
        self.seconds: float = 0.0

    def __enter__(self) -> "Timer":
        self.start = time.time()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.end = time.time()
        self.seconds = round(self.end - self.start, 3)
