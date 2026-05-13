import React from "react";

// model-viewer 是 web component，React 无法直接识别 prop，写在 JSX 里要用属性形式
export default function ModelViewer({ src, poster, height = 480 }) {
  if (!src) {
    return (
      <div className="viewer-box" style={{ height }}>
        暂无模型，先创建一个重建任务
      </div>
    );
  }
  return (
    <model-viewer
      src={src}
      poster={poster}
      camera-controls=""
      auto-rotate=""
      ar=""
      shadow-intensity="1"
      exposure="0.9"
      style={{ width: "100%", height: `${height}px`, background: "#181818", borderRadius: 8 }}
    />
  );
}
