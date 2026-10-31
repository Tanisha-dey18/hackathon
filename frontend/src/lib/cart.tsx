import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";

export interface Product {
  id: string;
  name: string;
  description: string;
  category: string;
  price: number;
  image: string;
  merchant_id: string;
  merchant_name: string;
  stock: number;
}
export interface CartLine {
  product: Product;
  quantity: number;
}

interface CartCtx {
  lines: CartLine[];
  add: (p: Product, qty?: number) => { ok: boolean; reason?: string };
  setQty: (id: string, qty: number) => void;
  remove: (id: string) => void;
  clear: () => void;
  replaceWith: (lines: CartLine[]) => void;
  total: number;
  count: number;
}

const Ctx = createContext<CartCtx | null>(null);
const KEY = "sentinel_cart";
const DEVICE_KEY = "sentinel_device_fp";
const GEO_KEY = "sentinel_demo_geo";

function load(): CartLine[] {
  try {
    return JSON.parse(localStorage.getItem(KEY) || "[]");
  } catch {
    return [];
  }
}

export function CartProvider({ children }: { children: ReactNode }) {
  const [lines, setLines] = useState<CartLine[]>(load);
  useEffect(() => {
    try {
      localStorage.setItem(KEY, JSON.stringify(lines));
    } catch {
      /* ignore */
    }
  }, [lines]);

  const add = useCallback((p: Product, qty = 1) => {
    if (lines.length && lines[0].product.merchant_id !== p.merchant_id) {
      return { ok: false, reason: `Your cart has items from ${lines[0].product.merchant_name}. Checkout is per seller.` };
    }
    setLines((prev) => {
      const i = prev.findIndex((l) => l.product.id === p.id);
      if (i >= 0) return prev.map((l, j) => (j === i ? { ...l, quantity: Math.min(10, l.quantity + qty) } : l));
      return [...prev, { product: p, quantity: qty }];
    });
    return { ok: true };
  }, [lines]);

  const value: CartCtx = {
    lines,
    add,
    setQty: (id, qty) => setLines((p) => p.map((l) => (l.product.id === id ? { ...l, quantity: Math.max(1, Math.min(10, qty)) } : l))),
    remove: (id) => setLines((p) => p.filter((l) => l.product.id !== id)),
    clear: () => setLines([]),
    replaceWith: (l) => setLines(l),
    total: lines.reduce((s, l) => s + l.product.price * l.quantity, 0),
    count: lines.reduce((s, l) => s + l.quantity, 0),
  };
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useCart() {
  const c = useContext(Ctx);
  if (!c) throw new Error("CartProvider missing");
  return c;
}

/** Stable per-browser device fingerprint (a random identifier; no tracking data collected). */
export function deviceFingerprint(): string {
  try {
    let fp = localStorage.getItem(DEVICE_KEY);
    if (!fp) {
      fp = "fp-browser-" + Math.random().toString(36).slice(2, 12) + Date.now().toString(36);
      localStorage.setItem(DEVICE_KEY, fp);
    }
    return fp;
  } catch {
    return "fp-browser-ephemeral-" + Math.random().toString(36).slice(2, 10);
  }
}

export function setDemoContext(fp: string, geo: { lat: number; lon: number } | null) {
  try {
    localStorage.setItem(DEVICE_KEY, fp);
    if (geo) localStorage.setItem(GEO_KEY, JSON.stringify(geo));
    else localStorage.removeItem(GEO_KEY);
  } catch {
    /* ignore */
  }
}

export function demoGeo(): { lat: number; lon: number } | null {
  try {
    return JSON.parse(localStorage.getItem(GEO_KEY) || "null");
  } catch {
    return null;
  }
}
