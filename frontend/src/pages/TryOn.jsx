import React, { useMemo } from "react";
import TryOnPanel from "../components/TryOnPanel.jsx";
import { navigate } from "../router.js";

function selectedProductId(path) {
  const queryIndex = path.indexOf("?");
  if (queryIndex < 0) return null;
  return new URLSearchParams(path.slice(queryIndex + 1)).get("product");
}

export default function TryOn({ path = "/tryon" }) {
  const productId = useMemo(() => selectedProductId(path), [path]);

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>虚拟试穿</h1>
          <p>从服装商品带入服装图，上传人像后生成试穿结果。</p>
        </div>
        <button className="secondary" onClick={() => navigate("/shop")}>
          返回商城选服装
        </button>
      </header>

      <section className="section">
        <TryOnPanel selectedProductId={productId} />
      </section>
    </div>
  );
}
