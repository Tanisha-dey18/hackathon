import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import {
  AlertTriangle, ArrowLeft, Bot, CheckCircle2, CircleDashed, CreditCard, FileText, Fingerprint, Gavel, Network, Radar, ScanSearch,
  ShieldCheck, Wrench, XCircle,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import DecisionPanel from "../../components/DecisionPanel";
import GraphView, { type GEdge, type GNode, type GraphData } from "../../components/GraphView";
import ShapChart from "../../components/ShapChart";
import { Card, ErrorBox, KV, Loading, ProbabilityBar, RiskBadge, Spinner, StatusPill, SyntheticTag } from "../../components/ui";
import { api } from "../../lib/api";
import { dt, usd } from "../../lib/format";

export interface Prediction {
  fraud_probability: number; anomaly_score: number; graph_risk_score: number; risk_level: string; model_version: string; model_algorithm: string;
  top_risk_factors: string[]; recommended_action: string; policy_notes: string[]; shap: { space: string; values: Record<string, number> };
  features: Record<string, number | null>; latency_ms: number; assessed_at: string;
}
interface TxnDetail {
  transaction: any; customer: any; merchant: any; device: any; destination: any; location: { lat: number; lon: number };
  predictions: Prediction[]; investigations: { id: string; status: string; mode: string; recommendation: string | null; created_at: string }[];
  decisions: { id: number; decision: string; reason: string; reviewer: string; risk_level_at_decision: string; payment_outcome: string; created_at: string }[];
  paypal_order: any; payment_events: any[]; audit: { id: number; action: string; actor: string; details: any; created_at: string; hash: string }[];
}
interface Step { name: string; tool: string; status: string; summary?: string; duration_ms?: number; started_at: string }
interface Investigation {
  id: string; status: string; mode: string; llm_model: string | null; steps: Step[]; error: string | null; recommendation: string | null;
  risk_level: string | null; created_at: string; completed_at: string | null;
  report: null | {
    mode: string; risk_level: string | null; summary: string; findings: { statement: string; evidence_keys: string[] }[]; recommendation: string;
    rationale: string; rejected_findings: { statement: string; reason: string }[]; notice: string; fallback_reason?: string;
    evidence: { key: string; tool: string; category: string; severity: string; summary: string; mitigating: boolean }[];
  };
}

const SEV: Record<string, string> = { HIGH: "text-rose-300 border-rose-400/30 bg-rose-400/10", MEDIUM: "text-amber-300 border-amber-400/30 bg-amber-400/10", LOW: "text-sky-300 border-sky-400/30 bg-sky-400/10", INFO: "text-fog-300 border-ink-500 bg-ink-700/40" };

export default function InvestigationWorkspace() {
  const { txnId = "" } = useParams();
  const qc = useQueryClient();
  const detail = useQuery({ queryKey: ["txn", txnId], queryFn: () => api<TxnDetail>(`/api/transactions/${txnId}`) });
  const graph = useQuery({ queryKey: ["graph", "txn", txnId], queryFn: () => api<GraphData>(`/api/graph/transaction/${txnId}`) });
  const [invId, setInvId] = useState<string | null>(null);
  const latestInv = detail.data?.investigations[0]?.id ?? null;
  useEffect(() => { if (!invId && latestInv) setInvId(latestInv); }, [latestInv, invId]);
  const inv = useQuery({
    queryKey: ["investigation", invId], enabled: !!invId,
    queryFn: () => api<Investigation>(`/api/investigations/${invId}`),
    refetchInterval: (q) => (q.state.data?.status === "RUNNING" || !q.state.data ? 700 : false),
  });
  useEffect(() => {
    if (inv.data && inv.data.status !== "RUNNING") {
      qc.invalidateQueries({ queryKey: ["txn", txnId] });
      qc.invalidateQueries({ queryKey: ["graph", "txn", txnId] });
    }
  }, [inv.data?.status, qc, txnId]);
  const start = useMutation({
    mutationFn: () => api<{ investigation_id: string }>("/api/investigations/start", { method: "POST", json: { transaction_id: txnId } }),
    onSuccess: (r) => setInvId(r.investigation_id),
  });
  const [selNode, setSelNode] = useState<GNode | null>(null);
  const [selEdge, setSelEdge] = useState<GEdge | null>(null);

  if (detail.isLoading) return <Loading label="Loading transaction" />;
  if (!detail.data) return <ErrorBox error={detail.error} />;
  const d = detail.data;
  const t = d.transaction;
  const p = d.predictions[0];
  const running = inv.data?.status === "RUNNING" || start.isPending;

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Link to="/console/transactions" className="rounded-md p-1.5 text-fog-400 hover:bg-ink-750 hover:text-fog-100"><ArrowLeft className="h-4 w-4" /></Link>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="font-mono text-lg font-semibold">{t.id}</h1>
              <RiskBadge level={t.risk_level} size="md" />
              <StatusPill status={t.status} />
              {t.is_synthetic && <SyntheticTag />}
            </div>
            <div className="text-xs text-fog-400">Live fraud investigation workspace · {dt(t.created_at)} · channel {t.channel}</div>
          </div>
        </div>
        <button className="btn-primary" onClick={() => start.mutate()} disabled={running}>
          {running ? <Spinner /> : <ScanSearch className="h-4 w-4" />}{running ? "Investigating…" : "INVESTIGATE"}
        </button>
      </div>
      <ErrorBox error={start.error} />

      <div className="grid gap-4 xl:grid-cols-12">
        {/* LEFT: transaction */}
        <div className="space-y-4 xl:col-span-3">
          <Card title="Transaction" icon={<CreditCard className="h-4 w-4" />}>
            <div className="font-mono text-3xl font-semibold">{usd(t.amount)}</div>
            <div className="mt-1 text-xs text-fog-400">{t.description}</div>
            <div className="mt-3 divide-y divide-ink-700/60">
              <KV k="Customer" v={<Link className="hover:text-cyan-300" to={`/console/network?entity=${d.customer.id}`}>{d.customer.name} <span className="font-mono text-xs text-fog-400">{d.customer.id}</span></Link>} />
              <KV k="Home" v={`${d.customer.city}, ${d.customer.country}`} />
              <KV k={d.merchant ? "Merchant" : "P2P to"} v={d.merchant ? <span>{d.merchant.name}{d.merchant.high_risk_category && <span className="ml-1 text-[10px] text-amber-300">HIGH-RISK CAT.</span>}</span> : d.destination.label} />
              <KV k="Destination" v={<span className={d.destination.flagged ? "text-rose-300" : ""}>{d.destination.id}{d.destination.flagged && " ⚑"}</span>} mono />
              <KV k="Device" v={<span className="flex items-center gap-1"><Fingerprint className="h-3 w-3" />{d.device.id} · {d.device.type}</span>} mono />
              <KV k="Location" v={`${d.location.lat.toFixed(2)}, ${d.location.lon.toFixed(2)}`} mono />
              <KV k="Review" v={<StatusPill status={t.review_status} />} />
            </div>
          </Card>
          {p && (
            <Card title="ML risk assessment" icon={<Radar className="h-4 w-4" />} actions={<span className="font-mono text-[10px] text-fog-400">{p.model_algorithm} {p.model_version}</span>}>
              <div className="label mb-1">Fraud probability</div>
              <ProbabilityBar value={p.fraud_probability} />
              <div className="label mb-1 mt-3">Anomaly percentile (Isolation Forest)</div>
              <ProbabilityBar value={p.anomaly_score} />
              <div className="label mb-1 mt-3">Graph risk</div>
              <ProbabilityBar value={p.graph_risk_score} />
              <div className="mt-3 space-y-1">
                {p.policy_notes.map((n) => <div key={n} className="text-[11.5px] text-fog-300">↳ {n}</div>)}
              </div>
              <div className="label mb-1 mt-4">SHAP drivers ({p.shap.space})</div>
              <ShapChart values={p.shap.values} features={p.features} height={210} />
              <ul className="mt-2 space-y-1">
                {p.top_risk_factors.map((f) => <li key={f} className="text-[11.5px] text-fog-300">• {f}</li>)}
              </ul>
            </Card>
          )}
        </div>

        {/* CENTRE: graph */}
        <div className="xl:col-span-6">
          <Card title="Financial relationship graph" icon={<Network className="h-4 w-4" />} bodyClass="p-0"
            actions={<span className="text-[11px] text-fog-400">hover to inspect · click for evidence</span>}>
            {graph.data ? <GraphView data={graph.data} height={620} onSelectNode={(n) => { setSelNode(n); setSelEdge(null); }} onSelectEdge={(e) => { setSelEdge(e); setSelNode(null); }} /> : <Loading label="Building graph" />}
            <AnimatePresence>
              {(selNode || selEdge) && (
                <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="border-t border-ink-700 p-4 text-sm">
                  {selNode && <NodeInspector n={selNode} />}
                  {selEdge && <EdgeInspector e={selEdge} />}
                </motion.div>
              )}
            </AnimatePresence>
          </Card>
        </div>

        {/* RIGHT: AI report */}
        <div className="xl:col-span-3">
          <Card title="AI investigation report" icon={<Bot className="h-4 w-4" />}
            actions={inv.data && <span className={`rounded border px-1.5 py-0.5 font-mono text-[10px] ${inv.data.mode === "LLM_AGENT" ? "border-fuchsia-400/40 text-fuchsia-300" : "border-amber-400/40 text-amber-300"}`}>{inv.data.mode === "LLM_AGENT" ? `LLM · ${inv.data.llm_model}` : "DETERMINISTIC FALLBACK"}</span>}>
            {!invId && !start.isPending && (
              <div className="py-6 text-center text-sm text-fog-400">
                No investigation yet.<br />Press <b className="text-cyan-300">INVESTIGATE</b> to run the LangGraph agent.
              </div>
            )}
            {inv.data && <StepList steps={inv.data.steps} running={inv.data.status === "RUNNING"} />}
            {inv.data?.status === "FAILED" && <ErrorBox error={inv.data.error} />}
            {inv.data?.report && <Report r={inv.data.report} />}
          </Card>
        </div>
      </div>

      {/* BOTTOM: evidence timeline + decisions */}
      <div className="mt-4 grid gap-4 xl:grid-cols-12">
        <Card title="Evidence timeline" icon={<FileText className="h-4 w-4" />} className="xl:col-span-7">
          {!inv.data?.report ? <div className="text-sm text-fog-400">Evidence appears here once the agent collects it.</div> : (
            <ol className="relative space-y-2 border-l border-ink-600 pl-5">
              {inv.data.report.evidence.map((e, i) => (
                <motion.li key={e.key} initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.04 }} className="relative">
                  <span className={`absolute -left-[26px] top-1 h-2.5 w-2.5 rounded-full border-2 border-ink-850 ${e.mitigating ? "bg-emerald-400" : e.severity === "HIGH" ? "bg-rose-500" : e.severity === "MEDIUM" ? "bg-amber-400" : "bg-fog-500"}`} />
                  <div className="flex flex-wrap items-center gap-2 text-xs">
                    <span className="font-mono font-semibold text-cyan-300">{e.key}</span>
                    <span className={`rounded border px-1 font-mono text-[10px] ${SEV[e.severity]}`}>{e.severity}</span>
                    {e.mitigating && <span className="rounded border border-emerald-400/30 px-1 font-mono text-[10px] text-emerald-300">MITIGATING</span>}
                    <span className="font-mono text-[10px] text-fog-500">{e.tool} · {e.category}</span>
                  </div>
                  <div className="mt-0.5 text-[13px] text-fog-200">{e.summary}</div>
                </motion.li>
              ))}
            </ol>
          )}
        </Card>
        <Card title="Decision & history" icon={<Gavel className="h-4 w-4" />} className="xl:col-span-5">
          <DecisionPanel txnId={t.id} status={t.status} riskLevel={t.risk_level} recommendation={inv.data?.report?.recommendation} />
          {d.paypal_order && (
            <div className="mt-4 rounded-lg border border-ink-700 bg-ink-900/60 p-3 text-xs">
              <div className="label mb-1.5">PayPal order (separate from Sentinel risk status)</div>
              <div className="flex flex-wrap gap-x-4 gap-y-1">
                <span>Order <span className="font-mono">{d.paypal_order.paypal_order_id}</span></span>
                <span className="flex items-center gap-1">PayPal <StatusPill status={d.paypal_order.paypal_status} /></span>
                <span className="flex items-center gap-1">Capture {d.paypal_order.capture_status ? <StatusPill status={d.paypal_order.capture_status} /> : "none"}</span>
                <span className="flex items-center gap-1">Sentinel <StatusPill status={d.paypal_order.sentinel_status} /></span>
              </div>
            </div>
          )}
          <div className="label mb-2 mt-4">Decisions</div>
          {!d.decisions.length && <div className="text-xs text-fog-500">No reviewer decisions yet.</div>}
          {d.decisions.map((x) => (
            <div key={x.id} className="mb-2 rounded-lg border border-ink-700 bg-ink-900/60 p-2.5 text-xs">
              <div className="flex items-center justify-between"><StatusPill status={x.decision === "APPROVE" ? "APPROVED" : x.decision === "REJECT" ? "REJECTED" : "ESCALATED"} /><span className="text-fog-500">{dt(x.created_at)}</span></div>
              <div className="mt-1 text-fog-300">{x.reason}</div>
              <div className="mt-1 font-mono text-[10.5px] text-fog-400">{x.reviewer} · outcome: {x.payment_outcome}</div>
            </div>
          ))}
          <div className="label mb-2 mt-4">Audit trail</div>
          <div className="max-h-56 space-y-1 overflow-y-auto pr-1">
            {d.audit.slice().reverse().map((a) => (
              <div key={a.id} className="flex items-start gap-2 text-[11.5px]">
                <span className="font-mono text-fog-500">#{a.id}</span>
                <span className="font-mono text-cyan-200">{a.action}</span>
                <span className="truncate text-fog-400">{a.actor}</span>
                <span className="ml-auto shrink-0 font-mono text-[10px] text-fog-500">{a.hash}</span>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}

function StepList({ steps, running }: { steps: Step[]; running: boolean }) {
  return (
    <ol className="space-y-1.5">
      {steps.map((s, i) => (
        <motion.li key={`${s.name}-${i}`} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} className="rounded-lg border border-ink-700 bg-ink-900/50 px-2.5 py-2">
          <div className="flex items-center gap-2 text-xs">
            {s.status === "COMPLETED" ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" /> : s.status === "ERROR" ? <XCircle className="h-3.5 w-3.5 text-rose-400" /> : <Spinner className="text-cyan-300" />}
            <span className="font-medium text-fog-100">{s.name}</span>
            {s.duration_ms != null && <span className="ml-auto font-mono text-[10px] text-fog-500">{s.duration_ms}ms</span>}
          </div>
          <div className="mt-0.5 flex items-center gap-1 font-mono text-[10px] text-fog-500"><Wrench className="h-2.5 w-2.5" />{s.tool}</div>
          {s.summary && <div className="mt-1 text-[11.5px] text-fog-300">{s.summary}</div>}
        </motion.li>
      ))}
      {running && <li className="flex items-center gap-2 px-2.5 py-1 text-xs text-cyan-300"><CircleDashed className="h-3.5 w-3.5 animate-spin" />agent working…</li>}
    </ol>
  );
}

function Report({ r }: { r: NonNullable<Investigation["report"]> }) {
  const recTone = r.recommendation === "APPROVE" ? "border-emerald-400/40 bg-emerald-400/10 text-emerald-200" : r.recommendation === "REJECT" ? "border-rose-400/40 bg-rose-500/10 text-rose-200" : "border-amber-400/40 bg-amber-400/10 text-amber-100";
  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-4 space-y-3 border-t border-ink-700 pt-4">
      <div className="flex items-center justify-between"><div className="label">Investigation report</div><RiskBadge level={r.risk_level} /></div>
      {r.mode !== "LLM_AGENT" && (
        <div className="flex gap-2 rounded-md border border-amber-400/30 bg-amber-400/5 p-2 text-[11px] text-amber-200">
          <AlertTriangle className="h-3.5 w-3.5 shrink-0" />Deterministic rule-based report — not LLM-generated.{r.fallback_reason ? ` ${r.fallback_reason}` : ""}
        </div>
      )}
      <p className="text-[13px] leading-relaxed text-fog-200">{r.summary}</p>
      <div>
        <div className="label mb-1.5">Evidence-backed findings</div>
        <ul className="space-y-1.5">
          {r.findings.map((f, i) => (
            <li key={i} className="text-[12.5px] text-fog-200">
              • {f.statement} {f.evidence_keys.map((k) => <span key={k} className="ml-1 rounded bg-cyan-400/10 px-1 font-mono text-[10px] text-cyan-300">{k}</span>)}
            </li>
          ))}
        </ul>
      </div>
      {r.rejected_findings.length > 0 && <div className="text-[11px] text-fog-500">{r.rejected_findings.length} unsupported statement(s) removed by InvestigationReportTool.</div>}
      <div className={`rounded-lg border p-3 ${recTone}`}>
        <div className="label !text-current opacity-80">Recommendation</div>
        <div className="mt-0.5 font-mono text-lg font-semibold">{r.recommendation.replaceAll("_", " ")}</div>
        <div className="mt-1 text-xs opacity-90">{r.rationale}</div>
      </div>
      <div className="flex items-start gap-1.5 text-[10.5px] text-fog-500"><ShieldCheck className="mt-0.5 h-3 w-3 shrink-0" />{r.notice}</div>
    </motion.div>
  );
}

export function NodeInspector({ n }: { n: GNode }) {
  return (
    <div>
      <div className="flex items-center gap-2"><span className="font-mono text-xs text-fog-400">{n.type}</span><span className="font-semibold">{n.label}</span><span className="font-mono text-xs text-cyan-300">{n.ref_id}</span><span className="ml-auto font-mono text-xs">risk {n.risk.toFixed(2)}</span></div>
      {n.flags.map((f) => <div key={f} className="mt-1 text-xs text-rose-300">⚑ {f}</div>)}
      <div className="mt-1 flex flex-wrap gap-x-4 text-xs text-fog-400">{Object.entries(n.details).map(([k, v]) => <span key={k}>{k}: <span className="font-mono text-fog-200">{String(v)}</span></span>)}</div>
      {n.type === "TRANSACTION" ? <Link className="mt-2 inline-block text-xs text-cyan-300 hover:underline" to={`/console/investigate/${n.ref_id}`}>Open transaction →</Link>
        : <Link className="mt-2 inline-block text-xs text-cyan-300 hover:underline" to={`/console/network?entity=${n.ref_id}`}>Explore {n.ref_id} in network graph →</Link>}
    </div>
  );
}

export function EdgeInspector({ e }: { e: GEdge }) {
  return (
    <div>
      <div className="flex items-center gap-2 text-xs"><span className="font-mono text-cyan-300">{e.type}</span><span className="font-mono text-fog-400">{e.source.split(":")[1]} → {e.target.split(":")[1]}</span>
        <span className="ml-auto font-mono">{e.count} txn · {usd(e.amount)}</span></div>
      {e.evidence.length ? e.evidence.map((x) => <div key={x} className="mt-1 text-xs text-rose-300">⚑ {x}</div>) : <div className="mt-1 text-xs text-fog-500">No suspicious evidence on this relationship.</div>}
      {e.transaction_ids.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">{e.transaction_ids.map((id) => <Link key={id} to={`/console/investigate/${id}`} className="rounded bg-ink-700 px-1.5 py-0.5 font-mono text-[10px] text-fog-200 hover:text-cyan-300">{id}</Link>)}</div>
      )}
    </div>
  );
}
