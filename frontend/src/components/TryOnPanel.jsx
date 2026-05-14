import React, { useEffect, useMemo, useRef, useState } from "react";
import { createTryOnJob, getProduct, getTryOnCapabilities } from "../api.js";
import JobStatus from "./JobStatus.jsx";

function filenameFromUrl(url, fallback) {
  try {
    const path = new URL(url, window.location.origin).pathname;
    const name = decodeURIComponent(path.split("/").pop() || "");
    return name || fallback;
  } catch {
    return fallback;
  }
}

async function fileFromImageUrl(url, fallbackName = "garment.png") {
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`无法读取服装图：${resp.status}`);
  const blob = await resp.blob();
  const type = blob.type || "image/png";
  const ext = type.includes("jpeg") ? ".jpg" : type.includes("webp") ? ".webp" : ".png";
  const name = filenameFromUrl(url, fallbackName).replace(/\.[^.]+$/, "") + ext;
  return new File([blob], name, { type });
}

function categoryFromProduct(product) {
  const value = product?.tryon_category || product?.garment_slot || "upper";
  if (value === "full" || value === "overall") return "dress";
  if (value === "lower") return "lower";
  return "upper";
}

function useObjectUrl(file) {
  const [url, setUrl] = useState(null);
  useEffect(() => {
    if (!file) {
      setUrl(null);
      return undefined;
    }
    const next = URL.createObjectURL(file);
    setUrl(next);
    return () => URL.revokeObjectURL(next);
  }, [file]);
  return url;
}

function GlbGarmentRenderer({ product, onCapture, onError }) {
  const ref = useRef(null);
  const capturedRef = useRef(false);
  const [state, setState] = useState("loading");

  const capture = async () => {
    const el = ref.current;
    if (!el) return;
    setState("capturing");
    try {
      await el.updateComplete;
      const blob = await el.toBlob({ idealAspect: true });
      if (!blob) throw new Error("3D 截图为空");
      onCapture(new File([blob], `${product.id || "garment"}-render.png`, { type: blob.type || "image/png" }));
      setState("ready");
      capturedRef.current = true;
    } catch (e) {
      setState("failed");
      onError(e.message || String(e));
    }
  };

  useEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    capturedRef.current = false;
    setState("loading");
    const onLoad = () => {
      if (!capturedRef.current) capture();
    };
    const onFail = (event) => {
      setState("failed");
      onError(event?.detail?.type || "3D 模型加载失败，无法生成服装图。");
    };
    el.addEventListener("load", onLoad);
    el.addEventListener("error", onFail);
    return () => {
      el.removeEventListener("load", onLoad);
      el.removeEventListener("error", onFail);
    };
  }, [product?.model_url]);

  const label = {
    loading: "正在加载 3D 服装",
    capturing: "正在生成服装图",
    ready: "已从 3D 生成服装图",
    failed: "生成失败，可调整视角后重试",
  }[state];

  return (
    <div className="tryon-render-card">
      <model-viewer
        ref={ref}
        src={product.model_url}
        poster={product.thumbnail_url || ""}
        camera-controls=""
        camera-orbit="0deg 75deg 2.3m"
        field-of-view="28deg"
        exposure="1"
        shadow-intensity="0.8"
        loading="eager"
        style={{ width: "100%", height: 260, background: "#f7f8fa", borderRadius: 8 }}
      />
      <div className="tryon-render-footer">
        <span>{label}</span>
        <button type="button" className="secondary" onClick={capture}>
          重新生成
        </button>
      </div>
    </div>
  );
}

function PreviewTile({ title, image, placeholder }) {
  return (
    <div className="tryon-preview-tile">
      <div className="tryon-preview-title">{title}</div>
      {image ? (
        <img src={image} alt={title} />
      ) : (
        <div className="tryon-preview-empty">{placeholder}</div>
      )}
    </div>
  );
}

export default function TryOnPanel({ selectedProductId = null }) {
  const [personImage, setPersonImage] = useState(null);
  const [garmentImage, setGarmentImage] = useState(null);
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [category, setCategory] = useState("upper");
  const [mock, setMock] = useState(false);
  const [capabilities, setCapabilities] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [preparingGarment, setPreparingGarment] = useState(false);
  const [error, setError] = useState(null);
  const [jobId, setJobId] = useState(null);
  const [result, setResult] = useState(null);

  const personPreview = useObjectUrl(personImage);
  const garmentObjectUrl = useObjectUrl(garmentImage);
  const garmentPreview = garmentObjectUrl || selectedProduct?.thumbnail_url || null;

  useEffect(() => {
    let cancelled = false;
    getTryOnCapabilities()
      .then((info) => {
        if (cancelled) return;
        setCapabilities(info);
        setMock(Boolean(info.default_mock));
      })
      .catch(() => {
        if (cancelled) return;
        setCapabilities({ ready: false, default_mock: true });
        setMock(true);
      });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    setSelectedProduct(null);
    setGarmentImage(null);
    setResult(null);
    setJobId(null);
    if (!selectedProductId) return undefined;

    getProduct(selectedProductId)
      .then(async (product) => {
        if (cancelled) return;
        setSelectedProduct(product);
        setCategory(categoryFromProduct(product));
        if (!product.thumbnail_url) return;
        setPreparingGarment(true);
        try {
          const file = await fileFromImageUrl(product.thumbnail_url, `${product.id}-garment.png`);
          if (!cancelled) setGarmentImage(file);
        } catch (e) {
          if (!cancelled) setError(`服装图读取失败，可从 3D 模型生成：${e.message || e}`);
        } finally {
          if (!cancelled) setPreparingGarment(false);
        }
      })
      .catch((e) => {
        if (!cancelled) setError(String(e));
      });

    return () => { cancelled = true; };
  }, [selectedProductId]);

  const resultUrl = result?.outputs?.preview_url
    || (result?.outputs?.tryon_result ? `/static/jobs/${result.job_id}/tryon/result.png` : null);
  const compareUrl = result?.outputs?.tryon_compare
    ? `/static/jobs/${result.job_id}/tryon/compare.png`
    : null;

  const realReady = capabilities?.ready === true;
  const needsGlbRender = selectedProduct?.model_url && !garmentImage && !selectedProduct?.thumbnail_url;
  const canSubmit = Boolean(personImage && garmentImage && !submitting && !preparingGarment);
  const primaryLabel = submitting
    ? "提交中..."
    : preparingGarment
      ? "正在准备服装图..."
      : mock
        ? "生成预览图"
        : "生成试穿图";

  const statusText = useMemo(() => {
    if (!selectedProduct && !garmentImage) return "未选择服装";
    if (needsGlbRender) return "正在从 3D 生成服装图";
    if (!personImage) return "等待上传人像";
    if (resultUrl) return "已生成结果";
    return "可以开始生成";
  }, [selectedProduct, garmentImage, needsGlbRender, personImage, resultUrl]);

  const handleGarmentFile = (file) => {
    setGarmentImage(file || null);
    setError(null);
    setResult(null);
    setJobId(null);
  };

  const handlePersonFile = (file) => {
    setPersonImage(file || null);
    setError(null);
    setResult(null);
    setJobId(null);
  };

  const onSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    if (!personImage) {
      setError("请先上传人像图。");
      return;
    }
    if (!garmentImage) {
      setError("请先准备服装图。");
      return;
    }
    setSubmitting(true);
    setResult(null);
    try {
      const r = await createTryOnJob({ personImage, garmentImage, category, mock });
      setJobId(r.job_id);
    } catch (e2) {
      setError(String(e2));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="tryon-console">
      <form className="tryon-control-panel" onSubmit={onSubmit}>
        <div className="tryon-panel-head">
          <div>
            <span className="tryon-eyebrow">2D TRY-ON</span>
            <h2>{selectedProduct?.name || "选择服装并上传人像"}</h2>
          </div>
          <span className={`tag ${mock ? "" : "success"}`}>{mock ? "快速预览" : "CatVTON"}</span>
        </div>

        <div className="tryon-status-line">{statusText}</div>

        <section className="tryon-input-block">
          <div className="tryon-input-label">
            <strong>服装</strong>
            {selectedProduct && <span>来自商品库</span>}
          </div>
          {selectedProduct ? (
            <div className="tryon-garment-summary">
              <div className="tryon-garment-thumb">
                {garmentPreview ? <img src={garmentPreview} alt={selectedProduct.name} /> : <span>3D</span>}
              </div>
              <div>
                <div className="tryon-garment-name">{selectedProduct.name}</div>
                <div className="product-tags">
                  {(selectedProduct.tags || []).slice(0, 3).map((t) => (
                    <span className="tiny-tag" key={t}>{t}</span>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <label className="tryon-upload-zone">
              <input type="file" accept="image/*" onChange={(e) => handleGarmentFile(e.target.files?.[0] || null)} />
              <span>上传服装图</span>
            </label>
          )}

          {needsGlbRender && (
            <GlbGarmentRenderer
              product={selectedProduct}
              onCapture={(file) => {
                setGarmentImage(file);
                setError(null);
              }}
              onError={setError}
            />
          )}

          <details className="tryon-advanced">
            <summary>{selectedProduct ? "替换服装图" : "高级设置"}</summary>
            {selectedProduct && (
              <label className="tryon-file-row">
                <span>手动上传服装图</span>
                <input type="file" accept="image/*" onChange={(e) => handleGarmentFile(e.target.files?.[0] || null)} />
              </label>
            )}
            <label className="tryon-file-row">
              <span>服装类别</span>
              <select value={category} onChange={(e) => setCategory(e.target.value)}>
                <option value="upper">上装</option>
                <option value="lower">下装</option>
                <option value="dress">连衣裙 / 整体</option>
              </select>
            </label>
            <label className="tryon-check-row">
              <input type="checkbox" checked={mock} onChange={(e) => setMock(e.target.checked)} />
              <span>快速预览模式</span>
            </label>
          </details>
        </section>

        <section className="tryon-input-block">
          <div className="tryon-input-label">
            <strong>人像</strong>
            <span>正面站姿效果最好</span>
          </div>
          <label className={`tryon-upload-zone ${personPreview ? "has-image" : ""}`}>
            <input type="file" accept="image/*" onChange={(e) => handlePersonFile(e.target.files?.[0] || null)} />
            {personPreview ? <img src={personPreview} alt="person" /> : <span>上传人像图</span>}
          </label>
        </section>

        {!realReady && !mock && (
          <div className="error-message">后端未检测到完整 CatVTON 环境，提交可能失败。</div>
        )}
        {error && <div className="error-message">{error}</div>}

        <button className="primary tryon-submit" type="submit" disabled={!canSubmit}>
          {primaryLabel}
        </button>
      </form>

      <section className="tryon-result-panel">
        <div className="tryon-result-head">
          <div>
            <span className="tryon-eyebrow">RESULT</span>
            <h2>{resultUrl ? "试穿结果" : "预览区"}</h2>
          </div>
          {jobId && <span className="tag">{jobId.slice(0, 12)}</span>}
        </div>

        {jobId && (
          <JobStatus jobId={jobId} onResolved={setResult} />
        )}

        {resultUrl ? (
          <div className="tryon-final-result">
            <img src={resultUrl} alt="try-on result" />
            <div className="tryon-result-actions">
              <a className="secondary" href={resultUrl} target="_blank" rel="noreferrer">打开结果</a>
              {compareUrl && <a className="secondary" href={compareUrl} target="_blank" rel="noreferrer">查看对比图</a>}
            </div>
          </div>
        ) : (
          <div className="tryon-preview-grid">
            <PreviewTile title="服装" image={garmentPreview} placeholder="等待服装" />
            <PreviewTile title="人像" image={personPreview} placeholder="等待人像" />
          </div>
        )}
      </section>
    </div>
  );
}
