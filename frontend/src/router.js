import { useEffect, useState } from "react";

// 极简 hash 路由：避免引入 react-router 带来的额外依赖
// 路由形式：#/shop  #/shop/<id>  #/studio  #/cart  #/  (重定向到 #/shop)
const PREV_ROUTE_KEY = "aigc3d_prev_route";

export function useHashRoute() {
  const [path, setPath] = useState(() => normalize(window.location.hash));
  useEffect(() => {
    const onHash = () => setPath(normalize(window.location.hash));
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);
  return path;
}

function normalize(hash) {
  if (!hash || hash === "#" || hash === "#/") return "/shop";
  if (hash.startsWith("#")) return hash.slice(1);
  return hash;
}

export function currentPath() {
  return normalize(window.location.hash);
}

export function navigate(path) {
  if (!path.startsWith("/")) path = "/" + path;
  const current = currentPath();
  if (current !== path) {
    sessionStorage.setItem(PREV_ROUTE_KEY, current);
  }
  window.location.hash = "#" + path;
}

export function goBack(fallback = "/shop") {
  const current = currentPath();
  const previous = sessionStorage.getItem(PREV_ROUTE_KEY);
  if (previous && previous !== current) {
    navigate(previous);
    return;
  }
  if (window.history.length > 1) {
    window.history.back();
    return;
  }
  navigate(fallback);
}
