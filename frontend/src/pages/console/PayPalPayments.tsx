import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CreditCard, Radio, RefreshCw, Webhook } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Card, Empty, ErrorBox, Loading, Modal, PageHeader, RiskBadge, Spinner, StatusPill } from "../../components/ui";
import { api } from "../../lib/api";
import { dt, usd } from "../../lib/format";
import type { OrderView } from "../shop/Orders";

interface Ev { id: number; paypal_order_id: string | null; source: string; event_type: string; http_status: number | null; debug_id: string | null; verified: boolean | null; created_at: string; payload: any }

export default function PayPalPayments() {
  const qc = useQueryClient();
  const cfg = useQuery({ queryKey: ["paypal-config"], queryFn: () => api<any>("/api/paypal/config") });
  const orders = useQuery({ queryKey: ["paypal-orders", "all"], queryFn: () => api<OrderView[]>("/api/paypal/orders"), refetchInterval: 15000 });
  const events = useQuery({ queryKey: ["paypal-events"], queryFn: () => api<Ev[]>("/api/paypal/events"), refetchInterval: 15000 });
  const refresh = useMutation({ mutationFn: (id: string) => api(`/api/paypal/order/${id}`), onSuccess: () => { qc.invalidateQueries({ queryKey: ["paypal-orders"] }); qc.invalidateQueries({ queryKey: ["paypal-events"] }); } });
  const [payload, setPayload] = useState<Ev | null>(null);

  return (
    <div>
      <PageHeader title="PayPal Payments" subtitle="PayPal Sandbox orders with PayPal status and Sentinel risk status tracked separately"
        actions={cfg.data && (
          <span className={`rounded-lg border px-2.5 py-1 font-mono text-xs ${cfg.data.configured ? "border-emerald-400/40 text-emerald-300" : "border-amber-400/40 text-amber-300"}`}>
            {cfg.data.configured ? `PayPal ${cfg.data.environment} connected` : "PayPal not configured"} · webhooks {cfg.data.webhook_verification ? "verified" : "not configured"}
          </span>
        )} />
      <ErrorBox error={refresh.error} />
      <Card title="Orders" icon={<CreditCard className="h-4 w-4" />} bodyClass="p-0">
        {orders.isLoading && <Loading />}
        {orders.data && !orders.data.length && <Empty>No PayPal orders yet. Run a checkout from <Link to="/shop" className="text-cyan-300">SENTINEL MERCHANT</Link>.</Empty>}
        {!!orders.data?.length && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-ink-700 text-left text-[11px] uppercase tracking-wider text-fog-400">
                <tr>{["Created", "PayPal order", "Transaction", "Amount", "PayPal status", "Capture", "Sentinel status", "Risk", ""].map((h) => <th key={h} className="px-4 py-2.5 font-medium">{h}</th>)}</tr>
              </thead>
              <tbody>
                {orders.data.map((o) => (
                  <tr key={o.paypal_order_id} className="border-b border-ink-700/50 hover:bg-ink-800/60">
                    <td className="px-4 py-2.5 text-xs text-fog-400">{dt(o.created_at)}</td>
                    <td className="px-4 py-2.5 font-mono text-xs">{o.paypal_order_id}</td>
                    <td className="px-4 py-2.5"><Link className="font-mono text-xs text-cyan-300 hover:underline" to={`/console/investigate/${o.transaction_id}`}>{o.transaction_id}</Link></td>
                    <td className="px-4 py-2.5 font-mono">{usd(o.amount)}</td>
                    <td className="px-4 py-2.5"><StatusPill status={o.paypal_status} /></td>
                    <td className="px-4 py-2.5">{o.capture_status ? <span className="flex flex-col gap-0.5"><StatusPill status={o.capture_status} /><span className="font-mono text-[10px] text-fog-500">{o.capture_id}</span></span> : <span className="text-xs text-fog-500">not captured</span>}</td>
                    <td className="px-4 py-2.5"><StatusPill status={o.sentinel_status} /></td>
                    <td className="px-4 py-2.5"><RiskBadge level={o.risk_level} /></td>
                    <td className="px-4 py-2.5">
                      <button className="btn-ghost px-2 py-1 text-xs" disabled={refresh.isPending} onClick={() => refresh.mutate(o.paypal_order_id)}>
                        {refresh.isPending && refresh.variables === o.paypal_order_id ? <Spinner /> : <RefreshCw className="h-3 w-3" />}Sync
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
      <Card title="Payment events (PayPal API responses & verified webhooks)" icon={<Webhook className="h-4 w-4" />} className="mt-4" bodyClass="p-0">
        {events.data && !events.data.length && <Empty>No payment events recorded.</Empty>}
        <div className="max-h-[420px] overflow-y-auto">
          {events.data?.map((e) => (
            <button key={e.id} onClick={() => setPayload(e)} className="flex w-full items-center gap-3 border-b border-ink-700/50 px-4 py-2 text-left text-xs hover:bg-ink-800/60">
              {e.source === "PAYPAL_WEBHOOK" ? <Radio className="h-3.5 w-3.5 text-fuchsia-300" /> : <CreditCard className="h-3.5 w-3.5 text-sky-300" />}
              <span className="w-28 font-mono text-fog-400">{e.source}</span>
              <span className="font-mono text-fog-100">{e.event_type}</span>
              <span className="font-mono text-fog-400">{e.paypal_order_id}</span>
              {e.http_status && <span className={`font-mono ${e.http_status < 300 ? "text-emerald-300" : "text-rose-300"}`}>HTTP {e.http_status}</span>}
              {e.verified != null && <span className="text-emerald-300">signature verified</span>}
              {e.debug_id && <span className="font-mono text-fog-500">debug {e.debug_id}</span>}
              <span className="ml-auto text-fog-500">{dt(e.created_at)}</span>
            </button>
          ))}
        </div>
      </Card>
      <Modal open={!!payload} onClose={() => setPayload(null)} title={payload?.event_type ?? ""} width="max-w-3xl">
        <pre className="max-h-[60vh] overflow-auto rounded-lg bg-ink-950 p-3 font-mono text-[11px] text-fog-200">{JSON.stringify(payload?.payload, null, 2)}</pre>
      </Modal>
    </div>
  );
}
