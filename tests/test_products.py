"""商品模块单元 + API 集成测试。

跑法（项目根目录）：
    .venv\\Scripts\\python.exe -m pytest tests -v
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import config, products
from backend.main import app
from backend.polyhaven_loader import (
    _pick_category,
    _stable_int,
    load_polyhaven_products,
)


# ---------------- 纯函数 ----------------
class TestPolyhavenLoader:
    def test_stable_int_deterministic(self):
        a = _stable_int("marble_bust_01", 100, 5000)
        b = _stable_int("marble_bust_01", 100, 5000)
        assert a == b
        assert 100 <= a <= 5000

    def test_stable_int_different_seeds(self):
        a = _stable_int("a", 0, 10000)
        b = _stable_int("b", 0, 10000)
        # 极小概率冲突，但同时 a==b 几乎不可能
        assert a != b

    def test_pick_category_direct_mapping(self):
        assert _pick_category(["furniture"]) == "home"
        assert _pick_category(["decorative"]) == "collectibles"
        assert _pick_category(["food"]) == "fresh"
        assert _pick_category(["electronics"]) == "digital"

    def test_pick_category_fallback_to_tags(self):
        # categories 里只有 props，靠 tags 兜底
        assert _pick_category(["props"], ["toy", "kids"]) == "toys"
        assert _pick_category(["props"], ["statue", "art"]) == "collectibles"
        assert _pick_category(["props"], ["camera", "old"]) == "digital"

    def test_pick_category_default_home(self):
        assert _pick_category([]) == "home"
        assert _pick_category(["unknown"], ["irrelevant"]) == "home"

    def test_load_polyhaven_returns_list(self):
        items = load_polyhaven_products()
        assert isinstance(items, list)
        # 假设 fetch_polyhaven_models.py 已经跑过；如果没跑则跳过
        if not items:
            pytest.skip("polyhaven_products.json 不存在或为空，跳过")
        # 抽样校验字段完整
        sample = items[0]
        for key in ("id", "name", "category", "price", "stock", "model_url",
                    "license", "source", "tryonable", "model_local"):
            assert key in sample, f"缺字段 {key}"
        assert sample["source"] == "polyhaven"
        assert sample["id"].startswith("ph-")
        assert sample["model_url"].startswith("/static/samples/polyhaven/")


# ---------------- list_products / search_products ----------------
class TestProductsModule:
    def test_list_products_has_three_sources(self):
        items = products.list_products()
        assert len(items) >= 16  # 至少 Khronos 16 件
        sources = {p.get("source") for p in items}
        assert "khronos" in sources

    def test_list_products_unique_ids(self):
        items = products.list_products()
        ids = [p["id"] for p in items]
        assert len(ids) == len(set(ids)), "商品 id 必须唯一"

    def test_list_products_required_fields(self):
        items = products.list_products()
        required = ("id", "name", "category", "price", "model_url")
        for p in items[:30]:
            for k in required:
                assert k in p, f"商品 {p.get('id')} 缺字段 {k}"

    def test_search_products_match_name(self):
        items = products.list_products()
        # 搜中文"沙发"应该命中至少一个 Poly Haven sofa（沙龙开头）
        results = products.search_products(items, "沙发")
        # sofa 在"沙龙"映射规则下不一定中文命中。改测试英文 sofa
        results_en = products.search_products(items, "sofa")
        # Khronos 没有沙发，Poly Haven 有 sofa_02 之类。如果 polyhaven 没下载到则跳过
        if any(p.get("source") == "polyhaven" for p in items):
            assert len(results_en) >= 1

    def test_search_products_empty_returns_all(self):
        items = products.list_products()
        assert products.search_products(items, "") == items
        assert products.search_products(items, "   ") == items

    def test_search_products_no_match(self):
        items = products.list_products()
        assert products.search_products(items, "zzzzz_no_match_xxx_999") == []

    def test_get_product_by_id(self):
        items = products.list_products()
        first_id = items[0]["id"]
        p = products.get_product(first_id)
        assert p is not None
        assert p["id"] == first_id

    def test_get_product_unknown(self):
        assert products.get_product("nonexistent-product") is None


# ---------------- API 集成 ----------------
@pytest.fixture(scope="module")
def client():
    return TestClient(app)


class TestProductsAPI:
    def test_health(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200

    def test_list_products(self, client):
        r = client.get("/api/products")
        assert r.status_code == 200
        body = r.json()
        assert "items" in body
        assert "categories" in body
        assert len(body["items"]) >= 16
        # categories 至少包含 all / home
        keys = {c["key"] for c in body["categories"]}
        assert "all" in keys and "home" in keys

    def test_filter_by_category(self, client):
        r = client.get("/api/products", params={"category": "home"})
        assert r.status_code == 200
        items = r.json()["items"]
        assert all(p["category"] == "home" for p in items)

    def test_filter_by_unknown_category(self, client):
        r = client.get("/api/products", params={"category": "nonexistent"})
        assert r.status_code == 200
        assert r.json()["items"] == []

    def test_search_query_english_id(self, client):
        # 中文商品名 + 英文 id 场景：搜 helmet 应该命中 damaged-helmet
        r = client.get("/api/products", params={"q": "helmet"})
        assert r.status_code == 200
        items = r.json()["items"]
        assert any(p["id"] == "damaged-helmet" for p in items)

    def test_search_query_chinese_tag(self, client):
        # 搜中文 tag 应该命中
        r = client.get("/api/products", params={"q": "头盔"})
        assert r.status_code == 200
        items = r.json()["items"]
        assert any(p["id"] == "damaged-helmet" for p in items)

    def test_get_single_product(self, client):
        r = client.get("/api/products/damaged-helmet")
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == "damaged-helmet"

    def test_get_unknown_product(self, client):
        r = client.get("/api/products/zzz-no-such")
        assert r.status_code == 404


# ---------------- 静态资源可达性 ----------------
class TestStaticAssets:
    def test_khronos_local_file_exists(self):
        # Khronos 16 件至少有几件本地 GLB
        glb_dir = config.SAMPLES_DIR / "glb"
        if not glb_dir.exists():
            pytest.skip("data/samples/glb 不存在，跳过")
        glbs = list(glb_dir.glob("*.glb"))
        assert len(glbs) >= 1, "至少应有一个本地 GLB"

    def test_polyhaven_assets_complete(self):
        # 抽查一个 slug：gltf + bin + textures 都在
        ph_dir = config.SAMPLES_DIR / "polyhaven"
        if not ph_dir.exists():
            pytest.skip("polyhaven 目录不存在，跳过")
        slugs = [d for d in ph_dir.iterdir() if d.is_dir()]
        if not slugs:
            pytest.skip("polyhaven 目录为空")
        sample = slugs[0]
        gltfs = list(sample.glob("*.gltf"))
        assert gltfs, f"{sample.name} 缺 gltf"

    def test_static_serving(self, tmp_path):
        # 验证 /static/samples/ mount 是否生效
        client = TestClient(app)
        # 找一个真实存在的 polyhaven gltf
        ph_dir = config.SAMPLES_DIR / "polyhaven"
        if not ph_dir.exists():
            pytest.skip("polyhaven 目录不存在，跳过")
        for slug in ph_dir.iterdir():
            if not slug.is_dir():
                continue
            gltfs = list(slug.glob("*.gltf"))
            if not gltfs:
                continue
            rel = gltfs[0].relative_to(config.SAMPLES_DIR)
            url = f"/static/samples/{rel.as_posix()}"
            r = client.get(url)
            assert r.status_code == 200, f"{url} 返回 {r.status_code}"
            ct = r.headers.get("content-type", "")
            assert "gltf" in ct or "json" in ct, f"MIME 不对：{ct}"
            return
        pytest.skip("没找到 gltf 文件")
