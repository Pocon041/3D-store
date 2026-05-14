import React, { useEffect, useRef, useState } from "react";

/**
 * 包裹 <model-viewer> 的组件：
 * - 监听 progress / load / error 事件，显示加载蒙层
 * - 蒙层在 load 之前一直显示，避免黑屏让用户误以为坏掉
 */
export default function Model3DPreview({
  src,
  poster,
  height = 560,
  ar = true,
  background = "#1b1b1f",
  borderRadius = 12,
}) {
  const ref = useRef(null);
  const [progress, setProgress] = useState(0);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    const el = ref.current;
    if (!el || !src) return undefined;
    setLoaded(false);
    setError(null);
    setProgress(0);

    const onProgress = (e) => {
      const r = e?.detail?.totalProgress;
      if (typeof r === "number") setProgress(r);
    };
    const onLoad = () => {
      setProgress(1);
      setLoaded(true);
    };
    const onError = (e) => {
      const msg = e?.detail?.sourceError?.message
        || e?.detail?.type
        || "模型加载失败";
      setError(String(msg));
    };

    el.addEventListener("progress", onProgress);
    el.addEventListener("load", onLoad);
    el.addEventListener("error", onError);
    return () => {
      el.removeEventListener("progress", onProgress);
      el.removeEventListener("load", onLoad);
      el.removeEventListener("error", onError);
    };
  }, [src]);

  if (!src) {
    return (
      <div className="model-shell" style={{ height, borderRadius, background }}>
        <div className="model-empty">暂无模型</div>
      </div>
    );
  }

  const showLoader = !loaded && !error;

  // model-viewer 是 web component；React 不识别非标准 prop，用 attr 形式
  const arProps = ar ? { ar: "" } : {};

  return (
    <div className="model-shell" style={{ height, borderRadius, background }}>
      <model-viewer
        ref={ref}
        src={src}
        poster={poster}
        camera-controls=""
        auto-rotate=""
        {...arProps}
        ar-modes="webxr scene-viewer quick-look"
        shadow-intensity="1.1"
        exposure="1.0"
        interaction-prompt="auto"
        loading="eager"
        style={{ width: "100%", height: "100%", background, borderRadius }}
      />
      {showLoader && (
        <div className="model-overlay">
          <div className="spinner" />
          <div className="model-overlay-text">
            模型加载中… {Math.round(progress * 100)}%
          </div>
          <div className="model-overlay-bar">
            <div className="model-overlay-bar-fill" style={{ width: `${progress * 100}%` }} />
          </div>
          <div className="model-overlay-hint">首次打开可能需要一点时间，请稍候。</div>
        </div>
      )}
      {error && (
        <div className="model-overlay error">
          <div className="model-overlay-text">加载失败</div>
          <div className="model-overlay-hint">{error}</div>
          <div className="model-overlay-hint">可尝试刷新页面，或稍后重新打开。</div>
        </div>
      )}
    </div>
  );
}
