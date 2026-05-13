"""输入图片简单筛选。

仅做最小可用：扩展名筛选、最小尺寸过滤、可选模糊度过滤。
更复杂的图像检索/聚类暂不实现。
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from .. import config


def filter_image_files(
    files: list[Path],
    min_size_kb: int = 5,
    deduplicate_by_name: bool = True,
) -> list[Path]:
    """根据扩展名和最小大小筛选图片文件。"""
    seen: set[str] = set()
    results: list[Path] = []
    for p in files:
        if p.suffix.lower() not in config.IMAGE_EXTENSIONS:
            continue
        try:
            size_kb = p.stat().st_size / 1024
        except FileNotFoundError:
            continue
        if size_kb < min_size_kb:
            continue
        key = p.name if deduplicate_by_name else str(p)
        if key in seen:
            continue
        seen.add(key)
        results.append(p)
    return results


def laplacian_blur_score(path: Path) -> Optional[float]:
    """返回 Laplacian 方差，越小越模糊。OpenCV 不可用时返回 None。"""
    try:
        import cv2  # type: ignore
        import numpy as np  # noqa: F401
    except Exception:
        return None
    img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return None
    return float(cv2.Laplacian(img, cv2.CV_64F).var())


def filter_blurry_images(
    files: list[Path],
    threshold: Optional[float] = None,
) -> tuple[list[Path], list[Path]]:
    """按 Laplacian 方差过滤模糊图片，返回 (清晰列表, 被过滤的模糊列表)。

    OpenCV 不可用时不执行过滤，全部视为清晰。
    """
    threshold = threshold if threshold is not None else config.BLUR_VAR_THRESHOLD
    sharp: list[Path] = []
    blurry: list[Path] = []
    for p in files:
        score = laplacian_blur_score(p)
        if score is None:
            sharp.append(p)
            continue
        if score < threshold:
            blurry.append(p)
        else:
            sharp.append(p)
    return sharp, blurry
