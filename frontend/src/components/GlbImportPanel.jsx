import React, { useEffect, useRef, useState } from "react";
import { createGlbImportJob, getJob } from "../api.js";
import Model3DPreview from "./Model3DPreview.jsx";

const SLOT_OPTIONS = [
  { key: "upper", label: "上装" },
  { key: "lower", label: "下装" },
  { key: "full", label: "连衣裙/全身" },
  { key: "shoes", label: "鞋子" },
];

const STATUS_LABELS = {
  queued: "排队中",
  running: "处理中",
  success: "已完成",
  failed: "失败",
};

export default function GlbImportPanel({ onResolved }) {
  const fileInputRef = useRef(null);
  const [file, setFile] = useState(null);
  const [name, setName] = useState("");
  const [price, setPrice] = useState("");
  const [stock, setStock] = useState("1");
  const [garmentSlot, setGarmentSlot] = useState("upper");
  const [job, setJob] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!job?.job_id) return undefined;
    if (job.status === "success" || job.status === "failed") return undefined;
    const timer = setInterval(async () => {
      try {
        const next = await getJob(job.job_id);
        setJob(next);
        if (next.status === "success" || next.status === "failed") {
          clearInterval(timer);
          if (next.status === "success" && onResolved) onResolved(next);
        }
      } catch {
        // ignore transient polling errors
      }
    }, 1200);
    return () => clearInterval(timer);
  }, [job?.job_id, job?.status, onResolved]);

  const handleFile = (e) => {
    const next = e.target.files?.[0] || null;
    setFile(next);
    setError(null);
    if (next && !name.trim()) {
      setName(next.name.replace(/\.[^.]+$/, ""));
    }
  };

  const handleSubmit = async () => {
    if (!file) {
      setError("请先选择一个 GLB 文件");
      return;
    }
    setSubmitting(true);
    setError(null);
    setJob(null);
    try {
      const created = await createGlbImportJob({
        model: file,
        name: name.trim() || undefined,
        price,
        stock,
        category: "apparel",
        garmentSlot,
      });
      setJob({ job_id: created.job_id, status: "queued", progress: 0, stage: "received" });
    } catch (e) {
      setError(e.message || String(e));
    } finally {
      setSubmitting(false);
    }
  };

  const reset = () => {
    setFile(null);
    setName("");
    setPrice("");
    setStock("1");
    setGarmentSlot("upper");
    setJob(null);
    setError(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const glbUrl = job?.outputs?.preview_url || null;
  const productId = job?.job_id ? `job-${job.job_id}` : null;
  const progress = Math.round((job?.progress || 0) * 100);
  const busy = submitting || (job && job.status !== "success" && job.status !== "failed");

  return (
    <div className="image-to-3d-panel glb-import-panel">
      <div className="form-grid two-col">
        <div className="form-col image-result-column">
          <label className="form-label">GLB 模型</label>
          <input
            ref={fileInputRef}
            type="file"
            accept=".glb,model/gltf-binary"
            onChange={handleFile}
            disabled={busy}
          />

          <label className="form-label" style={{ marginTop: 12 }}>商品名称</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="例如：羽绒服上装"
            disabled={busy}
          />

          <div className="publish-row">
            <div>
              <label className="form-label">服装位置</label>
              <select value={garmentSlot} onChange={(e) => setGarmentSlot(e.target.value)} disabled={busy}>
                {SLOT_OPTIONS.map((slot) => (
                  <option key={slot.key} value={slot.key}>{slot.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="form-label">库存</label>
              <input
                type="number"
                min="0"
                step="1"
                value={stock}
                onChange={(e) => setStock(e.target.value)}
                disabled={busy}
              />
            </div>
          </div>

          <label className="form-label">售价（元）</label>
          <input
            type="number"
            min="0"
            step="0.01"
            value={price}
            onChange={(e) => setPrice(e.target.value)}
            placeholder="0"
            disabled={busy}
          />

          <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
            <button className="primary" onClick={handleSubmit} disabled={!file || busy}>
              {busy ? "导入中..." : "导入并上架"}
            </button>
            <button className="secondary" onClick={reset} disabled={submitting}>
              重置
            </button>
          </div>

          {error && <div className="error-message">{error}</div>}
        </div>

        <div className="form-col">
          <label className="form-label">导入结果</label>
          {!job && (
            <div className="placeholder-box">
              <p>上传已有 GLB 后，系统会保存模型、渲染缩略图，并同步加入服装商品库。</p>
              <p className="hint">完成后可直接进入 3D 换装页，商品会按服装位置自动选中。</p>
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

          {job?.status === "success" && glbUrl && (
            <div className="generation-result-viewer">
              <Model3DPreview src={glbUrl} poster={job.outputs?.thumbnail_url} alt={job.job_id} height={420} />
              <div className="publish-actions">
                <a className="primary" href={`#/avatar-tryon?product=${encodeURIComponent(productId)}`}>
                  在人台预览
                </a>
                <a className="secondary" href={`#/shop/${encodeURIComponent(productId)}`}>
                  查看商品
                </a>
                <a className="secondary" href={glbUrl} download>
                  下载 GLB
                </a>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
