import React, { useEffect, useRef, useState } from "react";
import {
  createImage3DJob,
  getImage3DProviders,
  getJob,
  publishJobAsProduct,
} from "../api.js";
import Model3DPreview from "./Model3DPreview.jsx";

const CATEGORY_OPTIONS = [
  { key: "user-uploads", label: "用户作品（默认）" },
  { key: "home", label: "家居" },
  { key: "collectibles", label: "收藏" },
  { key: "digital", label: "数码" },
  { key: "toys", label: "玩具" },
  { key: "fresh", label: "生鲜" },
  { key: "apparel", label: "服装" },
];

const STATUS_LABELS = {
  queued: "排队中",
  running: "生成中",
  success: "已完成",
  failed: "失败",
};

/**
 * 图生 3D 面板：单图上传 -> 选 Provider -> 实时进度 -> 预览 GLB
 *
 * 设计目标：让商家用一张商品图，10-30 秒内得到可旋转的 3D 资产。
 * 默认走 mock，配置 TRIPO_API_KEY 后自动切真实 provider。
 */
export default function ImageTo3DPanel({ onResolved }) {
  const [file, setFile] = useState(null);
  const [previewSrc, setPreviewSrc] = useState(null);
  const [providers, setProviders] = useState({
    default: "mock",
    available: ["mock"],
    tripo_configured: false,
  });
  const [provider, setProvider] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [job, setJob] = useState(null);
  const fileInputRef = useRef(null);

  // 上架表单
  const [showPublishForm, setShowPublishForm] = useState(false);
  const [publishName, setPublishName] = useState("");
  const [publishDescription, setPublishDescription] = useState("");
  const [publishPrice, setPublishPrice] = useState("");
  const [publishCategory, setPublishCategory] = useState("user-uploads");
  const [publishStock, setPublishStock] = useState("1");
  const [publishing, setPublishing] = useState(false);
  const [publishMsg, setPublishMsg] = useState(null);

  useEffect(() => {
    getImage3DProviders()
      .then((r) => {
        setProviders(r);
        setProvider(""); // 空字符串 = 用服务器默认
      })
      .catch(() => {});
  }, []);

  // 轮询 job 状态
  useEffect(() => {
    if (!job?.job_id) return;
    if (job.status === "success" || job.status === "failed") return;
    const t = setInterval(async () => {
      try {
        const r = await getJob(job.job_id);
        setJob(r);
        if (r.status === "success" || r.status === "failed") {
          clearInterval(t);
          if (r.status === "success" && onResolved) onResolved(r);
        }
      } catch (e) {
        // ignore transient
      }
    }, 1500);
    return () => clearInterval(t);
  }, [job?.job_id, job?.status, onResolved]);

  const handleFileChange = (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    setFile(f);
    setError(null);
    if (previewSrc) URL.revokeObjectURL(previewSrc);
    setPreviewSrc(URL.createObjectURL(f));
  };

  const handleSubmit = async () => {
    if (!file) {
      setError("请先选择一张图片");
      return;
    }
    setSubmitting(true);
    setError(null);
    setJob(null);
    try {
      const resp = await createImage3DJob({
        image: file,
        provider: provider || undefined,
      });
      setJob({ job_id: resp.job_id, status: "queued", progress: 0, stage: "received" });
    } catch (e) {
      setError(e.message || String(e));
    } finally {
      setSubmitting(false);
    }
  };

  const handleReset = () => {
    if (previewSrc) URL.revokeObjectURL(previewSrc);
    setFile(null);
    setPreviewSrc(null);
    setJob(null);
    setError(null);
    setShowPublishForm(false);
    setPublishMsg(null);
    setPublishName("");
    setPublishDescription("");
    setPublishPrice("");
    setPublishCategory("user-uploads");
    setPublishStock("1");
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handlePublish = async () => {
    if (!job?.job_id) return;
    setPublishing(true);
    setPublishMsg(null);
    try {
      const payload = {};
      if (publishName.trim()) payload.name = publishName.trim();
      if (publishDescription.trim()) payload.description = publishDescription.trim();
      if (publishPrice && !Number.isNaN(Number(publishPrice))) {
        payload.price = Number(publishPrice);
      }
      if (publishCategory) payload.category = publishCategory;
      if (publishStock && !Number.isNaN(Number(publishStock))) {
        payload.stock = Number(publishStock);
      }
      const result = await publishJobAsProduct(job.job_id, payload);
      setPublishMsg({
        ok: true,
        text: `已上架：${result.name}，可在商城分类「${publishCategory}」中查看`,
        productId: result.id,
      });
    } catch (e) {
      setPublishMsg({ ok: false, text: e.message || String(e) });
    } finally {
      setPublishing(false);
    }
  };

  const glbUrl = job?.outputs?.preview_url || null;
  const progress = Math.round((job?.progress || 0) * 100);
  const isProcessing = job && job.status !== "success" && job.status !== "failed";
  const providerLabel = (p) => {
    if (!p) return "自动选择";
    if (p === "mock") return "快速预览";
    if (p === "tripo") return providers.tripo_configured
      ? "高质量生成"
      : "快速预览";
    return p;
  };

  return (
    <div className="image-to-3d-panel">
      <div className="form-grid two-col">
        <div className="form-col image-result-column">
          <label className="form-label">商品图片</label>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/png,image/jpeg,image/webp,image/bmp"
            onChange={handleFileChange}
            disabled={submitting || isProcessing}
          />
          {previewSrc && (
            <div className="image-preview">
              <img src={previewSrc} alt="upload preview" />
            </div>
          )}

          <label className="form-label" style={{ marginTop: 12 }}>生成方式</label>
          <select
            value={provider}
            onChange={(e) => setProvider(e.target.value)}
            disabled={submitting || isProcessing}
          >
            <option value="">{providerLabel("")}</option>
            {providers.available.map((p) => (
              <option key={p} value={p}>{providerLabel(p)}</option>
            ))}
          </select>

          <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
            <button
              className="primary"
              onClick={handleSubmit}
              disabled={!file || submitting || isProcessing}
            >
              {submitting ? "提交中…" : isProcessing ? "生成中…" : "开始生成 3D"}
            </button>
            <button className="secondary" onClick={handleReset} disabled={submitting}>
              重置
            </button>
          </div>

          {error && <div className="error-message">{error}</div>}
        </div>

        <div className="form-col">
          <label className="form-label">3D 结果</label>
          {!job && (
            <div className="placeholder-box">
              <p>上传商品图后，即可生成可旋转的 3D 展示资产。</p>
              <p className="hint">建议使用主体清晰、背景干净、边缘完整的商品图。</p>
            </div>
          )}

          {job && (
            <div className="job-progress">
              <div className="job-progress-header">
                <span className={`tag ${job.status}`}>{STATUS_LABELS[job.status] || job.status}</span>
                <span className="muted">{job.stage}</span>
                <span style={{ marginLeft: "auto" }}>{progress}%</span>
              </div>
              <div className="progress-bar">
                <div className="progress-bar-fill" style={{ width: `${progress}%` }} />
              </div>
              {job.error && <p className="error-message">{job.error}</p>}
            </div>
          )}

          {glbUrl && job?.status === "success" && (
            <div className="generation-result-viewer">
              <Model3DPreview src={glbUrl} alt="generated 3d" height={480} />
              <div className="publish-actions">
                {!showPublishForm && !publishMsg?.ok && (
                  <button className="primary" onClick={() => setShowPublishForm(true)}>
                    上架到商品库
                  </button>
                )}
                <a className="secondary" href={glbUrl} download>
                  下载 GLB
                </a>
              </div>

              {showPublishForm && !publishMsg?.ok && (
                <div className="publish-form">
                  <label className="form-label">商品名称（可选，默认自动命名）</label>
                  <input
                    type="text"
                    value={publishName}
                    onChange={(e) => setPublishName(e.target.value)}
                    placeholder="例如：轻奢陶瓷香薰摆件"
                  />
                  <label className="form-label">商品简介（可选）</label>
                  <textarea
                    value={publishDescription}
                    onChange={(e) => setPublishDescription(e.target.value)}
                    rows={4}
                    placeholder="补充材质、尺寸、适用场景或卖点。留空时会使用系统自动生成的简介。"
                  />
                  <div className="publish-row">
                    <div>
                      <label className="form-label">售价（元）</label>
                      <input
                        type="number"
                        min="0"
                        step="0.01"
                        value={publishPrice}
                        onChange={(e) => setPublishPrice(e.target.value)}
                        placeholder="0"
                      />
                    </div>
                    <div>
                      <label className="form-label">库存</label>
                      <input
                        type="number"
                        min="0"
                        step="1"
                        value={publishStock}
                        onChange={(e) => setPublishStock(e.target.value)}
                      />
                    </div>
                  </div>
                  <label className="form-label">分类</label>
                  <select
                    value={publishCategory}
                    onChange={(e) => setPublishCategory(e.target.value)}
                  >
                    {CATEGORY_OPTIONS.map((c) => (
                      <option key={c.key} value={c.key}>{c.label}</option>
                    ))}
                  </select>
                  <div className="publish-actions">
                    <button
                      className="primary"
                      onClick={handlePublish}
                      disabled={publishing}
                    >
                      {publishing ? "上架中…" : "确认上架"}
                    </button>
                    <button
                      className="secondary"
                      onClick={() => setShowPublishForm(false)}
                      disabled={publishing}
                    >
                      取消
                    </button>
                  </div>
                </div>
              )}

              {publishMsg && (
                <div className={publishMsg.ok ? "publish-success" : "error-message"}>
                  {publishMsg.text}
                  {publishMsg.ok && publishMsg.productId && (
                    <a
                      href={`#/shop/${encodeURIComponent(publishMsg.productId)}`}
                      style={{ marginLeft: 10 }}
                    >
                      查看商品详情 →
                    </a>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
