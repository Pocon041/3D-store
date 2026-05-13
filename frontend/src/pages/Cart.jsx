import React, { useState } from "react";
import { useCart, removeFromCart, setQty, clearCart } from "../cart.js";
import { navigate } from "../router.js";

function priceText(price) {
  if (!price) return "¥0";
  if (price >= 1000) return `¥${price.toLocaleString("zh-CN")}`;
  return `¥${price.toFixed(price < 100 ? 1 : 0)}`;
}

export default function Cart() {
  const { items, totalQty, totalPrice } = useCart();
  const [paid, setPaid] = useState(false);

  if (paid) {
    return (
      <div className="page">
        <div className="empty-cart">
          <div className="empty-cart-mark">✓</div>
          <h2>下单成功（演示）</h2>
          <p>这是 demo，没有真实结算。已为你清空购物车。</p>
          <button className="btn-primary" onClick={() => navigate("/shop")}>继续逛商城</button>
        </div>
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="page">
        <div className="empty-cart">
          <div className="empty-cart-mark">3D</div>
          <h2>购物车是空的</h2>
          <p>去 3D 商城挑几件感兴趣的商品看看吧。</p>
          <button className="btn-primary" onClick={() => navigate("/shop")}>去逛商城</button>
        </div>
      </div>
    );
  }

  return (
    <div className="page">
      <header className="page-header cart-header">
        <div>
          <h1>购物车</h1>
          <p>已选择 {totalQty} 件 3D 商品，结算前仍可调整数量。</p>
        </div>
        <div className="cart-total compact-total">
          合计 <span className="total-num">{priceText(totalPrice)}</span>
        </div>
      </header>

      <div className="cart-panel">
        <table className="cart-table">
          <thead>
            <tr>
              <th>商品</th>
              <th>单价</th>
              <th>数量</th>
              <th>小计</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {items.map((it) => (
              <tr key={it.id}>
                <td>
                  <div className="cart-item">
                    {it.thumbnail_url ? (
                      <img src={it.thumbnail_url} alt={it.name} />
                    ) : (
                      <div className="cart-thumb-fallback" />
                    )}
                    <a className="cart-name" onClick={() => navigate(`/shop/${it.id}`)}>{it.name}</a>
                  </div>
                </td>
                <td>{priceText(it.price)}</td>
                <td>
                  <div className="qty-row inline">
                    <button onClick={() => setQty(it.id, it.qty - 1)}>−</button>
                    <input value={it.qty} readOnly />
                    <button onClick={() => setQty(it.id, it.qty + 1)}>+</button>
                  </div>
                </td>
                <td>{priceText(it.price * it.qty)}</td>
                <td>
                  <button className="btn-link" onClick={() => removeFromCart(it.id)}>删除</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="cart-foot">
        <button className="btn-link" onClick={() => clearCart()}>清空购物车</button>
        <div className="cart-total">
          合计 <span className="total-num">{priceText(totalPrice)}</span>
          <button className="btn-primary" onClick={() => { clearCart(); setPaid(true); }}>
            结算（演示）
          </button>
        </div>
      </div>
    </div>
  );
}
