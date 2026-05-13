import React, { useEffect, useMemo, useRef, useState } from "react";
import { listProducts } from "../api.js";
import AvatarDressStage, { GARMENT_PRESETS } from "../components/AvatarDressStage.jsx";

const GARMENT_COLORS = [
  { name: "曜石黑", value: 0x111827 },
  { name: "云雾白", value: 0xf8fafc },
  { name: "电光蓝", value: 0x2563eb },
  { name: "珊瑚橙", value: 0xe4573d },
  { name: "苔原绿", value: 0x159464 },
  { name: "紫晶灰", value: 0x6d5dfc },
];

const MATERIALS = [
  { key: "matte", label: "哑光棉" },
  { key: "satin", label: "缎面微光" },
  { key: "denim", label: "粗纹牛仔" },
  { key: "technical", label: "机能面料" },
];

const BODY_COLORS = [
  { key: "porcelain", label: "陶瓷人台" },
  { key: "graphite", label: "石墨人台" },
  { key: "warm", label: "暖肤人台" },
  { key: "studio", label: "工作室灰" },
];

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
  const [selectedProductId, setSelectedProductId] = useState("");
  const [garment, setGarment] = useState("tee");
  const [garmentColor, setGarmentColor] = useState(GARMENT_COLORS[2].value);
  const [garmentMaterial, setGarmentMaterial] = useState("matte");
  const [bodyColor, setBodyColor] = useState("porcelain");
  const [pose, setPose] = useState("relaxed");
  const [heightScale, setHeightScale] = useState(1);
  const [shoulderScale, setShoulderScale] = useState(1);
  const [waistScale, setWaistScale] = useState(1);
  const [ghostBody, setGhostBody] = useState(false);
  const [showGrid, setShowGrid] = useState(true);
  const [showSeams, setShowSeams] = useState(true);
  const [customFile, setCustomFile] = useState(null);
  const [customModelUrl, setCustomModelUrl] = useState(null);
  const [customScale, setCustomScale] = useState(1);
  const [customYOffset, setCustomYOffset] = useState(0);
  const [customXOffset, setCustomXOffset] = useState(0);
  const [customZOffset, setCustomZOffset] = useState(0);
  const [customRotationY, setCustomRotationY] = useState(0);

  useEffect(() => {
    let cancelled = false;
    listProducts()
      .then((r) => {
        if (cancelled) return;
        setProducts((r.items || []).filter((p) => p.model_url));
      })
      .catch((e) => {
        if (!cancelled) setProductError(String(e));
      });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    const hash = window.location.hash || "";
    const qIndex = hash.indexOf("?");
    if (qIndex < 0) return;
    const params = new URLSearchParams(hash.slice(qIndex + 1));
    const productId = params.get("product");
    if (productId) setSelectedProductId(productId);
  }, []);

  useEffect(() => {
    if (!customFile) {
      setCustomModelUrl(null);
      return undefined;
    }
    const url = URL.createObjectURL(customFile);
    setCustomModelUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [customFile]);

  const settings = useMemo(() => ({
    garment,
    garmentColor,
    garmentMaterial,
    bodyColor,
    pose,
    heightScale,
    shoulderScale,
    waistScale,
    ghostBody,
    showGrid,
    showSeams,
    customScale,
    customYOffset,
    customXOffset,
    customZOffset,
    customRotationY,
  }), [
    garment,
    garmentColor,
    garmentMaterial,
    bodyColor,
    pose,
    heightScale,
    shoulderScale,
    waistScale,
    ghostBody,
    showGrid,
    showSeams,
    customScale,
    customYOffset,
    customXOffset,
    customZOffset,
    customRotationY,
  ]);

  const activeGarment = GARMENT_PRESETS[garment];
  const selectedProduct = useMemo(
    () => products.find((p) => p.id === selectedProductId) || null,
    [products, selectedProductId],
  );
  const overlayModelUrl = customModelUrl || selectedProduct?.model_url || null;
  const overlayName = customFile?.name || selectedProduct?.name || null;
  const handleSnapshot = () => {
    const dataUrl = stageRef.current?.snapshot();
    downloadDataUrl(dataUrl, `avatar-tryon-${garment}.png`);
  };

  return (
    <div className="page avatar-tryon-page">
      <header className="page-header">
        <div>
          <h1>3D 假人换装台</h1>
          <p>用更接近真实比例的人台承接商城 GLB：选择商品模型后可叠加到身体上，并手动校准比例、位置和朝向。</p>
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
              <strong>{activeGarment?.label}</strong>
              <span>{overlayName ? `叠加：${overlayName}` : "内置 3D 服装预设"}</span>
            </div>
            <button className="secondary" onClick={handleSnapshot}>导出截图</button>
          </div>
          <AvatarDressStage
            ref={stageRef}
            settings={settings}
            customModelUrl={overlayModelUrl}
          />
        </div>

        <aside className="avatar-controls">
          <section className="control-block">
            <h2>服装</h2>
            <div className="segmented-grid">
              {Object.entries(GARMENT_PRESETS).map(([key, item]) => (
                <button
                  key={key}
                  className={garment === key ? "active" : ""}
                  onClick={() => setGarment(key)}
                >
                  {item.label}
                </button>
              ))}
            </div>

            <label className="form-label">颜色</label>
            <div className="swatch-row">
              {GARMENT_COLORS.map((c) => (
                <button
                  key={c.name}
                  className={garmentColor === c.value ? "active" : ""}
                  title={c.name}
                  style={{ backgroundColor: `#${c.value.toString(16).padStart(6, "0")}` }}
                  onClick={() => setGarmentColor(c.value)}
                />
              ))}
            </div>

            <label className="form-label">材质</label>
            <select value={garmentMaterial} onChange={(e) => setGarmentMaterial(e.target.value)}>
              {MATERIALS.map((m) => <option key={m.key} value={m.key}>{m.label}</option>)}
            </select>
          </section>

          <section className="control-block">
            <h2>人台</h2>
            <label className="form-label">人台材质</label>
            <select value={bodyColor} onChange={(e) => setBodyColor(e.target.value)}>
              {BODY_COLORS.map((b) => <option key={b.key} value={b.key}>{b.label}</option>)}
            </select>

            <label className="form-label">姿态</label>
            <select value={pose} onChange={(e) => setPose(e.target.value)}>
              <option value="relaxed">自然站姿</option>
              <option value="a">A 字展示</option>
              <option value="runway">走秀站姿</option>
            </select>

            <div className="slider-field">
              <span>身高</span>
              <input type="range" min="0.9" max="1.12" step="0.01" value={heightScale} onChange={(e) => setHeightScale(Number(e.target.value))} />
              <strong>{heightScale.toFixed(2)}</strong>
            </div>
            <div className="slider-field">
              <span>肩宽</span>
              <input type="range" min="0.85" max="1.18" step="0.01" value={shoulderScale} onChange={(e) => setShoulderScale(Number(e.target.value))} />
              <strong>{shoulderScale.toFixed(2)}</strong>
            </div>
            <div className="slider-field">
              <span>腰胯</span>
              <input type="range" min="0.85" max="1.15" step="0.01" value={waistScale} onChange={(e) => setWaistScale(Number(e.target.value))} />
              <strong>{waistScale.toFixed(2)}</strong>
            </div>

            <label className="toggle-line">
              <input type="checkbox" checked={ghostBody} onChange={(e) => setGhostBody(e.target.checked)} />
              <span>半透明人台</span>
            </label>
            <label className="toggle-line">
              <input type="checkbox" checked={showGrid} onChange={(e) => setShowGrid(e.target.checked)} />
              <span>显示地面参考线</span>
            </label>
            <label className="toggle-line">
              <input type="checkbox" checked={showSeams} onChange={(e) => setShowSeams(e.target.checked)} />
              <span>显示服装缝线</span>
            </label>
          </section>

          <section className="control-block">
            <h2>商品 GLB 叠穿</h2>
            <p>可直接选择商城商品模型，也可上传服装 GLB。不同资产坐标系不一致，需要手动调节位置。</p>
            <label className="form-label">商城商品资产</label>
            <select
              value={selectedProductId}
              onChange={(e) => {
                setSelectedProductId(e.target.value);
                if (e.target.value) setCustomFile(null);
              }}
            >
              <option value="">不叠加商城商品</option>
              {products.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} · {p.category}
                </option>
              ))}
            </select>
            {productError && <div className="error-message compact">商品资产读取失败：{productError}</div>}
            {selectedProduct && (
              <div className="asset-chip">
                <span>{selectedProduct.source === "user" ? "用户作品" : "商城资产"}</span>
                <strong>{selectedProduct.name}</strong>
              </div>
            )}

            <label className="form-label">上传 GLB / GLTF</label>
            <input
              type="file"
              accept=".glb,.gltf,model/gltf-binary,model/gltf+json"
              onChange={(e) => {
                const file = e.target.files?.[0] || null;
                setCustomFile(file);
                if (file) setSelectedProductId("");
              }}
            />
            <div className="slider-field">
              <span>比例</span>
              <input type="range" min="0.25" max="3.2" step="0.05" value={customScale} onChange={(e) => setCustomScale(Number(e.target.value))} />
              <strong>{customScale.toFixed(2)}</strong>
            </div>
            <div className="slider-field">
              <span>高度</span>
              <input type="range" min="-1.2" max="1.4" step="0.02" value={customYOffset} onChange={(e) => setCustomYOffset(Number(e.target.value))} />
              <strong>{customYOffset.toFixed(2)}</strong>
            </div>
            <div className="slider-field">
              <span>左右</span>
              <input type="range" min="-1.2" max="1.2" step="0.02" value={customXOffset} onChange={(e) => setCustomXOffset(Number(e.target.value))} />
              <strong>{customXOffset.toFixed(2)}</strong>
            </div>
            <div className="slider-field">
              <span>前后</span>
              <input type="range" min="-1.2" max="1.2" step="0.02" value={customZOffset} onChange={(e) => setCustomZOffset(Number(e.target.value))} />
              <strong>{customZOffset.toFixed(2)}</strong>
            </div>
            <div className="slider-field">
              <span>旋转</span>
              <input type="range" min="-3.14" max="3.14" step="0.02" value={customRotationY} onChange={(e) => setCustomRotationY(Number(e.target.value))} />
              <strong>{customRotationY.toFixed(2)}</strong>
            </div>
            {(customFile || selectedProductId) && (
              <button
                className="secondary"
                onClick={() => {
                  setCustomFile(null);
                  setSelectedProductId("");
                }}
              >
                移除叠加模型
              </button>
            )}
          </section>
        </aside>
      </section>

      <section className="info-card avatar-info">
        <h3>实现路线</h3>
        <ul>
          <li>当前版本支持直接选择商城商品 GLB 或上传本地 GLB，适合展示“商品资产进入试穿场景”的闭环。</li>
          <li>不同商品模型坐标系和真实尺寸差异很大，所以第一版提供比例、前后、左右、高度和旋转校准。</li>
          <li>真正布料仿真可作为研究扩展，接 TailorNet、M3D-VTON 或 Blender cloth pipeline。</li>
        </ul>
      </section>
    </div>
  );
}
