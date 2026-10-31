import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, CreditCard, Database, Save, SlidersHorizontal, User } from "lucide-react";
import { useEffect, useState } from "react";
import { Card, ErrorBox, KV, Loading, PageHeader, RiskBadge, Spinner } from "../../components/ui";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";

interface Policy { low_max: number; medium_max: number; high_max: number; anomaly_escalation: number; amount_ratio_escalation: number; graph_escalation: boolean; auto_investigate_levels: string[] }

export default function Settings() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const integ = useQuery({ queryKey: ["integrations"], queryFn: () => api<any>("/api/settings/integrations") });
  const pol = useQuery({ queryKey: ["policy"], queryFn: () => api<{ policy: Policy; defaults: Policy }>("/api/settings/risk-policy") });
  const [p, setP] = useState<Policy | null>(null);
  useEffect(() => { if (pol.data) setP(pol.data.policy); }, [pol.data]);
  const save = useMutation({ mutationFn: (body: Policy) => api("/api/settings/risk-policy", { method: "PUT", json: body }), onSuccess: () => qc.invalidateQueries({ queryKey: ["policy"] }) });
  const admin = user?.role === "ADMIN";
  const i = integ.data;
  const num = (k: keyof Policy, label: string, step = 0.01) => (
    <label className="block">
      <span className="label">{label}</span>
      <input className="input mt-1 font-mono" type="number" step={step} disabled={!admin} value={p ? (p[k] as number) : ""} onChange={(e) => setP({ ...p!, [k]: Number(e.target.value) })} />
    </label>
  );

  return (
    <div>
      <PageHeader title="Settings" subtitle="Integrations, risk policy and session" />
      <div className="grid gap-4 xl:grid-cols-3">
        <Card title="Integrations" icon={<CreditCard className="h-4 w-4" />}>
          {!i ? <Loading /> : (
            <div className="divide-y divide-ink-700/60">
              <KV k="PayPal Sandbox" v={<Dot ok={i.paypal.configured} text={i.paypal.configured ? "configured" : "not configured"} />} />
              <KV k="PayPal API" v={i.paypal.base_url} mono />
              <KV k="Webhook verification" v={<Dot ok={i.paypal.webhook_verification} text={i.paypal.webhook_verification ? "PAYPAL_WEBHOOK_ID set" : "not configured"} />} />
              <KV k={<span className="flex items-center gap-1"><Bot className="h-3.5 w-3.5" />Groq LLM</span>} v={<Dot ok={i.groq.configured} text={i.groq.configured ? i.groq.model : "fallback (rules)"} />} />
              <KV k={<span className="flex items-center gap-1"><Database className="h-3.5 w-3.5" />Database</span>} v={i.database} mono />
              <KV k="Rate limiter" v={i.rate_limiter} mono />
              <KV k="Environment" v={i.environment} mono />
            </div>
          )}
          {i && !i.paypal.configured && (
            <div className="mt-4 rounded-lg border border-amber-400/30 bg-amber-400/5 p-3 text-xs text-amber-100">
              <div className="mb-1 font-semibold">Enable PayPal Sandbox</div>
              <ol className="list-decimal space-y-1 pl-4 text-amber-200/90">
                <li>developer.paypal.com → Apps & Credentials → Sandbox → Create App.</li>
                <li>Copy Client ID and Secret into <span className="font-mono">PAYPAL_CLIENT_ID</span> / <span className="font-mono">PAYPAL_CLIENT_SECRET</span> in <span className="font-mono">.env</span>.</li>
                <li>Optional: add a webhook to <span className="font-mono">/api/paypal/webhook</span> and set <span className="font-mono">PAYPAL_WEBHOOK_ID</span>.</li>
                <li>Restart the backend.</li>
              </ol>
            </div>
          )}
        </Card>
        <Card title="Risk policy" icon={<SlidersHorizontal className="h-4 w-4" />} className="xl:col-span-2"
          actions={admin ? <button className="btn-primary px-3 py-1.5 text-xs" disabled={save.isPending || !p} onClick={() => p && save.mutate(p)}>{save.isPending ? <Spinner /> : <Save className="h-3.5 w-3.5" />}Save policy</button> : <span className="text-xs text-fog-500">read-only (ADMIN edits)</span>}>
          {!p ? <Loading /> : (
            <>
              <div className="mb-4 flex h-3 overflow-hidden rounded-full">
                <div style={{ width: `${p.low_max * 100}%` }} className="bg-risk-low" />
                <div style={{ width: `${(p.medium_max - p.low_max) * 100}%` }} className="bg-risk-medium" />
                <div style={{ width: `${(p.high_max - p.medium_max) * 100}%` }} className="bg-risk-high" />
                <div style={{ width: `${(1 - p.high_max) * 100}%` }} className="bg-risk-critical" />
              </div>
              <div className="grid gap-3 md:grid-cols-3">
                {num("low_max", "LOW below")}{num("medium_max", "MEDIUM below")}{num("high_max", "HIGH below (else CRITICAL)")}
                {num("anomaly_escalation", "Anomaly percentile → ≥ MEDIUM")}{num("amount_ratio_escalation", "Amount × average → ≥ MEDIUM", 0.5)}
                <label className="block">
                  <span className="label">Graph escalation → ≥ HIGH</span>
                  <select className="input mt-1" disabled={!admin} value={String(p.graph_escalation)} onChange={(e) => setP({ ...p, graph_escalation: e.target.value === "true" })}>
                    <option value="true">enabled</option><option value="false">disabled</option>
                  </select>
                </label>
              </div>
              <div className="mt-4">
                <span className="label">Auto-investigate levels (PayPal & demo payments)</span>
                <div className="mt-2 flex gap-2">
                  {["MEDIUM", "HIGH", "CRITICAL"].map((l) => (
                    <button key={l} disabled={!admin} onClick={() => setP({ ...p, auto_investigate_levels: p.auto_investigate_levels.includes(l) ? p.auto_investigate_levels.filter((x) => x !== l) : [...p.auto_investigate_levels, l] })}
                      className={`rounded-lg border px-2 py-1.5 ${p.auto_investigate_levels.includes(l) ? "border-cyan-400/50 bg-cyan-400/10" : "border-ink-600 opacity-50"}`}><RiskBadge level={l} /></button>
                  ))}
                </div>
              </div>
              <div className="mt-4 rounded-lg border border-ink-700 bg-ink-900/60 p-3 text-xs text-fog-400">
                Policy actions: <b className="text-emerald-300">LOW</b> → automatic PayPal capture · <b className="text-amber-300">MEDIUM</b> → additional verification by a reviewer ·
                <b className="text-orange-300"> HIGH</b>/<b className="text-rose-300">CRITICAL</b> → held, never captured without a reviewer APPROVE. Escalations only increase risk; they never lower it. Changes are audited.
              </div>
              <div className="mt-3"><ErrorBox error={save.error} />{save.isSuccess && <div className="text-xs text-emerald-300">Policy saved and audited.</div>}</div>
            </>
          )}
        </Card>
        <Card title="Session" icon={<User className="h-4 w-4" />}>
          <KV k="Name" v={user?.full_name} />
          <KV k="Email" v={user?.email} mono />
          <KV k="Role" v={user?.role} mono />
          <p className="mt-3 text-xs text-fog-400">Roles: ADMIN (policy, retraining, escalations), REVIEWER (payment decisions), ANALYST (read & investigate), CUSTOMER (shopper).</p>
        </Card>
      </div>
    </div>
  );
}

function Dot({ ok, text }: { ok: boolean; text: string }) {
  return <span className="flex items-center gap-1.5"><span className={`h-2 w-2 rounded-full ${ok ? "bg-emerald-400" : "bg-amber-400"}`} />{text}</span>;
}
