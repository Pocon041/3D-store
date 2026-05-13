import React, { useEffect, useRef, useState } from "react";
import { getJob } from "../api.js";

const TERMINAL = new Set(["success", "failed"]);

export default function JobStatus({ jobId, onResolved }) {
  const [job, setJob] = useState(null);
  const [error, setError] = useState(null);
  // 用 ref 持有最新回调，避免 onResolved 每次 render 引用变化导致 effect 重订阅
  const onResolvedRef = useRef(onResolved);
  useEffect(() => {
    onResolvedRef.current = onResolved;
  }, [onResolved]);

  useEffect(() => {
    if (!jobId) return undefined;
    let timer = null;
    let cancelled = false;

    const tick = async () => {
      try {
        const r = await getJob(jobId);
        if (cancelled) return;
        setJob(r);
        if (TERMINAL.has(r.status)) {
          if (onResolvedRef.current) onResolvedRef.current(r);
          return;
        }
        timer = setTimeout(tick, 3000);
      } catch (e) {
        if (cancelled) return;
        setError(String(e));
        timer = setTimeout(tick, 5000);
      }
    };

    tick();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [jobId]);

  if (!jobId) return null;
  if (error && !job) return <div style={{ color: "#b6212c" }}>加载失败: {error}</div>;
  if (!job) return <div>加载中…</div>;

  return (
    <div>
      <div style={{ marginBottom: 8 }}>
        <span className={`tag ${job.status}`}>{job.status}</span>
        <span className="tag">{job.task_type}</span>
        {job.stage && <span className="tag">{job.stage}</span>}
        <span style={{ color: "#888", fontSize: 12, marginLeft: 6 }}>
          job_id: {job.job_id}
        </span>
      </div>
      <div style={{ fontSize: 13, color: "#444", marginBottom: 8 }}>
        进度：{Math.round((job.progress || 0) * 100)}%
        {job.error && <span style={{ color: "#b6212c", marginLeft: 12 }}>错误：{job.error}</span>}
      </div>
      {job.log_tail && job.log_tail.length > 0 && (
        <div className="log">
          {job.log_tail.slice(-12).join("\n")}
        </div>
      )}
    </div>
  );
}
