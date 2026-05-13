"""图生 3D Provider 抽象 + API 集成测试。

跑法：
    .venv\\Scripts\\python.exe -m pytest tests/test_image_to_3d.py -v
"""
from __future__ import annotations

import io
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend import config
from backend.job_store import job_store
from backend.main import app
from backend.pipelines.image_to_3d import (
    Image3DProvider,
    MockImage3DProvider,
    ProviderResult,
    get_provider,
    list_providers,
    run_image_to_3d_job,
)
from backend.utils.file_utils import generate_job_id


@pytest.fixture()
def fake_image(tmp_path: Path) -> Path:
    """造一张 64x64 的红色 PNG 当测试输入。"""
    img = Image.new("RGB", (64, 64), color=(220, 30, 30))
    p = tmp_path / "input.png"
    img.save(p)
    return p


@pytest.fixture()
def client():
    return TestClient(app)


# ---------------- Provider 抽象层 ----------------
class TestProviders:
    def test_list_providers_has_mock(self):
        ps = list_providers()
        assert "mock" in ps
        # tripo 至少注册了，无 key 时实例化会降级
        assert "tripo" in ps

    def test_get_provider_default_mock(self, monkeypatch):
        monkeypatch.setattr(config, "IMAGE3D_PROVIDER", "mock")
        p = get_provider()
        assert p.name == "mock"
        assert isinstance(p, MockImage3DProvider)

    def test_get_provider_unknown_falls_back_to_mock(self):
        p = get_provider("nonexistent_xxx")
        assert p.name == "mock"

    def test_get_provider_tripo_without_key_falls_back(self, monkeypatch):
        # 没配 TRIPO_API_KEY 时构造会抛，工厂应当降级到 mock
        monkeypatch.setattr(config, "TRIPO_API_KEY", "")
        p = get_provider("tripo")
        assert p.name == "mock"


# ---------------- MockProvider ----------------
class TestMockProvider:
    def test_mock_generates_glb(self, fake_image, tmp_path):
        provider = MockImage3DProvider()
        events: list[dict] = []

        def report(**fields):
            events.append(fields)

        job_dir = tmp_path / "job"
        job_dir.mkdir()
        result = provider.generate(fake_image, job_dir, report)

        assert isinstance(result, ProviderResult)
        assert result.provider == "mock"
        assert result.glb_path.exists()
        assert result.glb_path.stat().st_size > 0
        # 缩略图应该来自源图（红色）
        assert result.thumbnail_path is not None
        assert result.thumbnail_path.exists()
        # 至少有几次 report
        assert any(e.get("stage") == "upload_to_provider" for e in events)
        assert any(e.get("stage") == "download_glb" for e in events)


# ---------------- run_image_to_3d_job 端到端 ----------------
class TestEndToEnd:
    def test_run_full_job_mock(self, fake_image):
        job_id = generate_job_id("img3d-test")
        job_store.create_job(job_id, "image_to_3d", params={"provider": "mock"})
        metrics = run_image_to_3d_job(job_id, str(fake_image), provider_name="mock")

        # 校验 metrics 结构
        assert metrics["provider"] == "mock"
        assert metrics["outputs"]["glb_size_mb"] > 0
        assert metrics["outputs"]["preview_url"].endswith("/exports/glb/model.glb")

        # 校验 job_store 状态
        rec = job_store.get_job(job_id)
        assert rec is not None
        assert rec.status == "success"
        assert rec.progress == 1.0
        assert rec.outputs.glb is not None
        assert Path(rec.outputs.glb).exists()
        assert rec.outputs.provider == "mock"


# ---------------- API 集成 ----------------
class TestAPI:
    def test_providers_endpoint(self, client):
        r = client.get("/api/image-to-3d/providers")
        assert r.status_code == 200
        body = r.json()
        assert "mock" in body["available"]
        assert "default" in body
        assert "tripo_configured" in body

    def test_create_job_mock(self, client, fake_image):
        # 用 fake_image 文件上传
        with fake_image.open("rb") as f:
            r = client.post(
                "/api/image-to-3d",
                files={"image": ("input.png", f, "image/png")},
                data={"provider": "mock"},
            )
        assert r.status_code == 200, r.text
        body = r.json()
        job_id = body["job_id"]
        assert body["status"] == "queued"

        # 轮询任务直到 success（mock 应该很快）
        deadline = time.monotonic() + 10
        final = None
        while time.monotonic() < deadline:
            jr = client.get(f"/api/jobs/{job_id}")
            assert jr.status_code == 200
            final = jr.json()
            if final["status"] in {"success", "failed"}:
                break
            time.sleep(0.2)

        assert final is not None and final["status"] == "success", final
        assert final["outputs"]["glb"] is not None
        # 静态资源应该可以访问
        preview_url = final["outputs"]["preview_url"]
        assert preview_url.startswith("/static/jobs/")
        sr = client.get(preview_url)
        assert sr.status_code == 200
        assert sr.headers.get("content-type", "").startswith("model/gltf")

    def test_create_job_invalid_format(self, client, tmp_path):
        # 上传 .txt 应该被拒
        txt = tmp_path / "x.txt"
        txt.write_text("not an image")
        with txt.open("rb") as f:
            r = client.post(
                "/api/image-to-3d",
                files={"image": ("x.txt", f, "text/plain")},
            )
        assert r.status_code == 400


# ---------------- 一键上架 ----------------
class TestPublish:
    def test_publish_after_success(self, client, fake_image):
        # 1) 创建一个 mock job 并等它跑完
        with fake_image.open("rb") as f:
            r = client.post(
                "/api/image-to-3d",
                files={"image": ("in.png", f, "image/png")},
                data={"provider": "mock"},
            )
        job_id = r.json()["job_id"]
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            j = client.get(f"/api/jobs/{job_id}").json()
            if j["status"] in {"success", "failed"}:
                break
            time.sleep(0.2)
        assert j["status"] == "success"

        # 2) 默认上架
        pr = client.post(f"/api/products/publish/{job_id}", json={})
        assert pr.status_code == 200, pr.text
        product = pr.json()
        assert product["id"] == f"job-{job_id}"
        assert product["category"] == "user-uploads"
        assert product["published"] is True
        assert product["task_type"] == "image_to_3d"

        # 3) 商品列表里能查到
        all_resp = client.get("/api/products").json()
        ids = {p["id"] for p in all_resp["items"]}
        assert f"job-{job_id}" in ids

        # 4) 自定义名称/价格/分类 publish
        pr2 = client.post(
            f"/api/products/publish/{job_id}",
            json={"name": "测试新品", "price": 199.0, "category": "collectibles", "stock": 50},
        )
        assert pr2.status_code == 200
        p2 = pr2.json()
        # 商品 name 可能带 [mock] 前缀（因为 provider=mock）
        assert "测试新品" in p2["name"]
        assert p2["price"] == 199.0
        assert p2["category"] == "collectibles"
        assert p2["stock"] == 50

        # 5) 删除自定义商品后，商城列表和详情都不再暴露它
        dr = client.delete(f"/api/products/job-{job_id}")
        assert dr.status_code == 200, dr.text
        assert dr.json()["deleted"] is True

        gone = client.get(f"/api/products/job-{job_id}")
        assert gone.status_code == 404

        all_after_delete = client.get("/api/products").json()
        ids_after_delete = {p["id"] for p in all_after_delete["items"]}
        assert f"job-{job_id}" not in ids_after_delete

    def test_publish_nonexistent_job(self, client):
        r = client.post("/api/products/publish/no-such-job", json={})
        assert r.status_code == 404


# ---------------- multi-view ----------------
@pytest.fixture()
def fake_images(tmp_path: Path) -> list[Path]:
    """造 4 张 64x64 不同颜色的 PNG 当多视角输入。"""
    colors = [(220, 30, 30), (30, 220, 30), (30, 30, 220), (220, 220, 30)]
    paths = []
    for i, c in enumerate(colors):
        img = Image.new("RGB", (64, 64), color=c)
        p = tmp_path / f"view_{i}.png"
        img.save(p)
        paths.append(p)
    return paths


class TestMultiView:
    def test_mock_provider_multiview_fallback(self, fake_images, tmp_path):
        """mock provider 不支持原生 multiview，会 fallback 到第一张图。"""
        provider = MockImage3DProvider()
        events: list[dict] = []

        def report(**fields):
            events.append(fields)

        job_dir = tmp_path / "job"
        job_dir.mkdir()
        result = provider.generate_multiview(fake_images, job_dir, report)
        assert result.glb_path.exists()
        # 应该有 fallback 提示日志
        logs = [e.get("log", "") for e in events]
        assert any("不支持原生 multiview" in l for l in logs)

    def test_api_multiview_mock(self, client, fake_images):
        files = [("images", (p.name, p.open("rb"), "image/png")) for p in fake_images]
        try:
            r = client.post(
                "/api/multiview-to-3d",
                files=files,
                data={"provider": "mock"},
            )
        finally:
            for _, (_, f, _) in files:
                f.close()
        assert r.status_code == 200, r.text
        body = r.json()
        job_id = body["job_id"]

        # 轮询完成
        deadline = time.monotonic() + 10
        final = None
        while time.monotonic() < deadline:
            jr = client.get(f"/api/jobs/{job_id}").json()
            final = jr
            if jr["status"] in {"success", "failed"}:
                break
            time.sleep(0.2)
        assert final and final["status"] == "success", final
        assert final["params"]["kind"] == "multiview"
        assert final["params"]["num_views"] == 4
        # GLB 静态可访问
        preview_url = final["outputs"]["preview_url"]
        sr = client.get(preview_url)
        assert sr.status_code == 200

    def test_api_multiview_validation(self, client, tmp_path):
        # 0 张图应该被拒
        r = client.post("/api/multiview-to-3d", files=[])
        assert r.status_code in (400, 422)  # FastAPI/Starlette 不同版本可能返回 422

        # 超过 4 张
        paths = []
        for i in range(5):
            img = Image.new("RGB", (32, 32), color=(0, 0, 0))
            p = tmp_path / f"x{i}.png"
            img.save(p)
            paths.append(p)
        files = [("images", (p.name, p.open("rb"), "image/png")) for p in paths]
        try:
            r = client.post("/api/multiview-to-3d", files=files)
        finally:
            for _, (_, f, _) in files:
                f.close()
        assert r.status_code == 400
        assert "4" in r.json()["detail"]
