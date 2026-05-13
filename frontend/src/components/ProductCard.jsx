import React, { useState } from "react";
import { addToCart } from "../cart.js";
import { navigate } from "../router.js";

function priceText(price) {
  if (price === 0) return "面议";
  if (price >= 1000) return `¥${price.toLocaleString("zh-CN")}`;
  return `¥${price.toFixed(price < 100 ? 1 : 0)}`;
}

// 给没有 thumbnail 的卡片用：根据商品名的首字生成 SVG 占位
function FallbackThumb({ name }) {
  const ch = (name || "?").trim().charAt(0);
  return (
    <div className="thumb-fallback">
      <span className="thumb-fallback-ch">{ch}</span>
      <span className="thumb-fallback-tip">点击查看 3D</span>
    </div>
  );
}

export default function ProductCard({ product }) {
  const [imgFailed, setImgFailed] = useState(false);
  const showImg = product.thumbnail_url && !imgFailed;
  const sourceLabel = product.source === "user"
    ? "用户作品"
    : product.model_local
      ? "本地资产"
      : "3D 资产";

  return (
    <article
      className="product-card"
      onClick={() => navigate(`/shop/${product.id}`)}
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.target === e.currentTarget && e.key === "Enter") {
          navigate(`/shop/${product.id}`);
        }
      }}
    >
      <div className="product-thumb">
        {showImg ? (
          <img
            src={product.thumbnail_url}
            alt={product.name}
            loading="lazy"
            onError={() => setImgFailed(true)}
          />
        ) : (
          <FallbackThumb name={product.name} />
        )}
        <span className={`source-badge ${product.source === "user" ? "user" : product.model_local ? "local" : ""}`}>
          {sourceLabel}
        </span>
        {product.tryonable && <span className="source-badge tryon">可试穿</span>}
        <div className="product-thumb-overlay">查看 3D</div>
      </div>
      <div className="product-meta">
        <div className="product-kicker">
          <span>{product.category}</span>
          {product.model_local && <span>Local</span>}
        </div>
        <div className="product-name">{product.name}</div>
        <div className="product-tags">
          {(product.tags || []).slice(0, 3).map((t) => (
            <span key={t} className="tiny-tag">{t}</span>
          ))}
        </div>
        <div className="product-bottom">
          <span className="product-price">{priceText(product.price)}</span>
          <button
            className="add-cart"
            onClick={(e) => {
              e.stopPropagation();
              addToCart(product, 1);
            }}
          >
            加入购物车
          </button>
        </div>
      </div>
    </article>
  );
}
