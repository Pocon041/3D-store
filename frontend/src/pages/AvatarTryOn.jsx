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

const DEFAULT_POSE = {
  headYaw: 0,
  headPitch: 0,
  headRoll: 0,
  torsoLean: 0,
  torsoTwist: 0,
  torsoSide: 0,
  hipsTilt: 0,
  hipsTwist: 0,
  hipsSide: 0,
  leftShoulderSpread: 0,
  rightShoulderSpread: 0,
  leftArmSpread: 0,
  rightArmSpread: 0,
  leftArmForward: 0,
  rightArmForward: 0,
  leftArmTwist: 0,
  rightArmTwist: 0,
  leftElbowBend: 0,
  rightElbowBend: 0,
  leftLegForward: 0,
  rightLegForward: 0,
  leftLegSide: 0,
  rightLegSide: 0,
  leftLegTwist: 0,
  rightLegTwist: 0,
  leftKneeBend: 0,
  rightKneeBend: 0,
  leftFootPitch: 0,
  rightFootPitch: 0,
  leftFootRoll: 0,
  rightFootRoll: 0,
};

const POSE_PRESETS = [
  { key: "neutral", label: "自然站姿", values: {} },
  {
    key: "relaxed",
    label: "放松垂臂",
    values: {
      leftArmSpread: -18,
      rightArmSpread: -18,
      leftArmForward: 8,
      rightArmForward: 8,
      leftElbowBend: 8,
      rightElbowBend: 8,
    },
  },
  {
    key: "a-pose",
    label: "A 字手臂",
    values: {
      leftArmSpread: -32,
      rightArmSpread: -32,
      leftArmForward: 2,
      rightArmForward: 2,
    },
  },
  {
    key: "editorial",
    label: "陈列侧身",
    values: {
      headYaw: -10,
      torsoTwist: -8,
      hipsTwist: 6,
      leftArmSpread: -22,
      rightArmSpread: -14,
      leftElbowBend: 12,
      rightElbowBend: 6,
      leftLegForward: -4,
      rightLegForward: 5,
      leftKneeBend: 4,
    },
  },
];

const POSE_GROUPS = [
  {
    key: "upper",
    label: "头身",
    fields: [
      { key: "headYaw", label: "头部左右", min: -35, max: 35 },
      { key: "headPitch", label: "头部俯仰", min: -25, max: 25 },
      { key: "headRoll", label: "头部倾斜", min: -20, max: 20 },
      { key: "torsoLean", label: "躯干前后", min: -18, max: 18 },
      { key: "torsoTwist", label: "躯干旋转", min: -28, max: 28 },
      { key: "torsoSide", label: "躯干侧倾", min: -18, max: 18 },
      { key: "hipsTwist", label: "髋部旋转", min: -22, max: 22 },
    ],
  },
  {
    key: "arms",
    label: "手臂",
    fields: [
      { key: "leftArmSpread", label: "左臂开合", min: -80, max: 80 },
      { key: "rightArmSpread", label: "右臂开合", min: -80, max: 80 },
      { key: "leftArmForward", label: "左臂前后", min: -70, max: 70 },
      { key: "rightArmForward", label: "右臂前后", min: -70, max: 70 },
      { key: "leftElbowBend", label: "左肘弯曲", min: -5, max: 120 },
      { key: "rightElbowBend", label: "右肘弯曲", min: -5, max: 120 },
      { key: "leftArmTwist", label: "左臂扭转", min: -55, max: 55 },
      { key: "rightArmTwist", label: "右臂扭转", min: -55, max: 55 },
    ],
  },
  {
    key: "legs",
    label: "腿脚",
    fields: [
      { key: "leftLegForward", label: "左腿前后", min: -45, max: 45 },
      { key: "rightLegForward", label: "右腿前后", min: -45, max: 45 },
      { key: "leftLegSide", label: "左腿侧摆", min: -35, max: 35 },
      { key: "rightLegSide", label: "右腿侧摆", min: -35, max: 35 },
      { key: "leftKneeBend", label: "左膝弯曲", min: -5, max: 100 },
      { key: "rightKneeBend", label: "右膝弯曲", min: -5, max: 100 },
      { key: "leftFootPitch", label: "左脚俯仰", min: -35, max: 35 },
      { key: "rightFootPitch", label: "右脚俯仰", min: -35, max: 35 },
    ],
  },
];

const CONTROL_PANELS = [
  { key: "garment", label: "服装", hint: "选择款式" },
  { key: "fit", label: "贴合", hint: "位置尺寸" },
  { key: "pose", label: "姿态", hint: "骨骼角度" },
  { key: "scene", label: "场景", hint: "人台外观" },
];

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
  const [activeControlPanel, setActiveControlPanel] = useState("garment");
  const [slotTransforms, setSlotTransforms] = useState(() => (
    makeSlotMap(() => ({ ...DEFAULT_TRANSFORM }))
  ));
  const [activePoseGroup, setActivePoseGroup] = useState("upper");
  const [poseControls, setPoseControls] = useState(() => ({ ...DEFAULT_POSE }));

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
    return active.length ? active.join(" / ") : "尚未选择单品";
  }, [garments]);

  const settings = useMemo(() => ({
    mannequinUrl: mannequinFileUrl || undefined,
    bodyColor,
    ghostBody,
    showGrid,
    slotTransforms,
    poseControls,
  }), [
    mannequinFileUrl,
    bodyColor,
    ghostBody,
    showGrid,
    slotTransforms,
    poseControls,
  ]);

  const activeTransform = slotTransforms[activeAdjustSlot] || DEFAULT_TRANSFORM;
  const activeSlot = GARMENT_SLOTS.find((slot) => slot.key === activeAdjustSlot) || GARMENT_SLOTS[0];
  const activeSlotOptions = slotOptions[activeAdjustSlot] || [];
  const activeSlotGarment = garments[activeAdjustSlot] || null;
  const selectedCount = GARMENT_SLOTS.filter((slot) => garments[slot.key]).length;
  const activePose = POSE_GROUPS.find((group) => group.key === activePoseGroup) || POSE_GROUPS[0];

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

  const updatePoseControl = (key, value) => {
    setPoseControls((prev) => ({
      ...prev,
      [key]: value,
    }));
  };

  const applyPosePreset = (preset) => {
    setPoseControls({ ...DEFAULT_POSE, ...preset.values });
  };

  const resetPose = () => {
    setPoseControls({ ...DEFAULT_POSE });
  };

  const clearSlot = (slotKey) => {
    setSelectedProductIds((prev) => ({ ...prev, [slotKey]: "" }));
    setGarmentFiles((prev) => ({ ...prev, [slotKey]: null }));
  };

  const clearAllSlots = () => {
    setSelectedProductIds(makeSlotMap(() => ""));
    setGarmentFiles(makeSlotMap(() => null));
    setSlotSearches(makeSlotMap(() => ""));
    setSlotTransforms(makeSlotMap(() => ({ ...DEFAULT_TRANSFORM })));
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
            为商品上架前的搭配陈列和顾客试看准备一张干净的 3D 穿搭画面。
            先选位置，再选款式，最后微调贴合度。
          </p>
        </div>
        <div className="status-pill">
          <span className="tag success">实时搭配</span>
          <span>{selectedCount}/4 已选择</span>
        </div>
      </header>

      <section className="avatar-workbench">
        <div className="avatar-stage-panel">
          <div className="avatar-stage-toolbar">
            <div>
              <strong>搭配画面</strong>
              <span>{garmentSummary}</span>
            </div>
            <div className="avatar-stage-actions">
              <button className="secondary" onClick={clearAllSlots} disabled={selectedCount === 0}>清空搭配</button>
              <button className="primary" onClick={handleSnapshot}>导出画面</button>
            </div>
          </div>
          <AvatarDressStage
            ref={stageRef}
            settings={settings}
            garments={garments}
          />
        </div>

        <aside className="avatar-controls">
          <div className="control-mode-tabs" role="tablist" aria-label="换装控制面板">
            {CONTROL_PANELS.map((panel) => (
              <button
                key={panel.key}
                type="button"
                className={activeControlPanel === panel.key ? "active" : ""}
                onClick={() => setActiveControlPanel(panel.key)}
              >
                <strong>{panel.label}</strong>
                <span>{panel.hint}</span>
              </button>
            ))}
          </div>

          {activeControlPanel === "garment" && (
          <section className="control-block">
            <div className="control-block-title">
              <span>1</span>
              <div>
                <h2>选择穿搭位置</h2>
                <p>一次只编辑一个位置，已经选择的单品会保留在画面里。</p>
              </div>
            </div>

            <div className="slot-adjust-tabs slot-tabs-large">
              {GARMENT_SLOTS.map((slot) => {
                const filled = !!garments[slot.key];
                return (
                  <button
                    key={slot.key}
                    type="button"
                    className={`${activeAdjustSlot === slot.key ? "active" : ""} ${filled ? "filled" : ""}`}
                    onClick={() => setActiveAdjustSlot(slot.key)}
                  >
                    <span>{slot.label}</span>
                    {filled && <small>已选</small>}
                  </button>
                );
              })}
            </div>

            <div className={`garment-slot-card active focused`}>
              <div className="garment-slot-head">
                <div>
                  <strong>{activeSlot.label}</strong>
                  <span>{activeSlot.hint}</span>
                </div>
                {activeSlotGarment && <span className="asset-state">已加入</span>}
              </div>

              <input
                className="slot-search-input"
                type="search"
                value={slotSearches[activeAdjustSlot]}
                onChange={(e) => setSlotSearches((prev) => ({ ...prev, [activeAdjustSlot]: e.target.value }))}
                placeholder={`搜索${activeSlot.label}商品`}
                autoComplete="off"
              />

              <select
                value={selectedProductIds[activeAdjustSlot]}
                onChange={(e) => {
                  setSelectedProductIds((prev) => ({ ...prev, [activeAdjustSlot]: e.target.value }));
                  if (e.target.value) {
                    setGarmentFiles((prev) => ({ ...prev, [activeAdjustSlot]: null }));
                  }
                }}
              >
                <option value="">{activeSlot.emptyLabel}</option>
                {activeSlotOptions.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>

              <label className="form-label">导入{activeSlot.label} 3D 模型</label>
              <input
                type="file"
                accept=".glb,.gltf,model/gltf-binary,model/gltf+json"
                onChange={(e) => {
                  const file = e.target.files?.[0] || null;
                  setGarmentFiles((prev) => ({ ...prev, [activeAdjustSlot]: file }));
                  if (file) {
                    setSelectedProductIds((prev) => ({ ...prev, [activeAdjustSlot]: "" }));
                  }
                }}
              />

              {activeSlotGarment && (
                <div className="selected-asset-row">
                  <span>{activeSlotGarment.label}</span>
                  <button
                    className="link"
                    onClick={() => clearSlot(activeAdjustSlot)}
                    type="button"
                  >
                    移除
                  </button>
                </div>
              )}
            </div>

            {productError && <div className="error-message compact">商品资产读取失败：{productError}</div>}
          </section>
          )}

          {activeControlPanel === "fit" && (
          <section className="control-block">
            <div className="control-block-title">
              <span>2</span>
              <div>
                <h2>调整贴合度</h2>
                <p>当前正在调整：{activeSlot.label}</p>
              </div>
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
              重置{activeSlot.label}
            </button>
          </section>
          )}

          {activeControlPanel === "pose" && (
          <section className="control-block">
            <div className="control-block-title">
              <span>3</span>
              <div>
                <h2>人台姿态</h2>
                <p>先选一个姿态预设，再按部位微调骨骼角度。</p>
              </div>
            </div>

            <div className="pose-preset-grid">
              {POSE_PRESETS.map((preset) => (
                <button
                  key={preset.key}
                  type="button"
                  onClick={() => applyPosePreset(preset)}
                >
                  {preset.label}
                </button>
              ))}
            </div>

            <div className="pose-group-tabs" role="tablist" aria-label="人台姿态部位">
              {POSE_GROUPS.map((group) => (
                <button
                  key={group.key}
                  type="button"
                  className={activePoseGroup === group.key ? "active" : ""}
                  onClick={() => setActivePoseGroup(group.key)}
                >
                  {group.label}
                </button>
              ))}
            </div>

            <div className="pose-slider-list">
              {activePose.fields.map((field) => (
                <div className="slider-field pose-slider" key={field.key}>
                  <span>{field.label}</span>
                  <input
                    type="range"
                    min={field.min}
                    max={field.max}
                    step="1"
                    value={poseControls[field.key] ?? 0}
                    onChange={(e) => updatePoseControl(field.key, Number(e.target.value))}
                  />
                  <strong>{poseControls[field.key] ?? 0}°</strong>
                </div>
              ))}
            </div>

            <button className="secondary" onClick={resetPose}>
              重置人台姿态
            </button>
          </section>
          )}

          {activeControlPanel === "scene" && (
          <section className="control-block">
            <div className="control-block-title">
              <span>4</span>
              <div>
                <h2>人台与场景</h2>
                <p>按品牌陈列需要调整底色、参考线和人台透明度。</p>
              </div>
            </div>
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

            <label className="form-label">导入自有人台模型</label>
            <input
              type="file"
              accept=".glb,.gltf,model/gltf-binary,model/gltf+json"
              onChange={(e) => setMannequinFile(e.target.files?.[0] || null)}
            />
            <p className="control-hint">
              适合品牌自有人台、尺码模特或门店陈列模板；未导入时使用默认人台。
            </p>
            {mannequinFile && (
              <div className="asset-chip">
                <span>当前人台</span>
                <strong>{mannequinFile.name}</strong>
              </div>
            )}
            {mannequinFile && (
              <button className="secondary" onClick={() => setMannequinFile(null)} style={{ marginTop: 6 }}>
                恢复默认人台
              </button>
            )}
          </section>
          )}
        </aside>
      </section>

      <section className="info-card avatar-info">
        <h3>搭配建议</h3>
        <ul>
          <li>
            <strong>商品页主图</strong>：优先导出正面 45 度视角，能同时看到版型和材质。
          </li>
          <li>
            <strong>组合陈列</strong>：上装、下装和鞋子分开调整，更适合做套装搭配和门店陈列。
          </li>
          <li>
            <strong>上新效率</strong>：同一个人台可以复用多套商品，保持视觉风格一致。
          </li>
        </ul>
      </section>
    </div>
  );
}
