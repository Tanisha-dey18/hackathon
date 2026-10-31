import { PayPalButtons, PayPalScriptProvider } from "@paypal/react-paypal-js";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { AlertTriangle, CheckCircle2, Clock, ShieldAlert, ShieldCheck } from "lucide-react";
import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ErrorBox, Loading, RiskBadge, StatusPill } from "../../components/ui";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { demoGeo, deviceFingerprint, useCart } from "../../lib/cart";
import { usd, uuid } from "../../lib/format";

interface PayPalConfig { configured: boolean; client_id: string | null; currency: string; environment: string }
interface CaptureResult {
  paypal_order_id: string; transaction_id: string; paypal_status: string; sentinel_status: string; capture_id: string | null;
  capture_status: string | null; message: string; risk?: { risk_level: string; fraud_probability: number; recommended_action: string };
  investigation_id?: string; amount: number;
}

export default function Checkout() {
  const { user } = useAuth();
  const { lines, total, clear } = useCart();
  const cfg = useQuery({ queryKey: ["paypal-config"], queryFn: () => api<PayPalConfig>("/api/paypal/config") });
  const [result, setResult] = useState<CaptureResult | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [stage, setStage] = useState<string | null>(null);
  const lastOrder = useRef<string | null>(null);

  if (result) return <Result r={result} />;
  if (!user || user.role !== "CUSTOMER") {
    return (
      <div className="card mx-auto max-w-md p-6 text-center">
        <div className="text-lg font-semibold">Sign in to check out</div>
        <p className="mt-2 text-sm text-fog-400">Checkout requires a shopper account so Sentinel can verify payment ownership.</p>
        <Link to="/login?next=/shop/checkout" className="btn-primary mt-5">Sign in as shopper</Link>
      </div>
    );
  }
  if (!lines.length) return <div className="text-center text-sm text-fog-400">Cart is empty. <Link className="text-cyan-300" to="/shop">Shop</Link></div>;

  const geo = demoGeo();
  return (
    <div className="grid gap-6 md:grid-cols-[1fr_380px]">
      <div className="card p-5">
        <div className="label">Checkout · {lines[0].product.merchant_name}</div>
        <div className="mt-4 divide-y divide-ink-700/70">
          {lines.map((l) => (
            <div key={l.product.id} className="flex justify-between py-2.5 text-sm">
              <span>{l.quantity} × {l.product.name}</span><span className="font-mono">{usd(l.product.price * l.quantity)}</span>
            </div>
          ))}
        </div>
        <div className="mt-3 flex justify-between border-t border-ink-700 pt-3 text-lg font-semibold"><span>Total</span><span className="font-mono">{usd(total)}</span></div>
        <div className="mt-6 rounded-lg border border-ink-700 bg-ink-900/60 p-3 text-xs text-fog-400">
          <div className="mb-1 font-medium text-fog-200">How this payment is protected</div>
          1. Server creates a PayPal order (Orders API v2) with server-side prices. 2. You approve in PayPal.
          3. Sentinel retrieves the approved order, verifies amount & ownership, and scores risk. 4. Only LOW risk is captured automatically;
          anything else is held for a human reviewer and <b>not captured</b>.
          <div className="mt-2 font-mono text-[10.5px] text-fog-500">device context: {deviceFingerprint().slice(0, 24)}…{geo ? ` · geo ${geo.lat.toFixed(2)},${geo.lon.toFixed(2)} (demo)` : ""}</div>
        </div>
      </div>
      <div className="card h-fit p-5">
        <div className="label mb-3">Pay with PayPal (Sandbox)</div>
        {cfg.isLoading && <Loading />}
        {cfg.data && !cfg.data.configured && (
          <div className="rounded-lg border border-amber-400/30 bg-amber-400/10 p-3 text-sm text-amber-100">
            <div className="flex items-center gap-2 font-semibold"><AlertTriangle className="h-4 w-4" />PayPal Sandbox is not configured</div>
            <p className="mt-2 text-xs text-amber-200/80">
              Set <span className="font-mono">PAYPAL_CLIENT_ID</span> and <span className="font-mono">PAYPAL_CLIENT_SECRET</span> (Sandbox REST app credentials from developer.paypal.com) in the backend <span className="font-mono">.env</span> and restart.
              Sentinel never simulates a PayPal payment. Staff can still run the risk pipeline for this scenario from the Command Centre.
            </p>
          </div>
        )}
        {cfg.data?.configured && cfg.data.client_id && (
          <PayPalScriptProvider options={{ clientId: cfg.data.client_id, currency: "USD", intent: "capture", components: "buttons" }}>
            <PayPalButtons
              style={{ layout: "vertical", color: "gold", shape: "rect", label: "paypal", height: 44 }}
              createOrder={async () => {
                setError(null);
                setStage("Creating PayPal order…");
                const r = await api<{ paypal_order_id: string }>("/api/paypal/create-order", {
                  method: "POST",
                  headers: { "Idempotency-Key": uuid() },
                  json: { items: lines.map((l) => ({ product_id: l.product.id, quantity: l.quantity })), device_fingerprint: deviceFingerprint(), geo },
                }).catch((e) => { setError(e); setStage(null); throw e; });
                lastOrder.current = r.paypal_order_id;
                setStage("Waiting for approval in PayPal…");
                return r.paypal_order_id;
              }}
              onApprove={async (data) => {
                setStage("Approved by buyer. Sentinel is assessing risk before capture…");
                try {
                  const r = await api<CaptureResult>("/api/paypal/capture-order", { method: "POST", json: { order_id: data.orderID } });
                  clear();
                  setResult(r);
                } catch (e) {
                  setError(e);
                } finally {
                  setStage(null);
                }
              }}
              onCancel={() => setStage("Checkout cancelled in PayPal. Nothing was charged.")}
              onError={(e) => { setError(e instanceof Error ? e : new Error(String(e))); setStage(null); }}
            />
          </PayPalScriptProvider>
        )}
        {stage && <div className="mt-3 flex items-center gap-2 text-xs text-cyan-200"><Clock className="h-3.5 w-3.5" />{stage}</div>}
        <div className="mt-3"><ErrorBox error={error} /></div>
        <p className="mt-4 text-[11px] text-fog-500">Use a PayPal Sandbox personal (buyer) account to approve. No real money moves.</p>
      </div>
    </div>
  );
}

function Result({ r }: { r: CaptureResult }) {
  const captured = r.capture_status === "COMPLETED";
  const held = !r.capture_status && ["HELD_FOR_REVIEW", "HELD_FOR_VERIFICATION", "ESCALATED"].includes(r.sentinel_status);
  const Icon = captured ? CheckCircle2 : held ? ShieldAlert : ShieldCheck;
  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="card mx-auto max-w-2xl p-7">
      <div className="flex items-center gap-3">
        <Icon className={`h-9 w-9 ${captured ? "text-emerald-400" : held ? "text-amber-400" : "text-cyan-400"}`} />
        <div>
          <div className="text-xl font-semibold">{captured ? "Payment complete" : held ? "Payment under review" : "Payment status"}</div>
          <div className="text-sm text-fog-300">{r.message}</div>
        </div>
      </div>
      <div className="mt-6 grid gap-4 sm:grid-cols-2">
        <div className="rounded-lg border border-ink-700 bg-ink-900/60 p-4">
          <div className="label">PayPal status (from PayPal API)</div>
          <div className="mt-2 space-y-1.5 text-sm">
            <div className="flex justify-between"><span className="text-fog-400">Order</span><span className="font-mono text-xs">{r.paypal_order_id}</span></div>
            <div className="flex justify-between"><span className="text-fog-400">Order status</span><StatusPill status={r.paypal_status} /></div>
            <div className="flex justify-between"><span className="text-fog-400">Capture</span>{r.capture_status ? <StatusPill status={r.capture_status} /> : <span className="text-xs text-fog-400">not captured</span>}</div>
            {r.capture_id && <div className="flex justify-between"><span className="text-fog-400">Capture ID</span><span className="font-mono text-xs">{r.capture_id}</span></div>}
          </div>
        </div>
        <div className="rounded-lg border border-ink-700 bg-ink-900/60 p-4">
          <div className="label">Sentinel risk status</div>
          <div className="mt-2 space-y-1.5 text-sm">
            <div className="flex justify-between"><span className="text-fog-400">Transaction</span><span className="font-mono text-xs">{r.transaction_id}</span></div>
            <div className="flex justify-between"><span className="text-fog-400">Decision</span><StatusPill status={r.sentinel_status} /></div>
            {r.risk && <div className="flex justify-between"><span className="text-fog-400">Risk</span><RiskBadge level={r.risk.risk_level} /></div>}
            {r.investigation_id && <div className="flex justify-between"><span className="text-fog-400">AI investigation</span><span className="font-mono text-xs">{r.investigation_id}</span></div>}
          </div>
        </div>
      </div>
      <div className="mt-6 flex gap-2">
        <Link to="/shop/orders" className="btn-primary">View orders</Link>
        <Link to="/shop" className="btn-ghost">Continue shopping</Link>
      </div>
    </motion.div>
  );
}
