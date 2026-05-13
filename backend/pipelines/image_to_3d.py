"""图生 3D 管线 (Image -> 3D Model)。

设计原则
---------
1. **Provider 抽象**：把"上传图片 -> 排队 -> 拿到 GLB"封装成可插拔接口；
   默认 mock provider 保证无 API key 也能跑通 UX 全流程。
2. **统一产物布局**：每个任务输出到 `outputs/jobs/<job_id>/exports/glb/model.glb`，
   缩略图固定为 `<job_id>/thumbnail.png`，跟现有的重建/试穿任务对齐，
   前端可以复用 `JobStatus` 组件而不用做特殊处理。
3. **真实 Provider 失败时降级**：调用 Tripo/混元等真实 API 出错时，自动落到
   mock 上，保证 demo 永远有产物可看；日志会标明 fallback 原因。

接入新 Provider 的步骤
----------------------
1. 继承 `Image3DProvider`，实现 `generate(image_path, job_id) -> ProviderResult`
2. 在 `get_provider()` 的工厂里注册即可
3. 在 `backend/config.py` 加好对应的 env var

环境变量
--------
- IMAGE3D_PROVIDER = mock | tripo | hunyuan | meshy   （未设置或非法值 -> mock）
- TRIPO_API_KEY    Tripo3D 的 Bearer Token（去 platform.tripo3d.ai 创建）
- IMAGE3D_POLL_INTERVAL_SEC / IMAGE3D_POLL_TIMEOUT_SEC 控制真实 provider 的轮询节奏
"""
from __future__ import annotations

import json
import shutil
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from .. import config
from ..job_store import job_store
from ..utils.metrics import Timer, file_size_mb
from . import mock_pipeline


# ---------------------------------------------------------------------------
# 结果数据类
# ---------------------------------------------------------------------------
@dataclass
class ProviderResult:
    """Provider 完成一次生成后返回的内容。

    所有 provider 都必须把 GLB 落到 `glb_path`，其余字段可选。
    """
    glb_path: Path
    thumbnail_path: Optional[Path] = None
    provider: str = "mock"
    provider_task_id: Optional[str] = None
    extra: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 抽象基类
# ---------------------------------------------------------------------------
class Image3DProvider(ABC):
    """所有图生 3D Provider 的基类。

    子类至少要实现 `generate`（单图 → 3D）；如果支持多视角输入，再覆盖
    `generate_multiview`，否则会自动 fallback 到单图模式（取第一张图）。
    """

    name: str = "base"

    @abstractmethod
    def generate(
        self,
        image_path: Path,
        job_dir: Path,
        report: Callable[..., None],
    ) -> ProviderResult:
        """同步执行一次生成。

        Args:
            image_path: 已经保存到磁盘的输入图（绝对路径）
            job_dir:    本任务的 outputs 目录，子类可往里写中间文件
            report:     形如 `report(stage=..., progress=..., log=...)` 的回调

        Returns:
            ProviderResult，至少包含可加载的 GLB 路径
        """
        raise NotImplementedError

    def generate_multiview(
        self,
        image_paths: list[Path],
        job_dir: Path,
        report: Callable[..., None],
    ) -> ProviderResult:
        """多视角生成。默认实现：只取第一张图调单图 generate。"""
        if not image_paths:
            raise ValueError("multiview 需要至少 1 张图")
        report(log=f"[{self.name}] provider 不支持原生 multiview，使用第一张图作单图生成")
        return self.generate(image_paths[0], job_dir, report)


# ---------------------------------------------------------------------------
# Mock Provider：复用现有 mock_pipeline 的占位 GLB
# ---------------------------------------------------------------------------
class MockImage3DProvider(Image3DProvider):
    """无外部依赖的占位 Provider。

    生成一个简单立方体 GLB 充当模型；把源图缩成 256 当缩略图，让卡片看
    起来跟用户上传的图相关，而不是千篇一律的纯文字占位。
    """

    name = "mock"

    def generate(self, image_path, job_dir, report) -> ProviderResult:
        glb_dir = job_dir / "exports" / "glb"
        glb_dir.mkdir(parents=True, exist_ok=True)
        glb_target = glb_dir / "model.glb"

        report(stage="upload_to_provider", progress=0.2, log="[mock] skip real upload")
        time.sleep(0.1)

        report(stage="submit_task", progress=0.35, log="[mock] generate cube glb")
        sample = mock_pipeline._ensure_sample_glb()  # noqa: SLF001 复用内部工具
        if sample is None:
            raise RuntimeError("无法生成 mock GLB；请安装 trimesh")
        shutil.copy2(sample, glb_target)

        report(stage="polling", progress=0.6, log="[mock] simulate polling")
        time.sleep(0.2)

        report(stage="download_glb", progress=0.85, log="[mock] glb ready")

        # 缩略图：尽量用用户上传的图，让 mock 也有视觉关联
        thumb_path = job_dir / "thumbnail.png"
        if not _try_make_thumb_from_image(image_path, thumb_path):
            mock_pipeline._try_generate_thumbnail(thumb_path, label="image2 3d")  # noqa: SLF001

        return ProviderResult(
            glb_path=glb_target,
            thumbnail_path=thumb_path if thumb_path.exists() else None,
            provider=self.name,
        )


# ---------------------------------------------------------------------------
# Tripo3D Provider
# ---------------------------------------------------------------------------
class TripoImage3DProvider(Image3DProvider):
    """接入 Tripo3D 公开 API: https://platform.tripo3d.ai/docs/

    流程（按官方文档）：
    1. POST /upload  multipart=file -> file_token
    2. POST /task     body={"type":"image_to_model","file":{...},"model_version":...} -> task_id
    3. GET  /task/{task_id}  轮询，直到 status=success / failed
    4. 下载 success 响应里的 model.pbr_model.url 拿到 GLB
    """

    name = "tripo"

    def __init__(self) -> None:
        if not config.TRIPO_API_KEY:
            raise RuntimeError(
                "Tripo provider 需要 TRIPO_API_KEY；请在环境变量里配置"
            )
        # 延迟导入 requests，让 mock 模式可以不装这个包（虽然 requirements 已加）
        import requests  # noqa: WPS433

        self._requests = requests
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {config.TRIPO_API_KEY}",
        })

    @staticmethod
    def _raise_tripo_error(resp) -> None:
        """把 Tripo 的业务错误码翻译成可读消息。"""
        try:
            body = resp.json()
        except Exception:
            resp.raise_for_status()
            return
        code = body.get("code")
        msg = body.get("message") or body.get("suggestion") or str(body)
        if resp.status_code == 403 and code == 2010:
            raise RuntimeError(
                "Tripo3D 余额不足：请到 platform.tripo3d.ai 充值后再用真实 provider，"
                "当前会自动降级到 mock。"
            )
        if resp.status_code == 401:
            raise RuntimeError("Tripo3D 鉴权失败：TRIPO_API_KEY 无效或被撤销")
        if code and code != 0:
            raise RuntimeError(f"Tripo3D 业务错误 code={code}: {msg}")
        resp.raise_for_status()

    def _upload(self, image_path: Path) -> str:
        url = f"{config.TRIPO_API_BASE}/upload"
        with image_path.open("rb") as f:
            files = {"file": (image_path.name, f, _guess_mime(image_path.suffix))}
            r = self._session.post(url, files=files, timeout=60)
        if r.status_code >= 400:
            self._raise_tripo_error(r)
        body = r.json()
        # Tripo 返回 {"code":0, "data":{"image_token":"xxx"}}
        data = body.get("data") or body
        token = data.get("image_token") or data.get("file_token") or data.get("token")
        if not token:
            raise RuntimeError(f"Tripo upload 返回无 token: {body}")
        return token

    def _create_task(self, file_token: str, suffix: str) -> str:
        """创建 image_to_model 任务。

        参考官方 SDK 实现（tripo-python-sdk）：file.type 永远是 "jpg"，且默认
        不传 model_version 让服务端自行选择，避免某些 tier key 不支持指定版本。
        """
        url = f"{config.TRIPO_API_BASE}/task"
        payload: dict[str, Any] = {
            "type": "image_to_model",
            "file": {
                "type": "jpg",  # SDK 也是写死 jpg，服务端按 content sniffing
                "file_token": file_token,
            },
        }
        # 只有用户显式覆盖了默认 model_version 才传，避免触发 tier 限制
        if (
            config.TRIPO_MODEL_VERSION
            and config.TRIPO_MODEL_VERSION.lower() not in {"auto", "default", ""}
        ):
            payload["model_version"] = config.TRIPO_MODEL_VERSION

        r = self._session.post(url, json=payload, timeout=30)
        if r.status_code >= 400:
            self._raise_tripo_error(r)
        body = r.json()
        data = body.get("data") or body
        task_id = data.get("task_id") or data.get("id")
        if not task_id:
            raise RuntimeError(f"Tripo task 创建失败: {body}")
        return str(task_id)

    def _poll(self, task_id: str, report: Callable[..., None]) -> dict[str, Any]:
        """轮询任务状态，瞬时 5xx / 网络错误自动重试。

        Tripo 服务端偶尔会在网关层返回 502/503/504（特别是任务运行中），
        如果直接抛错会让明明已经在生成的任务被白白放弃。这里采用：
        - 单次响应 5xx / 网络异常 -> 记日志后等下一个 poll 周期重试
        - 连续 max_transient_errors 次失败才放弃，触发上层 fallback
        - 总超时仍由 IMAGE3D_POLL_TIMEOUT_SEC 控制（默认 5 分钟）
        """
        url = f"{config.TRIPO_API_BASE}/task/{task_id}"
        deadline = time.monotonic() + config.IMAGE3D_POLL_TIMEOUT_SEC
        max_transient_errors = 8
        transient_errors = 0
        last_progress = -1
        from requests.exceptions import RequestException  # 局部 import，避免 mock 模式依赖

        while time.monotonic() < deadline:
            try:
                r = self._session.get(url, timeout=30)
                if 500 <= r.status_code < 600:
                    transient_errors += 1
                    report(log=f"[tripo] transient {r.status_code} on poll "
                           f"({transient_errors}/{max_transient_errors})，{config.IMAGE3D_POLL_INTERVAL_SEC}s 后重试")
                    if transient_errors >= max_transient_errors:
                        raise RuntimeError(
                            f"Tripo task {task_id} 轮询连续 {max_transient_errors} 次 5xx，放弃"
                        )
                    time.sleep(config.IMAGE3D_POLL_INTERVAL_SEC)
                    continue
                if r.status_code >= 400:
                    self._raise_tripo_error(r)
            except RequestException as e:
                # 连接重置、DNS 抖动等
                transient_errors += 1
                report(log=f"[tripo] poll network error ({transient_errors}/{max_transient_errors}): {e}")
                if transient_errors >= max_transient_errors:
                    raise RuntimeError(f"Tripo task {task_id} 轮询连续网络失败：{e}") from e
                time.sleep(config.IMAGE3D_POLL_INTERVAL_SEC)
                continue

            # 成功响应 -> 重置瞬时错误计数
            transient_errors = 0
            body = r.json()
            data = body.get("data") or body
            status = (data.get("status") or "").lower()
            progress = float(data.get("progress") or 0) / 100.0
            # 进度无变化时少刷日志
            progress_pct = int(progress * 100)
            if progress_pct != last_progress or status not in {"queued", "running"}:
                report(
                    stage="polling",
                    progress=0.4 + min(progress, 1.0) * 0.5,
                    log=f"[tripo] status={status} progress={progress:.0%}",
                )
                last_progress = progress_pct
            if status in {"success", "completed", "succeed"}:
                return data
            if status in {"failed", "cancelled", "error"}:
                raise RuntimeError(f"Tripo task 失败: {data.get('error') or data}")
            time.sleep(config.IMAGE3D_POLL_INTERVAL_SEC)
        raise TimeoutError(f"Tripo task {task_id} 轮询超时 ({config.IMAGE3D_POLL_TIMEOUT_SEC}s)")

    def _download_glb(self, glb_url: str, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        with self._session.get(glb_url, stream=True, timeout=120) as r:
            r.raise_for_status()
            with target.open("wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 20):
                    if chunk:
                        f.write(chunk)

    # ------ 公开的轮询入口，便于从已有 task_id 拉产物 ------
    def fetch_existing_task(self, task_id: str, job_dir: Path, report: Callable[..., Any]) -> "ProviderResult":
        """复用已经在 Tripo 上完成 / 进行中的 task，避免重复扣费。"""
        report(stage="polling", progress=0.4, log=f"[tripo] resuming task {task_id}")
        data = self._poll(task_id, report)
        return self._finalize_result(data, task_id, job_dir, source_image=None, report=report)

    def _finalize_result(
        self,
        data: dict,
        task_id: str,
        job_dir: Path,
        source_image: Optional[Path],
        report: Callable[..., Any],
    ) -> "ProviderResult":
        glb_url = (
            (data.get("output") or {}).get("pbr_model")
            or (data.get("output") or {}).get("model")
            or (data.get("model") or {}).get("pbr_model_url")
            or (data.get("result") or {}).get("pbr_model_url")
            or data.get("pbr_model_url")
            or data.get("model_url")
        )
        if not glb_url:
            raise RuntimeError(f"Tripo 成功但找不到 GLB url，原始 output={data.get('output')}")

        glb_target = job_dir / "exports" / "glb" / "model.glb"
        report(stage="download_glb", progress=0.92, log=f"[tripo] downloading GLB ...")
        self._download_glb(glb_url, glb_target)

        # 缩略图：优先 Tripo 渲染图，否则源图缩略
        thumb_path = job_dir / "thumbnail.png"
        rendered = (data.get("output") or {}).get("rendered_image")
        if rendered:
            try:
                self._download_to(rendered, thumb_path)
            except Exception:
                if source_image is not None:
                    _try_make_thumb_from_image(source_image, thumb_path)
        elif source_image is not None:
            _try_make_thumb_from_image(source_image, thumb_path)

        return ProviderResult(
            glb_path=glb_target,
            thumbnail_path=thumb_path if thumb_path.exists() else None,
            provider=self.name,
            provider_task_id=task_id,
            extra={"glb_url": glb_url},
        )

    def _download_to(self, url: str, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        with self._session.get(url, stream=True, timeout=60) as r:
            r.raise_for_status()
            with target.open("wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 18):
                    if chunk:
                        f.write(chunk)

    def generate(self, image_path, job_dir, report) -> ProviderResult:
        report(stage="upload_to_provider", progress=0.1, log="[tripo] uploading image ...")
        token = self._upload(image_path)

        report(stage="submit_task", progress=0.25,
               log=f"[tripo] submitting task (model={config.TRIPO_MODEL_VERSION}) ...")
        task_id = self._create_task(token, image_path.suffix)
        report(log=f"[tripo] task_id={task_id}")

        data = self._poll(task_id, report)
        return self._finalize_result(data, task_id, job_dir, source_image=image_path, report=report)

    # ---- multiview_to_model ----
    def _create_multiview_task(self, file_tokens: list[Optional[str]]) -> str:
        """对应 SDK 的 multiview_to_model：files 是数组，按 [front, back, left, right]。

        SDK 源码中空槽传 `{}`，有图槽传 `{"type":"jpg","file_token":"..."}`。
        """
        files_payload: list[dict[str, Any]] = []
        for tok in file_tokens:
            if tok is None:
                files_payload.append({})
            else:
                files_payload.append({"type": "jpg", "file_token": tok})
        payload: dict[str, Any] = {
            "type": "multiview_to_model",
            "files": files_payload,
        }
        if (
            config.TRIPO_MODEL_VERSION
            and config.TRIPO_MODEL_VERSION.lower() not in {"auto", "default", ""}
        ):
            payload["model_version"] = config.TRIPO_MODEL_VERSION

        url = f"{config.TRIPO_API_BASE}/task"
        r = self._session.post(url, json=payload, timeout=30)
        if r.status_code >= 400:
            self._raise_tripo_error(r)
        body = r.json()
        data = body.get("data") or body
        task_id = data.get("task_id") or data.get("id")
        if not task_id:
            raise RuntimeError(f"Tripo multiview_to_model 创建失败: {body}")
        return str(task_id)

    def generate_multiview(self, image_paths, job_dir, report) -> ProviderResult:
        if not image_paths:
            raise ValueError("multiview 需要至少 1 张图")
        # Tripo 多视角最多 4 张
        if len(image_paths) > 4:
            report(log=f"[tripo] 收到 {len(image_paths)} 张图，多余的会被忽略，仅前 4 张参与生成")
            image_paths = image_paths[:4]

        report(stage="upload_to_provider", progress=0.1,
               log=f"[tripo] uploading {len(image_paths)} images ...")
        # 顺序上传（避免并发冲突；4 张图不会很慢）
        tokens: list[Optional[str]] = []
        for i, p in enumerate(image_paths):
            if p is None:
                tokens.append(None)
                continue
            tok = self._upload(p)
            tokens.append(tok)
            report(progress=0.1 + (i + 1) * 0.04,
                   log=f"[tripo] uploaded view {i+1}/{len(image_paths)} token={tok[:8]}...")

        # 不足 4 槽时补 None；Tripo API 接受 1..4 槽数
        while len(tokens) < len(image_paths):
            tokens.append(None)

        report(stage="submit_task", progress=0.3,
               log=f"[tripo] submitting multiview_to_model with {sum(1 for t in tokens if t)} views ...")
        task_id = self._create_multiview_task(tokens)
        report(log=f"[tripo] multiview task_id={task_id}")

        data = self._poll(task_id, report)
        # 缩略图用第一张图
        return self._finalize_result(
            data, task_id, job_dir,
            source_image=image_paths[0] if image_paths else None,
            report=report,
        )


# ---------------------------------------------------------------------------
# 工厂
# ---------------------------------------------------------------------------
_PROVIDERS: dict[str, type[Image3DProvider]] = {
    "mock": MockImage3DProvider,
    "tripo": TripoImage3DProvider,
    # "hunyuan": HunyuanImage3DProvider,   # TODO
    # "meshy": MeshyImage3DProvider,        # TODO
}


def get_provider(name: Optional[str] = None) -> Image3DProvider:
    key = (name or config.IMAGE3D_PROVIDER or "mock").lower()
    cls = _PROVIDERS.get(key)
    if cls is None:
        cls = MockImage3DProvider
    try:
        return cls()
    except Exception as e:
        # 真实 provider 初始化失败（如缺 key）-> 降级到 mock
        if key != "mock":
            return MockImage3DProvider()
        raise


def list_providers() -> list[str]:
    return sorted(_PROVIDERS.keys())


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------
def _guess_mime(suffix: str) -> str:
    s = suffix.lower().lstrip(".")
    return {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
        "bmp": "image/bmp",
    }.get(s, "application/octet-stream")


def _try_make_thumb_from_image(src: Path, target: Path, size: int = 384) -> bool:
    """把上传的源图缩成 size×size 的居中裁剪缩略图，PNG 保存。"""
    try:
        from PIL import Image, ImageOps  # type: ignore

        img = Image.open(src).convert("RGB")
        img = ImageOps.fit(img, (size, size), method=Image.Resampling.LANCZOS)
        target.parent.mkdir(parents=True, exist_ok=True)
        img.save(target, format="PNG", optimize=True)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# 主入口：被 main.py / cli 调用
# ---------------------------------------------------------------------------
def run_image_to_3d_job(
    job_id: str,
    image_path: str,
    *,
    provider_name: Optional[str] = None,
) -> dict[str, Any]:
    """同步执行一次图生 3D 任务，并在 job_store 里更新进度。

    返回 metrics dict。整个过程中任何抛出都会被 main 里的 `_run_in_thread`
    捕获并标记 status=failed。
    """
    job_dir = config.OUTPUT_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    img_path = Path(image_path)

    def _report(**fields: Any) -> None:
        log = fields.pop("log", None)
        if fields:
            job_store.update_job(job_id, **fields)
        if log:
            job_store.append_log(job_id, log)

    _report(status="running", stage="validate_image", progress=0.05,
            log=f"start image_to_3d job={job_id} provider={provider_name or config.IMAGE3D_PROVIDER}")

    if not img_path.exists():
        raise FileNotFoundError(f"input image not found: {img_path}")

    raw_size_mb = file_size_mb(img_path)

    provider = get_provider(provider_name)
    used_provider = provider.name
    fallback_reason: Optional[str] = None

    with Timer() as t_total:
        try:
            result = provider.generate(img_path, job_dir, _report)
        except Exception as e:
            # 真实 provider 出错 -> mock 降级
            if used_provider != "mock":
                fallback_reason = f"{used_provider} 失败: {e}"
                _report(log=f"[fallback] {fallback_reason}; 切换 mock")
                provider = MockImage3DProvider()
                used_provider = "mock"
                result = provider.generate(img_path, job_dir, _report)
            else:
                raise

    glb_size = file_size_mb(result.glb_path)
    preview_url = f"{config.STATIC_URL_PREFIX}/jobs/{job_id}/exports/glb/model.glb"
    thumb_url = None
    if result.thumbnail_path and result.thumbnail_path.exists():
        try:
            rel = result.thumbnail_path.resolve().relative_to(config.OUTPUT_DIR.resolve())
            thumb_url = f"{config.STATIC_URL_PREFIX}/jobs/{rel.as_posix()}"
        except ValueError:
            thumb_url = None

    metrics = {
        "job_id": job_id,
        "input": {
            "image": str(img_path),
            "raw_size_mb": raw_size_mb,
        },
        "provider": used_provider,
        "provider_task_id": result.provider_task_id,
        "fallback_reason": fallback_reason,
        "timing": {"total_sec": round(t_total.seconds, 3)},
        "outputs": {
            "glb_size_mb": glb_size,
            "preview_url": preview_url,
            "thumbnail_url": thumb_url,
        },
    }
    (job_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    _report(
        status="success",
        stage="finished",
        progress=1.0,
        outputs={
            "glb": str(result.glb_path),
            "preview_url": preview_url,
            "source_image": str(img_path),
            "thumbnail": str(result.thumbnail_path) if result.thumbnail_path else None,
            "provider": used_provider,
            "provider_task_id": result.provider_task_id,
        },
        metrics={"glb_size_mb": glb_size, "raw_size_mb": raw_size_mb},
        log=f"image_to_3d done provider={used_provider} glb={glb_size:.2f}MB",
    )
    return metrics


def run_multiview_to_3d_job(
    job_id: str,
    image_paths: list[str],
    *,
    provider_name: Optional[str] = None,
) -> dict[str, Any]:
    """多视角图生 3D：1-4 张视图（建议按 front/back/left/right 顺序）→ 单个 GLB。

    实现复用 image_to_3d 的 Provider 抽象，调用 Provider.generate_multiview。
    如果 provider 不支持原生 multiview（如 mock），基类会自动 fallback 到第一张图。
    """
    job_dir = config.OUTPUT_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    img_paths: list[Path] = [Path(p) for p in image_paths]
    for p in img_paths:
        if not p.exists():
            raise FileNotFoundError(f"input image not found: {p}")

    raw_size_mb = round(sum(file_size_mb(p) for p in img_paths), 3)

    def _report(**fields: Any) -> None:
        log = fields.pop("log", None)
        if fields:
            job_store.update_job(job_id, **fields)
        if log:
            job_store.append_log(job_id, log)

    _report(
        status="running", stage="validate_image", progress=0.05,
        log=(f"start multiview_to_3d job={job_id} provider={provider_name or config.IMAGE3D_PROVIDER} "
             f"views={len(img_paths)}"),
        metrics={"num_input_files": len(img_paths), "raw_size_mb": raw_size_mb},
    )

    provider = get_provider(provider_name)
    used_provider = provider.name
    fallback_reason: Optional[str] = None

    with Timer() as t_total:
        try:
            result = provider.generate_multiview(img_paths, job_dir, _report)
        except Exception as e:
            if used_provider != "mock":
                fallback_reason = f"{used_provider} 失败: {e}"
                _report(log=f"[fallback] {fallback_reason}; 切换 mock")
                provider = MockImage3DProvider()
                used_provider = "mock"
                result = provider.generate_multiview(img_paths, job_dir, _report)
            else:
                raise

    glb_size = file_size_mb(result.glb_path)
    preview_url = f"{config.STATIC_URL_PREFIX}/jobs/{job_id}/exports/glb/model.glb"
    thumb_url = None
    if result.thumbnail_path and result.thumbnail_path.exists():
        try:
            rel = result.thumbnail_path.resolve().relative_to(config.OUTPUT_DIR.resolve())
            thumb_url = f"{config.STATIC_URL_PREFIX}/jobs/{rel.as_posix()}"
        except ValueError:
            thumb_url = None

    metrics = {
        "job_id": job_id,
        "input": {
            "num_views": len(img_paths),
            "raw_size_mb": raw_size_mb,
            "images": [str(p) for p in img_paths],
        },
        "provider": used_provider,
        "provider_task_id": result.provider_task_id,
        "fallback_reason": fallback_reason,
        "timing": {"total_sec": round(t_total.seconds, 3)},
        "outputs": {
            "glb_size_mb": glb_size,
            "preview_url": preview_url,
            "thumbnail_url": thumb_url,
        },
    }
    (job_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    _report(
        status="success",
        stage="finished",
        progress=1.0,
        outputs={
            "glb": str(result.glb_path),
            "preview_url": preview_url,
            "source_image": str(img_paths[0]) if img_paths else None,
            "thumbnail": str(result.thumbnail_path) if result.thumbnail_path else None,
            "provider": used_provider,
            "provider_task_id": result.provider_task_id,
        },
        metrics={"glb_size_mb": glb_size, "raw_size_mb": raw_size_mb},
        log=f"multiview_to_3d done provider={used_provider} glb={glb_size:.2f}MB views={len(img_paths)}",
    )
    return metrics


def run_image_to_3d_resume(job_id: str, tripo_task_id: str) -> dict[str, Any]:
    """从已有 Tripo task_id 拉产物，避免重复扣费。

    适用场景：之前提交任务时由于网络瞬时错误被 fallback 到 mock，但任务在
    Tripo 服务器上仍然完成了；这里允许把那次产物挂回本地作为正式 job。
    """
    job_dir = config.OUTPUT_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    def _report(**fields: Any) -> None:
        log = fields.pop("log", None)
        if fields:
            job_store.update_job(job_id, **fields)
        if log:
            job_store.append_log(job_id, log)

    _report(status="running", stage="polling", progress=0.3,
            log=f"resume tripo task {tripo_task_id}")

    if not config.TRIPO_API_KEY:
        raise RuntimeError("resume 需要 TRIPO_API_KEY；请检查 scripts/.env.local")
    provider = TripoImage3DProvider()
    with Timer() as t_total:
        result = provider.fetch_existing_task(tripo_task_id, job_dir, _report)

    glb_size = file_size_mb(result.glb_path)
    preview_url = f"{config.STATIC_URL_PREFIX}/jobs/{job_id}/exports/glb/model.glb"
    thumb_url = None
    if result.thumbnail_path and result.thumbnail_path.exists():
        try:
            rel = result.thumbnail_path.resolve().relative_to(config.OUTPUT_DIR.resolve())
            thumb_url = f"{config.STATIC_URL_PREFIX}/jobs/{rel.as_posix()}"
        except ValueError:
            thumb_url = None

    metrics = {
        "job_id": job_id,
        "provider": "tripo",
        "provider_task_id": tripo_task_id,
        "resumed": True,
        "timing": {"total_sec": round(t_total.seconds, 3)},
        "outputs": {
            "glb_size_mb": glb_size,
            "preview_url": preview_url,
            "thumbnail_url": thumb_url,
        },
    }
    (job_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    _report(
        status="success",
        stage="finished",
        progress=1.0,
        outputs={
            "glb": str(result.glb_path),
            "preview_url": preview_url,
            "thumbnail": str(result.thumbnail_path) if result.thumbnail_path else None,
            "provider": "tripo",
            "provider_task_id": tripo_task_id,
        },
        metrics={"glb_size_mb": glb_size},
        log=f"image_to_3d resume done glb={glb_size:.2f}MB",
    )
    return metrics
