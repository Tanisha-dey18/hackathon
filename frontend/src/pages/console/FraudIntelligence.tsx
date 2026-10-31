import { useQuery } from "@tanstack/react-query";
import { BrainCircuit, Inbox, Radar } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ChartTooltip } from "../../components/charts";
import DecisionPanel from "../../components/DecisionPanel";
import ShapChart, { featureLabel } from "../../components/ShapChart";
import { Card, Empty, ErrorBox, Loading, PageHeader, ProbabilityBar, RiskBadge, StatusPill } from "../../components/ui";
import { api } from "../../lib/api";
import { dt, usd } from "../../lib/format";
import type { Prediction } from "./InvestigationWorkspace";
import type { TxnRow } from "./LiveTransactions";

export default function FraudIntelligence() {
  const queue = useQuery({ queryKey: ["queue"], queryFn: () => api<TxnRow[]>("/api/reviews/queue"), refetchInterval: 15000 });
  const models = useQuery({ queryKey: ["models"], queryFn: () => api<any[]>("/api/models") });
  const [sel, setSel] = useState<string | null>(null);
  useEffect(() => { if (!sel && queue.data?.length) setSel(queue.data[0].id); }, [queue.data, sel]);
  const detail = useQuery({ queryKey: ["txn", sel], enabled: !!sel, queryFn: () => api<any>(`/api/transactions/${sel}`) });
  const primary = models.data?.find((m) => m.is_primary && m.is_active);
  const imp = (primary?.metrics.global_importance ?? []).slice(0, 12).map((x: any) => ({ feature: featureLabel(x.feature), value: x.mean_abs_shap }));
  const p: Prediction | undefined = detail.data?.predictions[0];

  return (
    <div>
      <PageHeader title="Fraud Intelligence" subtitle="Review queue, per-transaction SHAP explanations and global model drivers" />
      <div className="grid gap-4 xl:grid-cols-12">
        <Card title={`Review queue (${queue.data?.length ?? 0})`} icon={<Inbox className="h-4 w-4" />} className="xl:col-span-4" bodyClass="p-0">
          {queue.isLoading && <Loading />}
          <ErrorBox error={queue.error} />
          {queue.data && !queue.data.length && <Empty>Queue is clear.</Empty>}
          <div className="max-h-[680px] overflow-y-auto">
            {queue.data?.map((t) => (
              <button key={t.id} onClick={() => setSel(t.id)}
                className={`flex w-full items-center gap-3 border-b border-ink-700/50 px-4 py-2.5 text-left transition ${sel === t.id ? "bg-cyan-400/5" : "hover:bg-ink-800"}`}>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2"><span className="font-mono text-xs">{t.id}</span><RiskBadge level={t.risk_level} /></div>
                  <div className="mt-0.5 truncate text-xs text-fog-400">{t.customer_name} · {t.merchant_name ?? t.destination_id}</div>
                </div>
                <div className="text-right">
                  <div className="font-mono text-sm">{usd(t.amount)}</div>
                  <div className="text-[10px] text-fog-500">{t.review_status === "ESCALATED" ? "ESCALATED" : t.channel}</div>
                </div>
              </button>
            ))}
          </div>
        </Card>
        <div className="space-y-4 xl:col-span-8">
          {sel && detail.data && p && (
            <Card title={<span className="flex items-center gap-2">Explanation · <span className="font-mono">{sel}</span></span>} icon={<Radar className="h-4 w-4" />}
              actions={<Link to={`/console/investigate/${sel}`} className="btn-ghost px-2.5 py-1 text-xs">Open workspace →</Link>}>
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <div className="flex items-center gap-2"><span className="font-mono text-2xl">{usd(detail.data.transaction.amount)}</span><StatusPill status={detail.data.transaction.status} /></div>
                  <div className="mt-1 text-xs text-fog-400">{detail.data.customer.name} · {dt(detail.data.transaction.created_at)}</div>
                  <div className="label mb-1 mt-4">Fraud probability</div><ProbabilityBar value={p.fraud_probability} />
                  <div className="label mb-1 mt-3">Anomaly percentile</div><ProbabilityBar value={p.anomaly_score} />
                  <div className="mt-3 space-y-1">{p.policy_notes.map((n) => <div key={n} className="text-[11.5px] text-fog-300">↳ {n}</div>)}</div>
                  <div className="label mb-1 mt-4">Top risk factors</div>
                  <ul className="space-y-1">{p.top_risk_factors.map((f) => <li key={f} className="text-[12.5px] text-fog-200">• {f}</li>)}</ul>
                  <div className="mt-4"><DecisionPanel txnId={sel} status={detail.data.transaction.status} riskLevel={detail.data.transaction.risk_level} recommendation={detail.data.investigations[0]?.recommendation} /></div>
                </div>
                <div>
                  <div className="label mb-1">SHAP contributions ({p.shap.space}) · red increases risk</div>
                  <ShapChart values={p.shap.values} features={p.features} top={12} height={330} />
                </div>
              </div>
            </Card>
          )}
          <Card title="Global risk drivers · mean |SHAP| on hold-out set" icon={<BrainCircuit className="h-4 w-4" />}
            actions={primary && <span className="font-mono text-[11px] text-fog-400">{primary.algorithm} {primary.version}</span>}>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={imp} layout="vertical" margin={{ left: 10, right: 16 }}>
                <XAxis type="number" hide />
                <YAxis type="category" dataKey="feature" width={150} tick={{ fill: "#9aa6ba", fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip cursor={{ fill: "rgba(255,255,255,.03)" }} content={<ChartTooltip fmt={(v) => v.toFixed(4)} />} />
                <Bar dataKey="value" name="mean |SHAP|" fill="#22d3ee" radius={[0, 3, 3, 0]} barSize={13} />
              </BarChart>
            </ResponsiveContainer>
          </Card>
        </div>
      </div>
    </div>
  );
}
