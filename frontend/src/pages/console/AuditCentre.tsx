import { useMutation, useQuery } from "@tanstack/react-query";
import { FileClock, Link2, ShieldCheck, ShieldX } from "lucide-react";
import { useState } from "react";
import { Card, ErrorBox, Loading, Modal, PageHeader, Spinner } from "../../components/ui";
import { api } from "../../lib/api";
import { dt } from "../../lib/format";

interface Row { id: number; actor: string; action: string; entity_type: string; entity_id: string; details: any; hash: string; prev_hash: string; created_at: string }

export default function AuditCentre() {
  const [action, setAction] = useState("");
  const [entity, setEntity] = useState("");
  const q = useQuery({ queryKey: ["audit", action, entity], queryFn: () => api<Row[]>(`/api/audit?limit=500${action ? `&action=${action}` : ""}${entity ? `&entity_id=${encodeURIComponent(entity)}` : ""}`), refetchInterval: 15000 });
  const verify = useMutation({ mutationFn: () => api<{ valid: boolean; checked: number; broken_at_id: number | null }>("/api/audit/verify") });
  const [sel, setSel] = useState<Row | null>(null);
  const actions = ["", "RISK_ASSESSED", "RISK_POLICY_APPLIED", "PAYPAL_ORDER_CREATED", "PAYPAL_CAPTURE", "PAYMENT_HELD", "REVIEW_DECISION", "INVESTIGATION_STARTED", "INVESTIGATION_COMPLETED", "WEBHOOK_PROCESSED", "WEBHOOK_REJECTED", "LOGIN", "LOGIN_FAILED", "MODEL_TRAINED", "RISK_POLICY_UPDATED"];
  return (
    <div>
      <PageHeader title="Audit Centre" subtitle="Append-only, SHA-256 hash-chained record of every risk, payment, agent and reviewer action"
        actions={<button className="btn-primary" onClick={() => verify.mutate()} disabled={verify.isPending}>{verify.isPending ? <Spinner /> : <Link2 className="h-4 w-4" />}Verify hash chain</button>} />
      {verify.data && (
        <div className={`mb-4 flex items-center gap-2 rounded-lg border p-3 text-sm ${verify.data.valid ? "border-emerald-400/30 bg-emerald-400/10 text-emerald-200" : "border-rose-400/30 bg-rose-500/10 text-rose-200"}`}>
          {verify.data.valid ? <ShieldCheck className="h-4 w-4" /> : <ShieldX className="h-4 w-4" />}
          {verify.data.valid ? `Chain intact: ${verify.data.checked.toLocaleString()} entries verified.` : `Chain broken at entry #${verify.data.broken_at_id} after ${verify.data.checked} valid entries.`}
        </div>
      )}
      <div className="mb-3 flex flex-wrap gap-2">
        <select className="input w-64" value={action} onChange={(e) => setAction(e.target.value)}>{actions.map((a) => <option key={a} value={a}>{a || "All actions"}</option>)}</select>
        <input className="input w-64 font-mono" placeholder="Entity ID (e.g. TXN_…)" value={entity} onChange={(e) => setEntity(e.target.value.trim())} />
      </div>
      <ErrorBox error={q.error || verify.error} />
      <Card title="Audit log" icon={<FileClock className="h-4 w-4" />} bodyClass="p-0">
        {q.isLoading && <Loading />}
        <div className="max-h-[calc(100vh-280px)] overflow-auto">
          <table className="w-full text-sm">
            <thead className="sticky top-0 border-b border-ink-700 bg-ink-850 text-left text-[11px] uppercase tracking-wider text-fog-400">
              <tr>{["#", "Time", "Action", "Entity", "Actor", "Hash"].map((h) => <th key={h} className="px-4 py-2.5 font-medium">{h}</th>)}</tr>
            </thead>
            <tbody>
              {q.data?.map((r) => (
                <tr key={r.id} onClick={() => setSel(r)} className="cursor-pointer border-b border-ink-700/40 hover:bg-ink-800/60">
                  <td className="px-4 py-2 font-mono text-xs text-fog-500">{r.id}</td>
                  <td className="px-4 py-2 text-xs text-fog-400">{dt(r.created_at)}</td>
                  <td className="px-4 py-2 font-mono text-xs text-cyan-200">{r.action}</td>
                  <td className="px-4 py-2 font-mono text-xs">{r.entity_type}:{r.entity_id}</td>
                  <td className="px-4 py-2 text-xs text-fog-300">{r.actor}</td>
                  <td className="px-4 py-2 font-mono text-[10.5px] text-fog-500">{r.hash.slice(0, 16)}…</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
      <Modal open={!!sel} onClose={() => setSel(null)} title={sel ? `#${sel.id} ${sel.action}` : ""} width="max-w-2xl">
        {sel && (
          <div className="space-y-2 text-xs">
            <div className="font-mono text-fog-400">prev_hash {sel.prev_hash}</div>
            <div className="font-mono text-cyan-300">hash&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; {sel.hash}</div>
            <pre className="max-h-[50vh] overflow-auto rounded-lg bg-ink-950 p-3 font-mono text-[11px] text-fog-200">{JSON.stringify(sel.details, null, 2)}</pre>
          </div>
        )}
      </Modal>
    </div>
  );
}
