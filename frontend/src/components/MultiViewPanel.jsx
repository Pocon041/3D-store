import React, { useEffect, useRef, useState } from "react";
import {
  createMultiView3DJob,
  getImage3DProviders,
  getJob,
} from "../api.js";
import JobResultCard from "./JobResultCard.jsx";

/**
 * 多视角图生 3D 面板：4 个视图槽位 + Tripo multiview_to_model（或 mock）。
 *
 * 视图顺序按 Tripo 官方约定：[front, back, left, right]。
 * front 必填，其余三个可选。多张视图能显著提升几何与贴图质量。
 */
const VIEW_SLOTS = [
  { key: "front", label: "正面", hint: "必填，主视图" },
  { key: "back",  label: "背面", hint: "可选" },
  { key: "left",  label: "左侧", hint: "可选" },
  { key: "right", label: "右侧", hint: "可选" },
];

export default function MultiViewPanel({ onResolved }) {
  const [slots, setSlots] = useState(() => VIEW_SLOTS.map(() => null));
  const [previews, setPreviews] = useState(() => VIEW_SLOTS.map(() => null));
  const [providers, setProviders] = useState({
    default: "mock",
    available: ["mock"],
    tripo_configured: false,
  });
  const [provider, setProvider] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [job, setJob] = useState(null);

  const fileInputs = useRef(VIEW_SLOTS.map(() => null));

  useEffect(() => {
    getImage3DProviders().then(setProviders).catch(() => {});
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
      } catch { /* ignore */ }
    }, 1500);
    return () => clearInterval(t);
  }, [job?.job_id, job?.status, onResolved]);

  // 清理 object URL，避免内存泄漏
  useEffect(() => () => {
    previews.forEach((p) => p && URL.revokeObjectURL(p));
  }, []);

  const handlePick = (idx) => (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setError(null);
    setSlots((prev) => {
      const next = [...prev];
      next[idx] = file;
      return next;
    });
    setPreviews((prev) => {
      const next = [...prev];
      if (next[idx]) URL.revokeObjectURL(next[idx]);
      next[idx] = URL.createObjectURL(file);
      return next;
    });
  };

  const handleClear = (idx) => () => {
    setSlots((prev) => {
      const next = [...prev];
      next[idx] = null;
      return next;
    });
    setPreviews((prev) => {
      const next = [...prev];
      if (next[idx]) URL.revokeObjectURL(next[idx]);
      next[idx] = null;
      return next;
    });
    if (fileInputs.current[idx]) fileInputs.current[idx].value = "";
  };

  const handleSubmit = async () => {
    const images = slots.filter(Boolean);
    if (!images.length) {
      setError("至少选择 1 张图（建议至少传正面 + 背面）");
      return;
    }
    if (!slots[0]) {
      setError("第一个槽位（正面）必须填，Tripo multiview 用它做主视图");
      return;
    }
    setSubmitting(true);
    setError(null);
    setJob(null);
    try {
      // 注意：按 slot 顺序传，None 槽位不上传，但前端要保证 front 在第一个
      const ordered = slots.filter(Boolean);
      const resp = await createMultiView3DJob({ images: ordered, provider: provider || undefined });
      setJob({
        job_id: resp.job_id,
        status: "queued",
        progress: 0,
        stage: "received",
        params: { kind: "multiview", num_views: ordered.length },
      });
    } catch (e) {
      setError(e.message || String(e));
    } finally {
      setSubmitting(false);
    }
  };

  const handleReset = () => {
    previews.forEach((p) => p && URL.revokeObjectURL(p));
    setSlots(VIEW_SLOTS.map(() => null));
    setPreviews(VIEW_SLOTS.map(() => null));
    setJob(null);
    setError(null);
    fileInputs.current.forEach((el) => { if (el) el.value = ""; });
  };

  const providerLabel = (p) => {
    if (!p) return "自动选择";
    if (p === "mock") return "快速预览";
    if (p === "tripo") return providers.tripo_configured
      ? "高质量生成"
      : "快速预览";
    return p;
  };

  const filledCount = slots.filter(Boolean).length;
  const isProcessing = job && job.status !== "success" && job.status !== "failed";
  const disableSubmit = !filledCount || submitting || isProcessing;

  return (
    <div className="multiview-panel">
      <div className="multiview-workspace">
        <div className="multiview-upload-area">
          <div className="multiview-upload-head">
            <div>
              <strong>视图素材</strong>
              <span>正面必填，建议补充背面与左右侧</span>
            </div>
            <span className="view-count-pill">{filledCount}/4</span>
          </div>

          <div className="view-grid view-grid-2x2">
            {VIEW_SLOTS.map((slot, idx) => (
              <ViewSlot
                key={slot.key}
                slot={slot}
                file={slots[idx]}
                preview={previews[idx]}
                disabled={submitting || isProcessing}
                onPick={handlePick(idx)}
                onClear={handleClear(idx)}
                inputRef={(el) => { fileInputs.current[idx] = el; }}
              />
            ))}
          </div>
        </div>

        <aside className="multiview-side">
          <div className="multiview-side-card">
            <div className="multiview-side-title">生成设置</div>
            <div className="multiview-provider">
              <label className="form-label">生成方式</label>
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
            </div>

            <div className="multiview-actions">
              <button
                className="primary"
                onClick={handleSubmit}
                disabled={disableSubmit}
              >
                {submitting ? "提交中…" : isProcessing
                  ? "生成中…"
                  : `生成 3D（${filledCount} 视图）`}
              </button>
              <button className="secondary" onClick={handleReset} disabled={submitting}>
                重置
              </button>
            </div>
          </div>

          <div className="multiview-tips">
            <span className={slots[0] ? "ready" : ""}>正面视图</span>
            <span className={filledCount >= 2 ? "ready" : ""}>几何补全</span>
            <span className={filledCount >= 4 ? "ready" : ""}>贴图更稳</span>
          </div>

          <p className="hint">
            视图越多，商品轮廓、背面细节和材质连续性越稳定。建议至少提供正面和背面。
          </p>
        </aside>
      </div>

      {error && <div className="error-message">{error}</div>}

      {job && (
        <div style={{ marginTop: 16 }}>
          <JobResultCard
            job={job}
            onPublished={() => onResolved && onResolved(job)}
            onClose={() => setJob(null)}
          />
        </div>
      )}

    </div>
  );
}

function ViewSlot({ slot, file, preview, disabled, onPick, onClear, inputRef }) {
  const idAttr = `mv-${slot.key}`;
  return (
    <label htmlFor={idAttr} className={`view-slot ${preview ? "filled" : "empty"}`}>
      <input
        id={idAttr}
        ref={inputRef}
        type="file"
        accept="image/png,image/jpeg,image/webp,image/bmp"
        onChange={onPick}
        disabled={disabled}
      />
      <div className="view-slot-header">
        <span className="view-slot-label">{slot.label}</span>
        <span className="view-slot-hint">{slot.hint}</span>
      </div>
      <div className="view-slot-body">
        {preview ? (
          <img src={preview} alt={slot.label} />
        ) : (
          <div className="view-slot-empty">
            <span>点击或拖拽上传</span>
          </div>
        )}
      </div>
      {file && (
        <div className="view-slot-footer">
          <span className="view-slot-filename">{file.name}</span>
          <button
            type="button"
            className="link"
            onClick={(e) => { e.preventDefault(); onClear(); }}
            disabled={disabled}
          >
            移除
          </button>
        </div>
      )}
    </label>
  );
}
