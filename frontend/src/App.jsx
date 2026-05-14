import React from "react";
import NavBar from "./components/NavBar.jsx";
import Shop from "./pages/Shop.jsx";
import ProductDetail from "./pages/ProductDetail.jsx";
import Studio from "./pages/Studio.jsx";
import Cart from "./pages/Cart.jsx";
import TryOn from "./pages/TryOn.jsx";
import AvatarTryOn from "./pages/AvatarTryOn.jsx";
import { useHashRoute } from "./router.js";

function RoutePane({ active, children }) {
  return <div style={{ display: active ? "block" : "none" }}>{children}</div>;
}

export default function App() {
  const path = useHashRoute();

  const isProductDetail = path.startsWith("/shop/");
  const isStudio = path === "/studio";
  const isTryOn = path === "/tryon" || path.startsWith("/tryon?");
  const isAvatarTryOn = path.startsWith("/avatar-tryon");
  const isCart = path === "/cart";
  const isShopHome = path === "/shop" || path === "/" || (
    !isProductDetail
    && !isStudio
    && !isTryOn
    && !isAvatarTryOn
    && !isCart
  );

  const productId = isProductDetail
    ? decodeURIComponent(path.slice("/shop/".length))
    : null;

  return (
    <div className="app">
      <NavBar currentPath={path} />
      <main className="app-main">
        <RoutePane active={isShopHome}>
          <Shop />
        </RoutePane>
        <RoutePane active={isStudio}>
          <Studio />
        </RoutePane>
        <RoutePane active={isTryOn}>
          <TryOn path={path} />
        </RoutePane>
        <RoutePane active={isAvatarTryOn}>
          <AvatarTryOn />
        </RoutePane>
        <RoutePane active={isCart}>
          <Cart />
        </RoutePane>
        {productId && <ProductDetail productId={productId} />}
      </main>
      <footer className="app-footer">
        <span className="footer-brand">AIGC 3D Mall</span>
        <span>数字商品、3D 资产生成与虚拟试穿演示工作站</span>
      </footer>
    </div>
  );
}
