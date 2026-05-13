import { useEffect, useState } from "react";

// 极简 hash 路由：避免引入 react-router 带来的额外依赖
// 路由形式：#/shop  #/shop/<id>  #/studio  #/cart  #/  (重定向到 #/shop)

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

export function navigate(path) {
  if (!path.startsWith("/")) path = "/" + path;
  window.location.hash = "#" + path;
}
