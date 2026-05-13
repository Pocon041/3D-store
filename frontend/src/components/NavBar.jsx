import React from "react";
import { useCart } from "../cart.js";
import { navigate } from "../router.js";

const LINKS = [
  { path: "/shop", label: "商城" },
  { path: "/tryon", label: "虚拟试穿" },
  { path: "/avatar-tryon", label: "3D换装" },
  { path: "/studio", label: "工作台" },
  { path: "/cart", label: "购物车" },
];

export default function NavBar({ currentPath }) {
  const { totalQty } = useCart();
  return (
    <nav className="nav">
      <div className="nav-inner">
        <div className="brand" onClick={() => navigate("/shop")}>
          <span className="brand-mark">3D</span>
          <span className="brand-text">
            <strong>AIGC 3D Mall</strong>
            <small>数字商品工作站</small>
          </span>
        </div>
        <div className="nav-links">
          {LINKS.map((link) => {
            const active = currentPath === link.path
              || currentPath.startsWith(`${link.path}?`)
              || (link.path === "/shop" && currentPath.startsWith("/shop/"));
            return (
              <a
                key={link.path}
                className={`nav-link ${active ? "active" : ""}`}
                onClick={(e) => {
                  e.preventDefault();
                  navigate(link.path);
                }}
                href={`#${link.path}`}
              >
                <span>{link.label}</span>
                {link.path === "/cart" && totalQty > 0 && (
                  <span className="cart-badge">{totalQty}</span>
                )}
              </a>
            );
          })}
        </div>
      </div>
    </nav>
  );
}
