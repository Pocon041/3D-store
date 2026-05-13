import React, { useEffect, useState } from "react";
import Upload3D from "../components/Upload3D.jsx";
import JobStatus from "../components/JobStatus.jsx";
import TryOnPanel from "../components/TryOnPanel.jsx";
import MetricsTable from "../components/MetricsTable.jsx";
import ImageTo3DPanel from "../components/ImageTo3DPanel.jsx";
import MultiViewPanel from "../components/MultiViewPanel.jsx";
import JobResultCard from "../components/JobResultCard.jsx";
import { health, listJobs, getJob } from "../api.js";

export default function Studio() {
  const [backendOk, setBackendOk] = useState(null);
  const [jobId, setJobId] = useState(null);
  const [job, setJob] = useState(null);
  const [recentJobs, setRecentJobs] = useState([]);

  useEffect(() => {
    health()
      .then((r) => setBackendOk(r?.status === "ok"))
      .catch(() => setBackendOk(false));
  }, []);

  const refreshRecent = async () => {
    try {
      const list = await listJobs(10);
      setRecentJobs(list);
    } catch {
      // ignore
    }
  };

  useEffect(() => {
    refreshRecent();
    const id = setInterval(refreshRecent, 5000);
    return () => clearInterval(id);
  }, []);

  const handleResolved = async (r) => {
    setJob(r);
  };

  const handleSelectJob = async (jid) => {
    setJobId(jid);
    try {
      const r = await getJob(jid);
      setJob(r);
    } catch {
      setJob(null);
    }
  };

  // 选中任务若仍在运行，每 1.5s 拉一次状态；终态则停止
  useEffect(() => {
    if (!jobId || !job) return;
    if (job.status === "success" || job.status === "failed") return;
    const t = setInterval(async () => {
      try {
        const r = await getJob(jobId);
        setJob(r);
        if (r.status === "success" || r.status === "failed") clearInterval(t);
      } catch { /* ignore */ }
    }, 1500);
    return () => clearInterval(t);
  }, [jobId, job?.status]);

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>商家工作台</h1>
          <p>上传商品多视角图或视频，平台自动生成可旋转的 3D 资产。完成后可直接在商城上架。</p>
        </div>
        <div className="status-pill">
          后端：
          {backendOk === null ? "检测中…" : backendOk ?
            <span className="tag success">在线</span> :
            <span className="tag failed">离线</span>}
        </div>
      </header>

      <section className="section">
        <h2>图生 3D（推荐）</h2>
        <p className="desc">
          上传一张商品图，<strong>10-30 秒</strong>生成可旋转的 3D 模型。
          默认 mock，配置 <code>TRIPO_API_KEY</code> 后自动调用 Tripo3D 真实生成。
        </p>
        <ImageTo3DPanel onResolved={(r) => { setJobId(r.job_id); setJob(r); refreshRecent(); }} />
      </section>

      <section className="section">
        <h2>多视角生 3D</h2>
        <p className="desc">
          上传 <strong>1-4 张</strong>同一物体的不同角度图（建议正面 + 背面 + 侧面），
          走 Tripo <code>multiview_to_model</code> 真实生成单个 PBR GLB；
          视图越多，几何越准确。
        </p>
        <MultiViewPanel
          onResolved={(r) => { setJobId(r.job_id); setJob(r); refreshRecent(); }}
        />

        <details className="advanced-mode">
          <summary>高级模式：NeRF / 3DGS（需 GPU + Nerfstudio）</summary>
          <p className="desc">支持多张图片或环绕视频。无 GPU 可勾选 mock 跑通流程。</p>
          <Upload3D onJobCreated={(jid) => { setJobId(jid); setJob(null); }} />
          {jobId && (
            <div style={{ marginTop: 16 }}>
              <JobStatus jobId={jobId} onResolved={handleResolved} />
            </div>
          )}
        </details>
      </section>

      <section className="section">
        <h2>二维虚拟试穿</h2>
        <p className="desc">上传人像和服装图，调用 CatVTON（或 mock）生成对比图。</p>
        <TryOnPanel />
      </section>

      {job && (
        <section className="section selected-job-section">
          <div className="section-header-row">
            <h2>任务详情</h2>
            <button className="link" onClick={() => { setJobId(null); setJob(null); }}>
              关闭 ×
            </button>
          </div>
          <p className="desc">3D 预览、上架与下载操作集中在这里；任务仍在运行时会自动刷新。</p>
          <JobResultCard
            job={job}
            onPublished={() => refreshRecent()}
            onClose={() => { setJobId(null); setJob(null); }}
          />
          {job.metrics && (
            <div style={{ marginTop: 16 }}>
              <h3 style={{ marginBottom: 8, fontSize: 14, color: "#555" }}>实验指标</h3>
              <MetricsTable metrics={job.metrics} />
            </div>
          )}
        </section>
      )}

      <section className="section">
        <h2>历史任务</h2>
        <p className="desc">
          最近 10 条任务。点「查看」展开 3D 预览与一键上架；图生 3D / 重建成功的任务可以挂到商城任意分类。
        </p>
        <table className="metrics-table">
          <thead>
            <tr>
              <th>job_id</th>
              <th>类型</th>
              <th>状态</th>
              <th>阶段</th>
              <th>更新时间</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {recentJobs.length === 0 && (
              <tr><td colSpan={6} style={{ color: "#888" }}>暂无任务</td></tr>
            )}
            {recentJobs.map((j) => (
              <tr key={j.job_id}>
                <td style={{ fontFamily: "monospace" }}>{j.job_id}</td>
                <td>{j.task_type}</td>
                <td><span className={`tag ${j.status}`}>{j.status}</span></td>
                <td>{j.stage}</td>
                <td>{j.updated_at}</td>
                <td>
                  <button className="secondary" onClick={() => handleSelectJob(j.job_id)}>查看</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
