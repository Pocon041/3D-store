// localStorage 购物车的最小实现，附带 React hook 用于订阅变化

import { useEffect, useState } from "react";

const KEY = "aigc3d_cart_v1";
const EVENT = "cart:change";

function read() {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return [];
    const arr = JSON.parse(raw);
    return Array.isArray(arr) ? arr : [];
  } catch {
    return [];
  }
}

function write(items) {
  localStorage.setItem(KEY, JSON.stringify(items));
  window.dispatchEvent(new Event(EVENT));
}

export function getCart() {
  return read();
}

export function addToCart(product, qty = 1) {
  const items = read();
  const idx = items.findIndex((it) => it.id === product.id);
  if (idx >= 0) {
    items[idx].qty += qty;
  } else {
    items.push({
      id: product.id,
      name: product.name,
      price: product.price,
      thumbnail_url: product.thumbnail_url,
      model_url: product.model_url,
      qty,
    });
  }
  write(items);
}

export function removeFromCart(productId) {
  write(read().filter((it) => it.id !== productId));
}

export function clearCart() {
  write([]);
}

export function setQty(productId, qty) {
  const items = read();
  const idx = items.findIndex((it) => it.id === productId);
  if (idx < 0) return;
  if (qty <= 0) {
    items.splice(idx, 1);
  } else {
    items[idx].qty = qty;
  }
  write(items);
}

export function useCart() {
  const [items, setItems] = useState(read);
  useEffect(() => {
    const onChange = () => setItems(read());
    window.addEventListener(EVENT, onChange);
    window.addEventListener("storage", onChange);
    return () => {
      window.removeEventListener(EVENT, onChange);
      window.removeEventListener("storage", onChange);
    };
  }, []);
  const totalQty = items.reduce((acc, it) => acc + it.qty, 0);
  const totalPrice = items.reduce((acc, it) => acc + it.qty * it.price, 0);
  return { items, totalQty, totalPrice };
}
