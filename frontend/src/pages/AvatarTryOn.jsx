import React, { useEffect, useMemo, useRef, useState } from "react";
import { listProducts } from "../api.js";
import AvatarDressStage from "../components/AvatarDressStage.jsx";

/**
 * 3D 人台换装页面。
 *
 * 这里和 2D CatVTON "虚拟试穿"分开：CatVTON 只处理上装 / 下装 / 连衣裙的图片；
 * 这个页面处理 GLB，人台上可以同时叠加上装、下装、连衣裙 / 全身、鞋子四个槽位。
 */

const BODY_COLORS = [
  { key: "porcelain", label: "陶瓷人台" },
  { key: "graphite", label: "石墨人台" },
  { key: "warm", label: "暖肤人台" },
  { key: "studio", label: "工作室灰" },
];

const GARMENT_SLOTS = [
  { key: "upper", label: "上装", hint: "T 恤 / 外套 / 背心", emptyLabel: "不叠加上装" },
  { key: "lower", label: "下装", hint: "裤装 / 半裙", emptyLabel: "不叠加下装" },
  { key: "full", label: "连衣裙", hint: "连衣裙 / 长袍 / 全身服装", emptyLabel: "不叠加连衣裙" },
  { key: "shoes", label: "鞋子", hint: "运动鞋 / 靴子 / 鞋类", emptyLabel: "不叠加鞋子" },
];

const DEFAULT_TRANSFORM = {
  customScale: 1,
  customYOffset: 0,
  customXOffset: 0,
  customZOffset: 0,
  customRotationY: 0,
};

function makeSlotMap(valueFactory) {
  return Object.fromEntries(GARMENT_SLOTS.map((slot) => [slot.key, valueFactory(slot)]));
}

function productText(product) {
  return [
    product.id,
    product.name,
    product.description,
    product.category,
    product.source,
    product.filename,
    ...(product.tags || []),
  ].join(" ").toLowerCase();
}

function hasAny(text, keywords) {
  return keywords.some((kw) => text.includes(kw));
}

function isShoeProduct(product) {
  return hasAny(productText(product), [
    "shoe", "shoes", "sneaker", "boot", "boots", "footwear",
    "鞋", "运动鞋", "跑鞋", "靴",
  ]);
}

function isApparelProduct(product) {
  const text = productText(product);
  return (
    product.category === "apparel"
    || hasAny(text, [
      "apparel", "cloth", "clothing", "garment", "dress", "gown", "shirt",
      "jacket", "coat", "pants", "trousers", "skirt", "corset", "shoe",
      "服装", "服饰", "衣", "裙", "裤", "鞋", "上装", "下装",
    ])
  );
}

function inferSlotFromProduct(product) {
  const text = productText(product);
  if (isShoeProduct(product)) return "shoes";
  if (hasAny(text, ["dress", "gown", "robe", "连衣裙", "长袍", "全身"])) return "full";
  if (hasAny(text, ["pants", "trousers", "skirt", "shorts", "jeans", "裤", "半裙", "下装"])) return "lower";
  return "upper";
}

function filterProductsForSlot(products, slot, query) {
  const q = query.trim().toLowerCase();
  return products
    .filter((p) => (slot === "shoes" ? isShoeProduct(p) : !isShoeProduct(p)))
    .filter((p) => !q || productText(p).includes(q));
}

function downloadDataUrl(dataUrl, filename) {
  if (!dataUrl) return;
  const a = document.createElement("a");
  a.href = dataUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
}

export default function AvatarTryOn() {
  const stageRef = useRef(null);
  const [products, setProducts] = useState([]);
  const [productError, setProductError] = useState(null);
  const [pendingProductId, setPendingProductId] = useState(null);

  const [selectedProductIds, setSelectedProductIds] = useState(() => makeSlotMap(() => ""));
  const [slotSearches, setSlotSearches] = useState(() => makeSlotMap(() => ""));
  const [garmentFiles, setGarmentFiles] = useState(() => makeSlotMap(() => null));
  const [garmentFileUrls, setGarmentFileUrls] = useState(() => makeSlotMap(() => null));

  const [bodyColor, setBodyColor] = useState("porcelain");
  const [ghostBody, setGhostBody] = useState(false);
  const [showGrid, setShowGrid] = useState(true);

  const [activeAdjustSlot, setActiveAdjustSlot] = useState("upper");
  const [slotTransforms, setSlotTransforms] = useState(() => (
    makeSlotMap(() => ({ ...DEFAULT_TRANSFORM }))
  ));

  // 自定义 mannequin GLB（覆盖默认 Xbot）
  const [mannequinFile, setMannequinFile] = useState(null);
  const [mannequinFileUrl, setMannequinFileUrl] = useState(null);

  useEffect(() => {
    let cancelled = false;
    listProducts()
      .then((r) => {
        if (cancelled) return;
        setProducts((r.items || []).filter((p) => p.model_url && isApparelProduct(p)));
      })
      .catch((e) => {
        if (!cancelled) setProductError(String(e));
      });
    return () => { cancelled = true; };
  }, []);

  // hash 路由：从商品详情页跳过来时携带 product id
  useEffect(() => {
    const hash = window.location.hash || "";
    const qIndex = hash.indexOf("?");
    if (qIndex < 0) return;
    const params = new URLSearchParams(hash.slice(qIndex + 1));
    const productId = params.get("product");
    if (productId) setPendingProductId(productId);
  }, []);

  useEffect(() => {
    if (!pendingProductId || products.length === 0) return;
    const product = products.find((p) => p.id === pendingProductId);
    if (!product) {
      setPendingProductId(null);
      return;
    }
    const slot = inferSlotFromProduct(product);
    setSelectedProductIds((prev) => ({ ...prev, [slot]: product.id }));
    setGarmentFiles((prev) => ({ ...prev, [slot]: null }));
    setActiveAdjustSlot(slot);
    setPendingProductId(null);
  }, [pendingProductId, products]);

  // 四个槽位的上传文件分别转 object URL。
  useEffect(() => {
    const urls = makeSlotMap(() => null);
    const revokes = [];
    for (const slot of GARMENT_SLOTS) {
      const file = garmentFiles[slot.key];
      if (!file) continue;
      const url = URL.createObjectURL(file);
      urls[slot.key] = url;
      revokes.push(url);
    }
    setGarmentFileUrls(urls);
    return () => {
      revokes.forEach((url) => URL.revokeObjectURL(url));
    };
  }, [garmentFiles]);

  // mannequin 文件 -> object URL
  useEffect(() => {
    if (!mannequinFile) {
      setMannequinFileUrl(null);
      return undefined;
    }
    const url = URL.createObjectURL(mannequinFile);
    setMannequinFileUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [mannequinFile]);

  const selectedProducts = useMemo(() => (
    makeSlotMap((slot) => products.find((p) => p.id === selectedProductIds[slot.key]) || null)
  ), [products, selectedProductIds]);

  const slotOptions = useMemo(() => (
    makeSlotMap((slot) => filterProductsForSlot(products, slot.key, slotSearches[slot.key]))
  ), [products, slotSearches]);

  const garments = useMemo(() => {
    const result = {};
    for (const slot of GARMENT_SLOTS) {
      const fileUrl = garmentFileUrls[slot.key];
      const product = selectedProducts[slot.key];
      const url = fileUrl || product?.model_url || null;
      if (!url) continue;
      result[slot.key] = {
        url,
        label: garmentFiles[slot.key]?.name || product?.name || slot.label,
      };
    }
    return result;
  }, [garmentFileUrls, garmentFiles, selectedProducts]);

  const garmentSummary = useMemo(() => {
    const active = GARMENT_SLOTS
      .filter((slot) => garments[slot.key])
      .map((slot) => `${slot.label}：${garments[slot.key].label}`);
    return active.length ? active.join(" / ") : "未选择服装 GLB";
  }, [garments]);

  const settings = useMemo(() => ({
    mannequinUrl: mannequinFileUrl || undefined,
    bodyColor,
    ghostBody,
    showGrid,
    slotTransforms,
  }), [
    mannequinFileUrl,
    bodyColor,
    ghostBody,
    showGrid,
    slotTransforms,
  ]);

  const activeTransform = slotTransforms[activeAdjustSlot] || DEFAULT_TRANSFORM;

  const updateSlotTransform = (key, value) => {
    setSlotTransforms((prev) => ({
      ...prev,
      [activeAdjustSlot]: {
        ...(prev[activeAdjustSlot] || DEFAULT_TRANSFORM),
        [key]: value,
      },
    }));
  };

  const resetActiveTransform = () => {
    setSlotTransforms((prev) => ({
      ...prev,
      [activeAdjustSlot]: { ...DEFAULT_TRANSFORM },
    }));
  };

  const clearSlot = (slotKey) => {
    setSelectedProductIds((prev) => ({ ...prev, [slotKey]: "" }));
    setGarmentFiles((prev) => ({ ...prev, [slotKey]: null }));
  };

  const handleSnapshot = () => {
    const dataUrl = stageRef.current?.snapshot();
    downloadDataUrl(dataUrl, `avatar-tryon-${Date.now()}.png`);
  };

  return (
    <div className="page avatar-tryon-page">
      <header className="page-header">
        <div>
          <h1>3D 人台换装</h1>
          <p>
            从商城选择服装 GLB，或给上装、下装、连衣裙、鞋子四个槽位分别上传模型。
            四类资产可以同时叠加在人台上，并各自微调位置。
          </p>
        </div>
        <div className="status-pill">
          <span className="tag success">Three.js</span>
          <span>实时预览</span>
        </div>
      </header>

      <section className="avatar-workbench">
        <div className="avatar-stage-panel">
          <div className="avatar-stage-toolbar">
            <div>
              <strong>3D 换装台</strong>
              <span>{garmentSummary}</span>
            </div>
            <button className="secondary" onClick={handleSnapshot}>导出截图</button>
          </div>
          <AvatarDressStage
            ref={stageRef}
            settings={settings}
            garments={garments}
          />
        </div>

        <aside className="avatar-controls">
          <section className="control-block">
            <h2>服装搭配</h2>
            <p className="control-hint">
              这里只显示服装类 GLB。鞋子会出现在鞋子槽位；2D 虚拟试穿不处理鞋子，但 3D 人台可以展示鞋类模型。
            </p>

            <div className="garment-slot-list">
              {GARMENT_SLOTS.map((slot) => {
                const active = !!garments[slot.key];
                const options = slotOptions[slot.key] || [];
                return (
                  <div key={slot.key} className={`garment-slot-card ${active ? "active" : ""}`}>
                    <div className="garment-slot-head">
                      <div>
                        <strong>{slot.label}</strong>
                        <span>{slot.hint}</span>
                      </div>
                      <button
                        className={`slot-adjust-btn ${activeAdjustSlot === slot.key ? "active" : ""}`}
                        onClick={() => setActiveAdjustSlot(slot.key)}
                        type="button"
                      >
                        调整
                      </button>
                    </div>

                    <input
                      className="slot-search-input"
                      type="search"
                      value={slotSearches[slot.key]}
                      onChange={(e) => setSlotSearches((prev) => ({ ...prev, [slot.key]: e.target.value }))}
                      placeholder={`搜索${slot.label}...`}
                      autoComplete="off"
                    />

                    <select
                      value={selectedProductIds[slot.key]}
                      onChange={(e) => {
                        setSelectedProductIds((prev) => ({ ...prev, [slot.key]: e.target.value }));
                        if (e.target.value) {
                          setGarmentFiles((prev) => ({ ...prev, [slot.key]: null }));
                          setActiveAdjustSlot(slot.key);
                        }
                      }}
                    >
                      <option value="">{slot.emptyLabel}</option>
                      {options.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.name}
                        </option>
                      ))}
                    </select>

                    <label className="form-label">上传{slot.label} GLB / GLTF</label>
                    <input
                      type="file"
                      accept=".glb,.gltf,model/gltf-binary,model/gltf+json"
                      onChange={(e) => {
                        const file = e.target.files?.[0] || null;
                        setGarmentFiles((prev) => ({ ...prev, [slot.key]: file }));
                        if (file) {
                          setSelectedProductIds((prev) => ({ ...prev, [slot.key]: "" }));
                          setActiveAdjustSlot(slot.key);
                        }
                      }}
                    />

                    {active && (
                      <button
                        className="secondary slot-clear-btn"
                        onClick={() => clearSlot(slot.key)}
                        type="button"
                      >
                        移除{slot.label}
                      </button>
                    )}
                  </div>
                );
              })}
            </div>

            {productError && <div className="error-message compact">商品资产读取失败：{productError}</div>}
          </section>

          <section className="control-block">
            <h2>槽位定位</h2>
            <p className="control-hint">
              先点某个槽位的"调整"，下面滑块只影响该槽位，不会移动其它服装。
            </p>

            <div className="slot-adjust-tabs">
              {GARMENT_SLOTS.map((slot) => (
                <button
                  key={slot.key}
                  type="button"
                  className={activeAdjustSlot === slot.key ? "active" : ""}
                  onClick={() => setActiveAdjustSlot(slot.key)}
                >
                  {slot.label}
                </button>
              ))}
            </div>

            <div className="slider-field">
              <span>缩放</span>
              <input type="range" min="0.35" max="2.6" step="0.02"
                     value={activeTransform.customScale}
                     onChange={(e) => updateSlotTransform("customScale", Number(e.target.value))} />
              <strong>{activeTransform.customScale.toFixed(2)}</strong>
            </div>
            <div className="slider-field">
              <span>高度</span>
              <input type="range" min="-0.8" max="0.8" step="0.01"
                     value={activeTransform.customYOffset}
                     onChange={(e) => updateSlotTransform("customYOffset", Number(e.target.value))} />
              <strong>{activeTransform.customYOffset.toFixed(2)}</strong>
            </div>
            <div className="slider-field">
              <span>左右</span>
              <input type="range" min="-0.7" max="0.7" step="0.01"
                     value={activeTransform.customXOffset}
                     onChange={(e) => updateSlotTransform("customXOffset", Number(e.target.value))} />
              <strong>{activeTransform.customXOffset.toFixed(2)}</strong>
            </div>
            <div className="slider-field">
              <span>前后</span>
              <input type="range" min="-0.7" max="0.7" step="0.01"
                     value={activeTransform.customZOffset}
                     onChange={(e) => updateSlotTransform("customZOffset", Number(e.target.value))} />
              <strong>{activeTransform.customZOffset.toFixed(2)}</strong>
            </div>
            <div className="slider-field">
              <span>旋转</span>
              <input type="range" min="-3.14" max="3.14" step="0.02"
                     value={activeTransform.customRotationY}
                     onChange={(e) => updateSlotTransform("customRotationY", Number(e.target.value))} />
              <strong>{activeTransform.customRotationY.toFixed(2)}</strong>
            </div>
            <button className="secondary" onClick={resetActiveTransform}>
              重置当前槽位
            </button>
          </section>

          <section className="control-block">
            <h2>人台</h2>
            <label className="form-label">人台底色</label>
            <select value={bodyColor} onChange={(e) => setBodyColor(e.target.value)}>
              {BODY_COLORS.map((b) => <option key={b.key} value={b.key}>{b.label}</option>)}
            </select>

            <label className="toggle-line">
              <input type="checkbox" checked={ghostBody}
                     onChange={(e) => setGhostBody(e.target.checked)} />
              <span>半透明人台（减少遮挡）</span>
            </label>
            <label className="toggle-line">
              <input type="checkbox" checked={showGrid}
                     onChange={(e) => setShowGrid(e.target.checked)} />
              <span>显示地面参考线</span>
            </label>

            <label className="form-label">自定义人台 GLB</label>
            <input
              type="file"
              accept=".glb,.gltf,model/gltf-binary,model/gltf+json"
              onChange={(e) => setMannequinFile(e.target.files?.[0] || null)}
            />
            <p className="control-hint">
              想要更真实的人体？可以下载 rigged GLB 后上传，或覆盖
              <code> data/samples/avatars/mannequin.glb </code>。
            </p>
            {mannequinFile && (
              <div className="asset-chip">
                <span>自定义人台</span>
                <strong>{mannequinFile.name}</strong>
              </div>
            )}
            {mannequinFile && (
              <button className="secondary" onClick={() => setMannequinFile(null)} style={{ marginTop: 6 }}>
                恢复默认人台
              </button>
            )}
          </section>
        </aside>
      </section>

      <section className="info-card avatar-info">
        <h3>当前能做什么，做不到什么</h3>
        <ul>
          <li>
            <strong>3D 人台</strong>：四个槽位可同时叠加，鞋子也能作为 3D 模型展示在人台脚部。
          </li>
          <li>
            <strong>对齐方式</strong>：每个槽位用自己的身体锚点自动缩放和摆放，再用滑块做微调。
          </li>
          <li>
            <strong>边界</strong>：这是实时 GLB 叠加与摆位，不是骨骼绑定或布料仿真；不同来源模型仍可能需要手动调位置。
          </li>
        </ul>
      </section>
    </div>
  );
}
