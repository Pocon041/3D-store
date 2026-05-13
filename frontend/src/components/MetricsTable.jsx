import React from "react";

const ROWS = [
  { key: "num_input_files", label: "输入文件数量" },
  { key: "raw_size_mb", label: "原始输入大小 (MB)" },
  { key: "process_time_sec", label: "数据处理耗时 (s)" },
  { key: "train_time_sec", label: "训练耗时 (s)" },
  { key: "convert_time_sec", label: "GLB 转换耗时 (s)" },
  { key: "splat_size_mb", label: "Splat 文件大小 (MB)" },
  { key: "obj_size_mb", label: "OBJ 文件大小 (MB)" },
  { key: "glb_size_mb", label: "GLB 大小 (MB)" },
  { key: "optimized_glb_size_mb", label: "优化后 GLB (MB)" },
  { key: "compression_ratio", label: "压缩率（1 - after/before）" },
];

export default function MetricsTable({ metrics }) {
  if (!metrics) {
    return <div style={{ color: "#888" }}>暂无指标，等待任务完成…</div>;
  }
  return (
    <table className="metrics-table">
      <thead>
        <tr>
          <th>指标</th>
          <th>数值</th>
        </tr>
      </thead>
      <tbody>
        {ROWS.map((row) => (
          <tr key={row.key}>
            <td>{row.label}</td>
            <td>{metrics[row.key] ?? "-"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
