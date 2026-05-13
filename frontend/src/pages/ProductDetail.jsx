import React, { useEffect, useState } from "react";
import { deleteProduct, getProduct } from "../api.js";
import { addToCart, removeFromCart } from "../cart.js";
import { goBack, navigate } from "../router.js";
import Model3DPreview from "../components/Model3DPreview.jsx";

function priceText(price) {
  if (!price) return "面议";
  if (price >= 1000) return `¥${price.toLocaleString("zh-CN")}`;
  return `¥${price.toFixed(price < 100 ? 1 : 0)}`;
}

export default function ProductDetail({ productId }) {
  const [product, setProduct] = useState(null);
  const [error, setError] = useState(null);
  const [qty, setQty] = useState(1);
  const [added, setAdded] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    setProduct(null);
    setError(null);
    setAdded(false);
    setDeleting(false);
    setQty(1);
    getProduct(productId)
      .then(setProduct)
      .catch((e) => setError(String(e)));
  }, [productId]);

  if (error) {
    return (
      <div className="page">
        <button className="back-link" onClick={() => goBack("/shop")}>← 返回上一页</button>
        <div className="error-banner">{error}</div>
      </div>
    );
  }
  if (!product) {
    return (
      <div className="page">
        <button className="back-link" onClick={() => goBack("/shop")}>← 返回上一页</button>
        <div className="loading">加载中…</div>
      </div>
    );
  }

  const onAdd = () => {
    addToCart(product, qty);
    setAdded(true);
    setTimeout(() => setAdded(false), 1500);
  };

  const onDelete = async () => {
    if (!product || product.source !== "user") return;
    const ok = window.confirm(`确定删除「${product.name}」吗？\n删除后它会从商城和购物车中移除，生成任务文件仍会保留。`);
    if (!ok) return;

    setDeleting(true);
    setError(null);
    try {
      await deleteProduct(product.id);
      removeFromCart(product.id);
      navigate("/shop");
    } catch (e) {
      setError(String(e));
      setDeleting(false);
    }
  };

  return (
    <div className="page detail-page">
      <button className="back-link" onClick={() => goBack("/shop")}>← 返回上一页</button>

      <div className="detail-layout">
        <div className="detail-viewer">
          <Model3DPreview src={product.model_url} poster={product.thumbnail_url} height={560} />
          <div className="viewer-foot">
            <span>3D 预览 · PBR 材质 · 移动端 AR</span>
            <a href={product.model_url} target="_blank" rel="noreferrer">下载 GLB</a>
          </div>
        </div>

        <aside className="detail-info">
          <div className="detail-cat">
            <span>{product.category}</span>
            <span>{product.model_local ? "Local asset" : "CDN asset"}</span>
          </div>
          <h1 className="detail-name">{product.name}</h1>
          <div className="detail-price">
            <span className="price-num">{priceText(product.price)}</span>
            {product.stock != null && <span className="stock">库存 {product.stock}</span>}
          </div>
          <p className="detail-desc">{product.description}</p>

          <div className="detail-tags">
            {(product.tags || []).map((t) => <span key={t} className="tag-chip">#{t}</span>)}
          </div>

          <div className="qty-row">
            <span>数量</span>
            <button onClick={() => setQty(Math.max(1, qty - 1))}>−</button>
            <input value={qty} readOnly />
            <button onClick={() => setQty(qty + 1)}>+</button>
          </div>

          <div className="detail-buttons">
            <button className="btn-primary" onClick={onAdd}>{added ? "已加入" : "加入购物车"}</button>
            <button className="btn-secondary" onClick={() => { addToCart(product, qty); navigate("/cart"); }}>
              立即购买
            </button>
            {product.tryonable && (
              <button className="btn-tryon" onClick={() => navigate("/tryon")}>
                虚拟试穿这件
              </button>
            )}
            <button
              className="secondary"
              onClick={() => navigate(`/avatar-tryon?product=${encodeURIComponent(product.id)}`)}
            >
              3D 人台预览
            </button>
            {product.source === "user" && (
              <button className="btn-danger" onClick={onDelete} disabled={deleting}>
                {deleting ? "删除中…" : "删除商品"}
              </button>
            )}
          </div>

          <div className="detail-assurance">
            <div>
              <strong>360°</strong>
              <span>可交互检视</span>
            </div>
            <div>
              <strong>AR</strong>
              <span>实景摆放</span>
            </div>
            <div>
              <strong>PBR</strong>
              <span>材质预览</span>
            </div>
          </div>

          <div className="detail-meta">
            <div><span>许可</span>{product.license || "—"}</div>
            <div><span>来源</span>{product.source}</div>
            <div><span>资产</span>{product.model_local ? "本地" : "CDN"}</div>
            {product.job_id && (
              <div><span>任务</span>{product.job_id}</div>
            )}
          </div>
        </aside>
      </div>

      <section className="info-card">
        <h3>3D 商品体验亮点</h3>
        <ul>
          <li>360° 旋转检视避免单一拍摄角度的『美颜陷阱』。</li>
          <li>AR 实景预览大型商品的真实尺寸，降低退货物流成本。</li>
          <li>PBR 材质忠实呈现金属、玻璃、布料质感，购前预期更准确。</li>
        </ul>
      </section>
    </div>
  );
}
