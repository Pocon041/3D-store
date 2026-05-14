import React, { useEffect, useState } from "react";
import { publishJobAsProduct } from "../api.js";
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

const TASK_LABELS = {
  image_to_3d: "单图生成",
  reconstruct: "高级重建",
  tryon: "虚拟试穿",
};

const STATUS_LABELS = {
  queued: "排队中",
  running: "生成中",
  success: "已完成",
  failed: "失败",
};

/**
 * 已完成任务的详情卡片：3D 预览 + 上架表单 + 下载入口。
 *
 * 用于 Studio 历史任务点"查看"时展示，也可以被 ImageTo3DPanel 复用。
 *
 * Props:
 *   - job: JobRecord (来自 /api/jobs/{id})
 *   - onPublished?: (productId) => void
 *   - onClose?: () => void
 */
export default function JobResultCard({ job, onPublished, onClose }) {
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [price, setPrice] = useState("");
  const [category, setCategory] = useState("user-uploads");
  const [stock, setStock] = useState("1");
  const [publishing, setPublishing] = useState(false);
  const [msg, setMsg] = useState(null);

  // 任务切换时重置表单
  useEffect(() => {
    setShowForm(false);
    setMsg(null);
    setName("");
    setDescription("");
    setPrice("");
    setCategory("user-uploads");
    setStock("1");
  }, [job?.job_id]);

  if (!job) return null;

  const isSuccess = job.status === "success";
  const isPublishable = isSuccess && (job.task_type === "image_to_3d" || job.task_type === "reconstruct");
  const glbUrl = job.outputs?.preview_url
    || pickGlbUrl(job.job_id, job.outputs?.optimized_glb)
    || pickGlbUrl(job.job_id, job.outputs?.glb);
  const progress = Math.round((job.progress || 0) * 100);

  const handlePublish = async () => {
    setPublishing(true);
    setMsg(null);
    try {
      const payload = {};
      if (name.trim()) payload.name = name.trim();
      if (description.trim()) payload.description = description.trim();
      if (price && !Number.isNaN(Number(price))) payload.price = Number(price);
      if (category) payload.category = category;
      if (stock && !Number.isNaN(Number(stock))) payload.stock = Number(stock);
      const result = await publishJobAsProduct(job.job_id, payload);
      setMsg({
        ok: true,
        text: `已上架：${result.name}（分类「${category}」）`,
        productId: result.id,
      });
      if (onPublished) onPublished(result.id);
    } catch (e) {
      setMsg({ ok: false, text: e.message || String(e) });
    } finally {
      setPublishing(false);
    }
  };

  return (
    <div className="job-result-card">
      <div className="job-result-header">
        <div className="job-result-meta">
          <code>{job.job_id}</code>
          <span className={`tag ${job.status}`}>{STATUS_LABELS[job.status] || job.status}</span>
          <span className="muted">{TASK_LABELS[job.task_type] || job.task_type}</span>
        </div>
        {onClose && (
          <button className="link" onClick={onClose}>收起 ×</button>
        )}
      </div>

      {!isSuccess && (
        <div className="job-progress" style={{ marginTop: 10 }}>
          <div className="job-progress-header">
            <span className="muted">{job.stage}</span>
            <span style={{ marginLeft: "auto" }}>{progress}%</span>
          </div>
          <div className="progress-bar">
            <div className="progress-bar-fill" style={{ width: `${progress}%` }} />
          </div>
          {job.error && <p className="error-message">{job.error}</p>}
        </div>
      )}

      {isSuccess && glbUrl && (
        <div className="job-result-body">
          <div className="job-result-preview">
            <Model3DPreview src={glbUrl} alt={job.job_id} height={440} />
            <div className="job-result-actions">
              {isPublishable && !showForm && !msg?.ok && (
                <button className="primary" onClick={() => setShowForm(true)}>
                  上架到商品库
                </button>
              )}
              <a className="secondary" href={glbUrl} download>下载 GLB</a>
            </div>
          </div>

          {isPublishable && showForm && !msg?.ok && (
            <div className="publish-form">
              <label className="form-label">商品名称（可选，默认自动命名）</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="例如：北欧风木质边柜"
              />
              <label className="form-label">商品简介（可选）</label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={4}
                placeholder="写给顾客看的卖点说明，比如材质、尺寸、使用场景、保养方式。"
              />
              <div className="publish-row">
                <div>
                  <label className="form-label">售价（元）</label>
                  <input
                    type="number" min="0" step="0.01"
                    value={price}
                    onChange={(e) => setPrice(e.target.value)}
                    placeholder="0"
                  />
                </div>
                <div>
                  <label className="form-label">库存</label>
                  <input
                    type="number" min="0" step="1"
                    value={stock}
                    onChange={(e) => setStock(e.target.value)}
                  />
                </div>
              </div>
              <label className="form-label">分类</label>
              <select value={category} onChange={(e) => setCategory(e.target.value)}>
                {CATEGORY_OPTIONS.map((c) => (
                  <option key={c.key} value={c.key}>{c.label}</option>
                ))}
              </select>
              <div className="job-result-actions">
                <button className="primary" onClick={handlePublish} disabled={publishing}>
                  {publishing ? "上架中…" : "确认上架"}
                </button>
                <button
                  className="secondary"
                  onClick={() => setShowForm(false)}
                  disabled={publishing}
                >
                  取消
                </button>
              </div>
            </div>
          )}

          {msg && (
            <div className={msg.ok ? "publish-success" : "error-message"}>
              {msg.text}
              {msg.ok && msg.productId && (
                <a href={`#/shop/${encodeURIComponent(msg.productId)}`} style={{ marginLeft: 10 }}>
                  查看商品详情 →
                </a>
              )}
            </div>
          )}
        </div>
      )}

      {isSuccess && !glbUrl && (
        <div className="hint" style={{ marginTop: 8 }}>
          这个任务没有可预览的 3D 资产。
        </div>
      )}
    </div>
  );
}

function pickGlbUrl(jobId, abs) {
  if (!abs) return null;
  const norm = abs.replace(/\\/g, "/");
  const idx = norm.indexOf(`/${jobId}/`);
  if (idx < 0) return null;
  return `/static/jobs${norm.substring(idx)}`;
}
