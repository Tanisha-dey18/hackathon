import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import {
  Activity, AlertOctagon, Ban, BrainCircuit, CheckCircle2, Clock, CreditCard, ExternalLink, Network, Pause, Play, Radio,
  ScanSearch, ShieldAlert, Zap,
} from "lucide-react";
import { Link } from "react-router-dom";
import {
  Area, AreaChart, Bar, BarChart, Cell, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid,
} from "recharts";
import { axis, ChartTooltip, grid } from "../../components/charts";
import { Card, ErrorBox, Loading, PageHeader, RiskBadge, Spinner, Stat, StatusPill, SyntheticTag } from "../../components/ui";
import { api } from "../../lib/api";
import { ago, num, pct, RISK_COLORS, usd } from "../../lib/format";
import { useLive } from "../../lib/live";

export interface Metrics {
  data_label: string;
  kpis: Record<string, number | null>;
  volume_series: { date: string; count: number; amount: number; LOW: number; MEDIUM: number; HIGH: number; CRITICAL: number; rejected: number }[];
  risk_distribution: Record<string, number>;
  probability_histogram: { bucket: string; count: number }[];
  paypal_status_distribution: Record<string, number>;
  sentinel_status_distribution: Record<string, number>;
  channels: Record<string, number>;
  network: { suspicious_clusters: number; shared_devices: number; cycles: number; flagged_destinations: number; nodes: number; edges: number; clusters: number };
  model: { version: string; algorithm: string; precision: number; recall: number; f1: number; roc_auc: number; pr_auc: number } | null;
  investigations: Record<string, number>;
  simulator: { running: boolean; generated: number };
}

export default function CommandCentre() {
  const q = useQuery({ queryKey: ["dashboard"], queryFn: () => api<Metrics>("/api/dashboard/metrics"), refetchInterval: 15000 });
  if (q.isLoading) return <Loading label="Loading command centre" />;
  if (!q.data) return <ErrorBox error={q.error} />;
  const m = q.data;
  const k = m.kpis;
  return (
    <div>
      <PageHeader title="Command Centre" subtitle={<span className="flex flex-wrap items-center gap-2">Real-time payment risk posture <SyntheticTag text={m.data_label.toUpperCase()} /></span>} />
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">
        <Stat label="Analysed" value={num(k.transactions_analysed)} sub="transactions scored" icon={<Activity className="h-4 w-4" />} />
        <Stat label="Suspicious" value={num(k.suspicious)} sub="medium risk or above" icon={<ShieldAlert className="h-4 w-4" />} tone="amber" delay={0.03} />
        <Stat label="Critical" value={num(k.critical)} sub={`${num(k.high)} high`} icon={<AlertOctagon className="h-4 w-4" />} tone="rose" delay={0.06} />
        <Stat label="Awaiting review" value={num(k.awaiting_review)} sub="human decision pending" icon={<Clock className="h-4 w-4" />} tone="amber" delay={0.09} />
        <Stat label="PayPal captured" value={num(k.captured_paypal_payments)} sub={usd(k.captured_amount)} icon={<CreditCard className="h-4 w-4" />} tone="emerald" delay={0.12} />
        <Stat label="Rejected" value={num(k.blocked_or_rejected)} sub="blocked by reviewers" icon={<Ban className="h-4 w-4" />} tone="rose" delay={0.15} />
        <Stat label="Avg processing" value={k.avg_processing_ms != null ? `${k.avg_processing_ms}ms` : "—"} sub={`${num(k.live_assessments)} live assessments`} icon={<Zap className="h-4 w-4" />} tone="fog" delay={0.18} />
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-3">
        <Card title="Transaction volume · 30 days" icon={<Activity className="h-4 w-4" />} className="xl:col-span-2">
          <ResponsiveContainer width="100%" height={470}>
            <AreaChart data={m.volume_series} margin={{ left: -18, right: 8, top: 8 }}>
              <defs>
                {Object.entries(RISK_COLORS).map(([lvl, c]) => (
                  <linearGradient key={lvl} id={`g-${lvl}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={c} stopOpacity={0.45} /><stop offset="100%" stopColor={c} stopOpacity={0.02} />
                  </linearGradient>
                ))}
              </defs>
              <CartesianGrid {...grid} />
              <XAxis dataKey="date" {...axis} tickFormatter={(d) => d.slice(5)} minTickGap={24} />
              <YAxis {...axis} allowDecimals={false} />
              <Tooltip content={<ChartTooltip />} />
              {["LOW", "MEDIUM", "HIGH", "CRITICAL"].map((lvl) => (
                <Area key={lvl} type="monotone" dataKey={lvl} name={lvl} stackId="1" stroke={RISK_COLORS[lvl]} fill={`url(#g-${lvl})`} strokeWidth={1.5} />
              ))}
            </AreaChart>
          </ResponsiveContainer>
        </Card>
        <DemoLauncher />
      </div>

      <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Card title="Risk distribution" icon={<ShieldAlert className="h-4 w-4" />}>
          <ResponsiveContainer width="100%" height={190}>
            <PieChart>
              <Pie data={Object.entries(m.risk_distribution).map(([name, value]) => ({ name, value }))} dataKey="value" nameKey="name"
                innerRadius={52} outerRadius={78} paddingAngle={2} stroke="none">
                {Object.keys(m.risk_distribution).map((l) => <Cell key={l} fill={RISK_COLORS[l]} />)}
              </Pie>
              <Tooltip content={<ChartTooltip />} />
            </PieChart>
          </ResponsiveContainer>
          <div className="grid grid-cols-2 gap-1.5">
            {Object.entries(m.risk_distribution).map(([l, v]) => (
              <div key={l} className="flex items-center justify-between rounded-md bg-ink-900/60 px-2 py-1 text-xs"><RiskBadge level={l} /><span className="font-mono">{num(v)}</span></div>
            ))}
          </div>
        </Card>
        <Card title="Fraud probability histogram" icon={<BrainCircuit className="h-4 w-4" />}>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={m.probability_histogram} margin={{ left: -14, right: 4, top: 8 }}>
              <CartesianGrid {...grid} />
              <XAxis dataKey="bucket" {...axis} tickFormatter={(b) => b.split("-")[0]} />
              <YAxis {...axis} scale="sqrt" allowDecimals={false} />
              <Tooltip content={<ChartTooltip />} />
              <Bar dataKey="count" name="transactions" radius={[3, 3, 0, 0]}>
                {m.probability_histogram.map((_, i) => <Cell key={i} fill={i >= 9 ? RISK_COLORS.CRITICAL : i >= 7 ? RISK_COLORS.HIGH : i >= 3 ? RISK_COLORS.MEDIUM : RISK_COLORS.LOW} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>
        <Card title="Fraud detection trend" icon={<AlertOctagon className="h-4 w-4" />}>
          <ResponsiveContainer width="100%" height={250}>
            <LineChart data={m.volume_series.map((d) => ({ ...d, flagged: d.HIGH + d.CRITICAL }))} margin={{ left: -18, right: 8, top: 8 }}>
              <CartesianGrid {...grid} />
              <XAxis dataKey="date" {...axis} tickFormatter={(d) => d.slice(5)} minTickGap={30} />
              <YAxis {...axis} allowDecimals={false} />
              <Tooltip content={<ChartTooltip />} />
              <Line dataKey="flagged" name="high + critical" stroke={RISK_COLORS.CRITICAL} strokeWidth={2} dot={false} />
              <Line dataKey="MEDIUM" name="medium" stroke={RISK_COLORS.MEDIUM} strokeWidth={1.5} dot={false} />
              <Line dataKey="rejected" name="rejected" stroke="#a78bfa" strokeWidth={1.5} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </Card>
        <Card title="Payment status" icon={<CreditCard className="h-4 w-4" />}>
          <div className="label mb-2">PayPal order status</div>
          <StatusBars data={m.paypal_status_distribution} empty="No PayPal orders yet" />
          <div className="label mb-2 mt-4">Sentinel decision status</div>
          <StatusBars data={m.sentinel_status_distribution} empty="—" />
        </Card>
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-3">
        <Card title="Suspicious network activity" icon={<Network className="h-4 w-4" />} actions={<Link to="/console/network" className="text-xs text-cyan-300 hover:underline">Explore graph →</Link>}>
          <div className="grid grid-cols-2 gap-3">
            {[
              ["Suspicious clusters", m.network.suspicious_clusters, "rose"], ["Shared devices", m.network.shared_devices, "amber"],
              ["Circular loops", m.network.cycles, "rose"], ["Flagged destinations", m.network.flagged_destinations, "amber"],
            ].map(([l, v, t]) => (
              <div key={l as string} className="rounded-lg border border-ink-700 bg-ink-900/60 p-3">
                <div className="label">{l}</div>
                <div className={`mt-1 font-mono text-2xl font-semibold ${t === "rose" ? "text-rose-300" : "text-amber-300"}`}>{v as number}</div>
              </div>
            ))}
          </div>
          <div className="mt-3 text-xs text-fog-400">Graph of {num(m.network.nodes)} entities and {num(m.network.edges)} relationships (NetworkX).</div>
        </Card>
        <Card title="Risk model performance (hold-out)" icon={<BrainCircuit className="h-4 w-4" />} actions={<Link to="/console/models" className="text-xs text-cyan-300 hover:underline">Details →</Link>}>
          {m.model ? (
            <>
              <div className="mb-3 font-mono text-xs text-fog-400">{m.model.algorithm} · {m.model.version}</div>
              {(["pr_auc", "roc_auc", "precision", "recall", "f1"] as const).map((key) => (
                <div key={key} className="mb-2">
                  <div className="flex justify-between text-xs"><span className="uppercase tracking-wider text-fog-400">{key.replace("_", "-")}</span><span className="font-mono">{m.model![key].toFixed(3)}</span></div>
                  <div className="mt-1 h-1.5 rounded-full bg-ink-700"><motion.div className="h-full rounded-full bg-cyan-400" initial={{ width: 0 }} animate={{ width: pct(m.model![key], 0) }} /></div>
                </div>
              ))}
            </>
          ) : <div className="text-sm text-fog-400">No model trained.</div>}
        </Card>
        <LiveFeed />
      </div>
    </div>
  );
}

function StatusBars({ data, empty }: { data: Record<string, number>; empty: string }) {
  const total = Object.values(data).reduce((a, b) => a + b, 0);
  if (!total) return <div className="text-xs text-fog-500">{empty}</div>;
  return (
    <div className="space-y-1.5">
      {Object.entries(data).sort((a, b) => b[1] - a[1]).map(([s, v]) => (
        <div key={s} className="flex items-center gap-2">
          <div className="w-40 shrink-0"><StatusPill status={s} /></div>
          <div className="h-1.5 flex-1 rounded-full bg-ink-700"><div className="h-full rounded-full bg-cyan-400/70" style={{ width: `${(v / total) * 100}%` }} /></div>
          <span className="w-6 text-right font-mono text-xs">{v}</span>
        </div>
      ))}
    </div>
  );
}

interface ScenarioRun { scenario: string; transaction_id: string; status: string; action: string; investigation_id: string | null;
  risk: { risk_level: string; fraud_probability: number; top_risk_factors: string[]; policy_notes: string[] } }

function DemoLauncher() {
  const qc = useQueryClient();
  const sc = useQuery({ queryKey: ["scenarios"], queryFn: () => api<{ scenarios: any[]; paypal_configured: boolean }>("/api/demo/scenarios") });
  const sim = useQuery({ queryKey: ["simulator"], queryFn: () => api<{ running: boolean; generated: number; last_error: string | null }>("/api/demo/simulator"), refetchInterval: 4000 });
  const run = useMutation({
    mutationFn: (key: string) => api<ScenarioRun>(`/api/demo/scenarios/${key}/run`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["dashboard"] }),
  });
  const simToggle = useMutation({
    mutationFn: (action: "start" | "stop") => api("/api/demo/simulator", { method: "POST", json: { action, interval_seconds: 3 } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["simulator"] }),
  });
  const r = run.data;
  return (
    <Card title="Demonstration scenarios" icon={<ScanSearch className="h-4 w-4" />} actions={<SyntheticTag text="SYNTHETIC" />}>
      <div className="space-y-2">
        {sc.data?.scenarios.map((s) => (
          <div key={s.key} className="rounded-lg border border-ink-700 bg-ink-900/60 p-3">
            <div className="flex items-start justify-between gap-2">
              <div>
                <div className="text-sm font-semibold"><span className="mr-1.5 font-mono text-cyan-300">{s.key}</span>{s.title}</div>
                <div className="mt-0.5 text-[11.5px] leading-snug text-fog-400">{s.description}</div>
              </div>
            </div>
            <div className="mt-2 flex flex-wrap gap-2">
              <button className="btn-primary px-2.5 py-1 text-xs" disabled={run.isPending} onClick={() => run.mutate(s.key)}>
                {run.isPending && run.variables === s.key ? <Spinner /> : <Play className="h-3 w-3" />} Run risk pipeline
              </button>
              <Link to={`/shop/demo/${s.key}`} className="btn-ghost px-2.5 py-1 text-xs" title={sc.data?.paypal_configured ? "" : "PayPal not configured"}>
                <CreditCard className="h-3 w-3" /> PayPal checkout
                {!sc.data?.paypal_configured && <span className="text-amber-300">(not configured)</span>}
              </Link>
            </div>
          </div>
        ))}
      </div>
      <ErrorBox error={run.error} />
      <AnimatePresence>
        {r && (
          <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} className="mt-3 rounded-lg border border-cyan-400/25 bg-cyan-400/5 p-3 text-xs">
            <div className="flex items-center justify-between"><span className="font-mono">{r.transaction_id}</span><RiskBadge level={r.risk.risk_level} /></div>
            <div className="mt-1 text-fog-300">p(fraud) {r.risk.fraud_probability.toFixed(3)} · <StatusPill status={r.status} /></div>
            {r.risk.policy_notes.slice(1).map((n) => <div key={n} className="mt-1 text-amber-200">↳ {n}</div>)}
            <Link to={`/console/investigate/${r.transaction_id}`} className="mt-2 inline-flex items-center gap-1 text-cyan-300 hover:underline">
              Open investigation workspace <ExternalLink className="h-3 w-3" />
            </Link>
          </motion.div>
        )}
      </AnimatePresence>
      <div className="mt-3 flex items-center justify-between rounded-lg border border-ink-700 bg-ink-900/60 p-3">
        <div>
          <div className="text-sm font-medium">Live traffic simulator</div>
          <div className="text-[11px] text-fog-400">{sim.data?.running ? `running · ${sim.data.generated} generated` : "Synthetic transactions through the real risk engine"}</div>
          {sim.data?.last_error && <div className="text-[11px] text-rose-300">{sim.data.last_error}</div>}
        </div>
        <button className={sim.data?.running ? "btn-danger px-2.5 py-1 text-xs" : "btn-ghost px-2.5 py-1 text-xs"} onClick={() => simToggle.mutate(sim.data?.running ? "stop" : "start")}>
          {sim.data?.running ? <><Pause className="h-3 w-3" />Stop</> : <><Radio className="h-3 w-3" />Start</>}
        </button>
      </div>
    </Card>
  );
}

function LiveFeed() {
  const { events, connected } = useLive();
  const icon = (e: string) => e.startsWith("payment") ? <CreditCard className="h-3.5 w-3.5 text-sky-300" /> :
    e.startsWith("investigation") ? <BrainCircuit className="h-3.5 w-3.5 text-fuchsia-300" /> :
      e === "decision.made" ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-300" /> : <Activity className="h-3.5 w-3.5 text-cyan-300" />;
  return (
    <Card title="Live event stream" icon={<Radio className="h-4 w-4" />} actions={<span className={`h-2 w-2 rounded-full ${connected ? "bg-emerald-400" : "bg-rose-500"}`} />} bodyClass="p-0">
      <div className="max-h-[300px] overflow-y-auto">
        {!events.length && <div className="p-6 text-center text-xs text-fog-500">Waiting for events… run a scenario or start the simulator.</div>}
        <AnimatePresence initial={false}>
          {events.map((e) => (
            <motion.div key={`${e.ts}-${e.event}-${e.data.transaction_id ?? e.data.investigation_id}`} initial={{ opacity: 0, x: -8, backgroundColor: "rgba(34,211,238,.12)" }}
              animate={{ opacity: 1, x: 0, backgroundColor: "rgba(0,0,0,0)" }} transition={{ duration: 0.6 }}
              className="flex items-center gap-2 border-b border-ink-700/50 px-4 py-2 text-xs">
              {icon(e.event)}
              <span className="font-mono text-fog-300">{e.event}</span>
              {e.data.transaction_id && <Link to={`/console/investigate/${e.data.transaction_id}`} className="font-mono text-cyan-300 hover:underline">{e.data.transaction_id}</Link>}
              {e.data.risk_level && <RiskBadge level={e.data.risk_level} />}
              {e.data.amount != null && <span className="font-mono text-fog-400">{usd(e.data.amount)}</span>}
              {e.data.step && <span className="truncate text-fog-400">{e.data.step.name}</span>}
              <span className="ml-auto shrink-0 text-fog-500">{ago(e.ts)}</span>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </Card>
  );
}
