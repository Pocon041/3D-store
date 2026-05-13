import React, { useState } from "react";
import { createTryOnJob } from "../api.js";
import JobStatus from "./JobStatus.jsx";

export default function TryOnPanel() {
  const [personImage, setPersonImage] = useState(null);
  const [garmentImage, setGarmentImage] = useState(null);
  const [category, setCategory] = useState("upper");
  const [mock, setMock] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [jobId, setJobId] = useState(null);
  const [result, setResult] = useState(null);

  const personPreview = personImage ? URL.createObjectURL(personImage) : null;
  const garmentPreview = garmentImage ? URL.createObjectURL(garmentImage) : null;
  const resultUrl = result?.outputs?.preview_url
    || (result?.outputs?.tryon_result ? `/static/jobs/${result.job_id}/tryon/result.png` : null);
  const compareUrl = result?.outputs?.tryon_compare
    ? `/static/jobs/${result.job_id}/tryon/compare.png`
    : null;

  const onSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    if (!personImage || !garmentImage) {
      setError("请同时选择人像图和服装图");
      return;
    }
    setSubmitting(true);
    setResult(null);
    try {
      const r = await createTryOnJob({ personImage, garmentImage, category, mock });
      setJobId(r.job_id);
    } catch (e) {
      setError(String(e));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div>
      <form onSubmit={onSubmit}>
        <div className="row">
          <div className="col">
            <div className="field">
              <label>人像图</label>
              <input type="file" accept="image/*"
                     onChange={(e) => setPersonImage(e.target.files?.[0] || null)} />
            </div>
            <div className="field">
              <label>服装图</label>
              <input type="file" accept="image/*"
                     onChange={(e) => setGarmentImage(e.target.files?.[0] || null)} />
            </div>
          </div>
          <div className="col">
            <div className="field">
              <label>服装类别</label>
              <select value={category} onChange={(e) => setCategory(e.target.value)}>
                <option value="upper">上装 upper</option>
                <option value="lower">下装 lower</option>
                <option value="dress">连衣裙 dress</option>
              </select>
            </div>
            <div className="field-inline">
              <input id="tryon-mock" type="checkbox"
                     checked={mock}
                     onChange={(e) => setMock(e.target.checked)} />
              <label htmlFor="tryon-mock">使用 mock 模式（无 CatVTON 时也能跑通）</label>
            </div>
          </div>
        </div>
        <button className="primary" type="submit" disabled={submitting}>
          {submitting ? "提交中…" : "生成试穿图"}
        </button>
        {error && <div style={{ color: "#b6212c", marginTop: 8 }}>{error}</div>}
      </form>

      {jobId && (
        <div style={{ marginTop: 16 }}>
          <JobStatus jobId={jobId} onResolved={setResult} />
        </div>
      )}

      <div className="tryon-grid" style={{ marginTop: 16 }}>
        <div>
          <div className="label">人像</div>
          {personPreview ? <img src={personPreview} alt="person" /> : <div className="viewer-box" style={{ height: 240 }}>未选择</div>}
        </div>
        <div>
          <div className="label">服装</div>
          {garmentPreview ? <img src={garmentPreview} alt="garment" /> : <div className="viewer-box" style={{ height: 240 }}>未选择</div>}
        </div>
        <div>
          <div className="label">试穿结果</div>
          {resultUrl ? (
            <>
              <img src={resultUrl} alt="result" />
              <div className="job-result-actions" style={{ marginTop: 10 }}>
                <a className="secondary" href={resultUrl} target="_blank" rel="noreferrer">打开结果</a>
                {compareUrl && (
                  <a className="secondary" href={compareUrl} target="_blank" rel="noreferrer">查看对比图</a>
                )}
              </div>
            </>
          ) : (
            <div className="viewer-box" style={{ height: 240 }}>等待生成</div>
          )}
        </div>
      </div>
    </div>
  );
}
