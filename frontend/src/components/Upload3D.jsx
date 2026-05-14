import React, { useState } from "react";
import { createReconstructJob } from "../api.js";

const QUALITY_OPTIONS = [
  { value: "fast", label: "快速" },
  { value: "balanced", label: "均衡" },
  { value: "high", label: "精细" },
];

export default function Upload3D({ onJobCreated }) {
  const [files, setFiles] = useState([]);
  const [mode, setMode] = useState("images");
  const [quality, setQuality] = useState("fast");
  const [exportGlb, setExportGlb] = useState(true);
  const [mock, setMock] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const onSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    if (!files.length) {
      setError("请选择至少一个文件");
      return;
    }
    if (mode === "video" && files.length !== 1) {
      setError("环绕视频模式只能上传单个视频");
      return;
    }
    setSubmitting(true);
    try {
      const r = await createReconstructJob({ files, mode, quality, exportGlb, mock });
      if (onJobCreated) onJobCreated(r.job_id);
    } catch (e) {
      setError(String(e));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={onSubmit}>
      <div className="row">
        <div className="col">
          <div className="field">
            <label>输入模式</label>
            <select value={mode} onChange={(e) => setMode(e.target.value)}>
              <option value="images">多张图片</option>
              <option value="video">环绕视频</option>
            </select>
          </div>
          <div className="field">
            <label>{mode === "images" ? "选择图片（可多选）" : "选择视频文件"}</label>
            <input
              type="file"
              multiple={mode === "images"}
              accept={mode === "images" ? "image/*" : "video/*"}
              onChange={(e) => setFiles(Array.from(e.target.files || []))}
            />
            <div style={{ fontSize: 12, color: "#888", marginTop: 4 }}>
              已选择 {files.length} 个文件
            </div>
          </div>
        </div>
        <div className="col">
          <div className="field">
            <label>质量档位</label>
            <select value={quality} onChange={(e) => setQuality(e.target.value)}>
              {QUALITY_OPTIONS.map((o) => (
                <option value={o.value} key={o.value}>{o.label}</option>
              ))}
            </select>
          </div>
          <div className="field-inline">
            <input
              id="exportGlb"
              type="checkbox"
              checked={exportGlb}
              onChange={(e) => setExportGlb(e.target.checked)}
            />
            <label htmlFor="exportGlb">生成可上架 3D 文件</label>
          </div>
          <div className="field-inline">
            <input
              id="mock"
              type="checkbox"
              checked={mock}
              onChange={(e) => setMock(e.target.checked)}
            />
            <label htmlFor="mock">快速预览模式</label>
          </div>
        </div>
      </div>
      <button className="primary" type="submit" disabled={submitting}>
        {submitting ? "提交中…" : "开始重建"}
      </button>
      {error && <div style={{ color: "#b6212c", marginTop: 8 }}>{error}</div>}
    </form>
  );
}
