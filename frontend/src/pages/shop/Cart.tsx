import { Minus, Plus, Trash2 } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { Empty } from "../../components/ui";
import { useCart } from "../../lib/cart";
import { usd } from "../../lib/format";
import ProductIcon from "./ProductIcon";

export default function Cart() {
  const { lines, setQty, remove, total, clear } = useCart();
  const nav = useNavigate();
  if (!lines.length) return <Empty>Your cart is empty. <Link className="text-cyan-300" to="/shop">Browse products</Link></Empty>;
  return (
    <div className="grid gap-6 md:grid-cols-[1fr_320px]">
      <div className="card divide-y divide-ink-700/70">
        <div className="flex items-center justify-between px-4 py-3">
          <div className="text-sm font-semibold">Cart · {lines[0].product.merchant_name}</div>
          <button className="text-xs text-fog-400 hover:text-rose-300" onClick={clear}>Clear</button>
        </div>
        {lines.map((l) => (
          <div key={l.product.id} className="flex items-center gap-4 p-4">
            <ProductIcon image={l.product.image} className="h-16 w-16" />
            <div className="min-w-0 flex-1">
              <div className="truncate font-medium">{l.product.name}</div>
              <div className="font-mono text-sm text-fog-400">{usd(l.product.price)}</div>
            </div>
            <div className="flex items-center gap-1">
              <button className="btn-ghost p-1.5" onClick={() => setQty(l.product.id, l.quantity - 1)}><Minus className="h-3 w-3" /></button>
              <span className="w-8 text-center font-mono text-sm">{l.quantity}</span>
              <button className="btn-ghost p-1.5" onClick={() => setQty(l.product.id, l.quantity + 1)}><Plus className="h-3 w-3" /></button>
            </div>
            <div className="w-24 text-right font-mono">{usd(l.product.price * l.quantity)}</div>
            <button className="text-fog-500 hover:text-rose-300" onClick={() => remove(l.product.id)}><Trash2 className="h-4 w-4" /></button>
          </div>
        ))}
      </div>
      <div className="card h-fit p-5">
        <div className="label">Order summary</div>
        <div className="mt-4 flex justify-between text-sm"><span className="text-fog-400">Subtotal</span><span className="font-mono">{usd(total)}</span></div>
        <div className="mt-1 flex justify-between text-sm"><span className="text-fog-400">Shipping</span><span className="font-mono">Free</span></div>
        <div className="mt-4 flex justify-between border-t border-ink-700 pt-4 font-semibold"><span>Total</span><span className="font-mono">{usd(total)}</span></div>
        <button className="btn-primary mt-5 w-full" onClick={() => nav("/shop/checkout")}>Checkout with PayPal</button>
        <p className="mt-3 text-[11px] text-fog-500">Prices are recalculated on the server. The client total is for display only.</p>
      </div>
    </div>
  );
}
