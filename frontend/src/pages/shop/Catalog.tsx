import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Plus, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { ErrorBox, Loading } from "../../components/ui";
import { api } from "../../lib/api";
import { useCart, type Product } from "../../lib/cart";
import { usd } from "../../lib/format";
import ProductIcon from "./ProductIcon";

export default function Catalog() {
  const { data, isLoading, error } = useQuery({ queryKey: ["products"], queryFn: () => api<Product[]>("/api/shop/products") });
  const { add } = useCart();
  const [msg, setMsg] = useState<string | null>(null);
  const [cat, setCat] = useState("All");
  const cats = ["All", ...new Set((data ?? []).map((p) => p.category))];
  const items = (data ?? []).filter((p) => cat === "All" || p.category === cat);

  return (
    <div>
      <section className="relative mb-8 overflow-hidden rounded-2xl border border-ink-700 bg-gradient-to-br from-ink-800 via-ink-850 to-ink-900 p-8">
        <div className="absolute -right-20 -top-20 h-64 w-64 rounded-full bg-cyan-400/10 blur-3xl" />
        <div className="relative max-w-xl">
          <div className="inline-flex items-center gap-1.5 rounded-full border border-cyan-400/30 bg-cyan-400/10 px-2.5 py-1 text-xs text-cyan-200">
            <ShieldCheck className="h-3.5 w-3.5" /> Every checkout is risk-assessed by Sentinel before capture
          </div>
          <h1 className="mt-4 text-3xl font-semibold tracking-tight">Considered goods, protected payments.</h1>
          <p className="mt-2 text-sm text-fog-300">Pay with PayPal. Sentinel analyses the order with machine learning and graph intelligence before PayPal captures any funds.</p>
        </div>
      </section>
      <div className="mb-5 flex flex-wrap gap-2">
        {cats.map((c) => (
          <button key={c} onClick={() => setCat(c)} className={`rounded-full border px-3 py-1 text-xs ${cat === c ? "border-cyan-400/50 bg-cyan-400/10 text-cyan-200" : "border-ink-600 text-fog-300 hover:border-ink-500"}`}>{c}</button>
        ))}
      </div>
      {msg && <div className="mb-4 rounded-lg border border-amber-400/30 bg-amber-400/10 px-3 py-2 text-sm text-amber-200">{msg}</div>}
      {isLoading ? <Loading /> : <ErrorBox error={error} />}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {items.map((p, i) => (
          <motion.div key={p.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.03 }} className="card group flex flex-col p-3">
            <Link to={`/shop/product/${p.id}`}><ProductIcon image={p.image} /></Link>
            <div className="mt-3 flex-1">
              <div className="text-[11px] uppercase tracking-wider text-fog-400">{p.merchant_name}</div>
              <Link to={`/shop/product/${p.id}`} className="mt-0.5 block font-medium text-fog-100 hover:text-cyan-300">{p.name}</Link>
            </div>
            <div className="mt-3 flex items-center justify-between">
              <span className="font-mono text-lg font-semibold">{usd(p.price)}</span>
              <button className="btn-ghost px-2.5 py-1.5 text-xs" onClick={() => { const r = add(p); setMsg(r.ok ? null : r.reason!); }}>
                <Plus className="h-3.5 w-3.5" /> Add
              </button>
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
