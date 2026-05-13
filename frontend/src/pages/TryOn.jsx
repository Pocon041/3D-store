import React from "react";
import TryOnPanel from "../components/TryOnPanel.jsx";

export default function TryOn() {
  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>虚拟试穿</h1>
          <p>上传自己的照片和心仪的服装图，几秒内得到试穿效果。无需下载 App，纯网页推理。</p>
        </div>
      </header>

      <section className="section">
        <p className="desc">
          mock 模式：把人像和服装拼接到一起作为占位结果，便于无 GPU 演示。
          关闭 mock 后调用 external/CatVTON 真实推理（需先克隆 CatVTON 仓库并安装权重）。
        </p>
        <TryOnPanel />
      </section>

      <section className="info-card">
        <h3>为什么试穿能降低退货成本</h3>
        <ul>
          <li>消费者购前可视化版型，避免买回家『效果完全不对』。</li>
          <li>退换货物流单次成本 5-20 元，规模化后影响显著。</li>
          <li>对长尾 SKU 拍模特图代价高，AIGC 试穿可补全。</li>
        </ul>
      </section>
    </div>
  );
}
