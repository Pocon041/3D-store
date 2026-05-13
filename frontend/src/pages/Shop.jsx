import React, { useEffect, useMemo, useState } from "react";
import { listProducts } from "../api.js";
import ProductCard from "../components/ProductCard.jsx";
import Model3DPreview from "../components/Model3DPreview.jsx";
import { navigate } from "../router.js";

// 把所有商品一次拉回，分类与搜索都在前端内存里做，切换瞬时响应
export default function Shop() {
  const [allItems, setAllItems] = useState([]);
  const [categories, setCategories] = useState([{ key: "all", label: "全部" }]);
  const [active, setActive] = useState("all");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    listProducts()
      .then((r) => {
        if (cancelled) return;
        setAllItems(r.items || []);
        if (r.categories) setCategories(r.categories);
      })
      .catch((e) => { if (!cancelled) setError(String(e)); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  // 计算每个分类下的商品数，给 chip 显示徽标
  const categoryCounts = useMemo(() => {
    const counts = { all: allItems.length };
    for (const p of allItems) {
      counts[p.category] = (counts[p.category] || 0) + 1;
    }
    return counts;
  }, [allItems]);

  // 当前分类 + 搜索词过滤后的列表
  const filteredItems = useMemo(() => {
    const q = query.trim().toLowerCase();
    return allItems.filter((p) => {
      if (active !== "all" && p.category !== active) return false;
      if (!q) return true;
      const hay = [
        p.name,
        p.description,
        (p.tags || []).join(" "),
        p.category,
      ].join(" ").toLowerCase();
      return hay.includes(q);
    });
  }, [allItems, active, query]);

  const localCount = useMemo(() => allItems.filter((p) => p.model_local).length, [allItems]);
  const userCount = useMemo(
    () => allItems.filter((p) => p.source === "user" || p.category === "user-uploads").length,
    [allItems],
  );
  const tryonCount = useMemo(() => allItems.filter((p) => p.tryonable).length, [allItems]);

  // hero 使用第一件本地化商品作为展示，避免首屏依赖 CDN
  const featuredProduct = useMemo(
    () => allItems.find((p) => p.model_local && p.category !== "user-uploads") || allItems[0],
    [allItems],
  );
  const heroSrc = useMemo(() => {
    return featuredProduct?.model_url
      || "https://cdn.jsdelivr.net/gh/KhronosGroup/glTF-Sample-Models@master/2.0/DamagedHelmet/glTF-Binary/DamagedHelmet.glb";
  }, [featuredProduct]);

  return (
    <div className="page">
      <section className="hero">
        <div className="hero-text">
          <div className="hero-eyebrow">AIGC 3D COMMERCE</div>
          <h1>把商品放到顾客手里，再让他们下单</h1>
          <p>从单图、多视角到可交互 GLB 资产，商城、工作台和虚拟试穿在同一个体验里闭环。</p>
          <div className="hero-actions">
            <button className="hero-primary" onClick={() => navigate("/studio")}>
              生成 3D 商品
            </button>
            <button
              className="hero-secondary"
              onClick={() => document.querySelector(".search-box input")?.focus()}
            >
              浏览商品
            </button>
          </div>
          <div className="hero-tags">
            <span>多视角建模</span>
            <span>GLB / AR 预览</span>
            <span>试穿链路</span>
          </div>
          <div className="hero-stats">
            <div>
              <strong>{allItems.length || "..."}</strong>
              <span>上架商品</span>
            </div>
            <div>
              <strong>{localCount}</strong>
              <span>本地资产</span>
            </div>
            <div>
              <strong>{tryonCount}</strong>
              <span>可试穿 SKU</span>
            </div>
          </div>
        </div>
        <div className="hero-art">
          <div className="hero-stage-header">
            <span>Live 3D Preview</span>
            <span>{featuredProduct?.model_local ? "Local asset" : "CDN asset"}</span>
          </div>
          <Model3DPreview
            src={heroSrc}
            height={360}
            background="transparent"
            borderRadius={8}
            ar={false}
          />
          <div className="hero-product-chip">
            <span>{featuredProduct?.name || "精选 3D 商品"}</span>
            <strong>{userCount} 件用户作品</strong>
          </div>
        </div>
      </section>

      <section className="shop-panel">
        <div className="shop-toolbar">
          <div>
            <h2>3D 商品陈列</h2>
            <p>按类目筛选，或直接搜索材质、用途与资产标签。</p>
          </div>
          <div className="search-box">
            <span className="search-icon">⌕</span>
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="搜索商品名称、描述或标签…"
              autoComplete="off"
            />
            {query && (
              <button className="search-clear" onClick={() => setQuery("")} title="清空">×</button>
            )}
          </div>
          <div className="shop-result-meta">
            共 {filteredItems.length} 件
            {query && <span className="result-query"> · 关键词「{query}」</span>}
          </div>
        </div>

        <div className="filter-bar">
          {categories.map((c) => {
            const count = categoryCounts[c.key] ?? 0;
            if (c.key !== "all" && count === 0) return null;
            return (
              <button
                key={c.key}
                className={`filter-chip ${active === c.key ? "active" : ""}`}
                onClick={() => setActive(c.key)}
              >
                {c.label}
                <span className="chip-count">{count}</span>
              </button>
            );
          })}
        </div>

        {error && <div className="error-banner">加载失败：{error}</div>}

        {loading && allItems.length === 0 ? (
          <div className="loading-grid">
            {[...Array(8)].map((_, i) => <div key={i} className="skeleton-card" />)}
          </div>
        ) : (
          <div className="product-grid">
            {filteredItems.map((p) => <ProductCard key={p.id} product={p} />)}
            {filteredItems.length === 0 && (
              <div className="empty">
                {query
                  ? `没有匹配"${query}"的商品，换个关键词试试`
                  : "该分类暂无商品。试试上传到工作台，作品会自动上架。"}
              </div>
            )}
          </div>
        )}
      </section>
    </div>
  );
}
