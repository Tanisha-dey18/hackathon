import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, ShieldCheck, ShoppingCart } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ErrorBox, Loading } from "../../components/ui";
import { api } from "../../lib/api";
import { useCart, type Product } from "../../lib/cart";
import { usd } from "../../lib/format";
import ProductIcon from "./ProductIcon";

export default function ProductDetail() {
  const { id } = useParams();
  const { data: p, isLoading, error } = useQuery({ queryKey: ["product", id], queryFn: () => api<Product>(`/api/shop/products/${id}`) });
  const { add } = useCart();
  const nav = useNavigate();
  const [qty, setQty] = useState(1);
  const [msg, setMsg] = useState<string | null>(null);
  if (isLoading) return <Loading />;
  if (!p) return <ErrorBox error={error} />;
  return (
    <div>
      <Link to="/shop" className="mb-4 inline-flex items-center gap-1 text-sm text-fog-400 hover:text-fog-100"><ArrowLeft className="h-4 w-4" />Back</Link>
      <div className="grid gap-8 md:grid-cols-2">
        <ProductIcon image={p.image} className="h-80" />
        <div>
          <div className="text-xs uppercase tracking-wider text-fog-400">{p.merchant_name} · {p.category}</div>
          <h1 className="mt-1 text-2xl font-semibold">{p.name}</h1>
          <div className="mt-3 font-mono text-3xl font-semibold">{usd(p.price)}</div>
          <p className="mt-4 text-sm leading-relaxed text-fog-300">{p.description}</p>
          <div className="mt-6 flex items-center gap-3">
            <select className="input w-24" value={qty} onChange={(e) => setQty(Number(e.target.value))}>
              {Array.from({ length: 5 }, (_, i) => i + 1).map((n) => <option key={n}>{n}</option>)}
            </select>
            <button className="btn-primary" onClick={() => { const r = add(p, qty); if (r.ok) nav("/shop/cart"); else setMsg(r.reason!); }}>
              <ShoppingCart className="h-4 w-4" /> Add to cart
            </button>
          </div>
          {msg && <div className="mt-3 text-sm text-amber-300">{msg}</div>}
          <div className="mt-8 flex items-start gap-2 rounded-lg border border-ink-700 bg-ink-900/60 p-3 text-xs text-fog-400">
            <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-cyan-400" />
            Sold by {p.merchant_name} ({p.merchant_id}). Payment is processed by PayPal; Sentinel reviews risk before funds are captured.
          </div>
        </div>
      </div>
    </div>
  );
}
