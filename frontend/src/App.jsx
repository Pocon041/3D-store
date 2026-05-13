import React from "react";
import NavBar from "./components/NavBar.jsx";
import Shop from "./pages/Shop.jsx";
import ProductDetail from "./pages/ProductDetail.jsx";
import Studio from "./pages/Studio.jsx";
import Cart from "./pages/Cart.jsx";
import TryOn from "./pages/TryOn.jsx";
import { useHashRoute } from "./router.js";

export default function App() {
  const path = useHashRoute();

  let page;
  if (path.startsWith("/shop/")) {
    const id = decodeURIComponent(path.slice("/shop/".length));
    page = <ProductDetail productId={id} />;
  } else if (path === "/shop" || path === "/") {
    page = <Shop />;
  } else if (path === "/studio") {
    page = <Studio />;
  } else if (path === "/tryon") {
    page = <TryOn />;
  } else if (path === "/cart") {
    page = <Cart />;
  } else {
    page = <Shop />;
  }

  return (
    <div className="app">
      <NavBar currentPath={path} />
      <main className="app-main">{page}</main>
      <footer className="app-footer">
        <span className="footer-brand">AIGC 3D Mall</span>
        <span>数字商品、3D 资产生成与虚拟试穿演示工作站</span>
      </footer>
    </div>
  );
}
