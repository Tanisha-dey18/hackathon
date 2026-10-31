import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import { Link } from "react-router-dom";
import { Empty, ErrorBox, Loading, RiskBadge, Spinner, StatusPill } from "../../components/ui";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { dt, usd } from "../../lib/format";

export interface OrderView {
  paypal_order_id: string; transaction_id: string; amount: number; currency: string; items: { name: string; quantity: number }[];
  paypal_status: string; sentinel_status: string; capture_status: string | null; capture_id: string | null;
  risk_level: string | null; transaction_status: string | null; created_at: string; payer_email: string | null;
}

export default function Orders() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["paypal-orders", "mine"], queryFn: () => api<OrderView[]>("/api/paypal/orders"), enabled: !!user, refetchInterval: 10000 });
  const refresh = useMutation({
    mutationFn: (id: string) => api(`/api/paypal/order/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["paypal-orders"] }),
  });
  if (!user) return <Empty>Please <Link to="/login?next=/shop/orders" className="text-cyan-300">sign in</Link>.</Empty>;
  return (
    <div>
      <h1 className="mb-4 text-xl font-semibold">Your orders</h1>
      {q.isLoading && <Loading />}
      <ErrorBox error={q.error || refresh.error} />
      {q.data && !q.data.length && <Empty>No orders yet.</Empty>}
      <div className="space-y-3">
        {q.data?.map((o) => (
          <div key={o.paypal_order_id} className="card p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="font-medium">{o.items.map((i) => `${i.quantity}× ${i.name}`).join(", ")}</div>
                <div className="mt-0.5 font-mono text-xs text-fog-400">{o.paypal_order_id} · {dt(o.created_at)}</div>
              </div>
              <div className="font-mono text-lg">{usd(o.amount)}</div>
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2 text-xs">
              <span className="flex items-center gap-1.5 text-fog-400">PayPal <StatusPill status={o.paypal_status} /></span>
              <span className="flex items-center gap-1.5 text-fog-400">Capture {o.capture_status ? <StatusPill status={o.capture_status} /> : <span className="text-fog-500">none</span>}</span>
              <span className="flex items-center gap-1.5 text-fog-400">Sentinel <StatusPill status={o.sentinel_status} /></span>
              <span className="flex items-center gap-1.5 text-fog-400">Risk <RiskBadge level={o.risk_level} /></span>
              <button className="btn-ghost ml-auto px-2 py-1 text-xs" onClick={() => refresh.mutate(o.paypal_order_id)} disabled={refresh.isPending}>
                {refresh.isPending && refresh.variables === o.paypal_order_id ? <Spinner /> : <RefreshCw className="h-3 w-3" />} Refresh from PayPal
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
