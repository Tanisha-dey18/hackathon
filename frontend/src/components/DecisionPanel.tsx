import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowUpRight, Check, ShieldX } from "lucide-react";
import { useState } from "react";
import { api } from "../lib/api";
import { canReview, useAuth } from "../lib/auth";
import { ErrorBox, Modal, RiskBadge, Spinner } from "./ui";

type Decision = "APPROVE" | "REJECT" | "ESCALATE";
const META: Record<Decision, { label: string; cls: string; icon: typeof Check; help: string }> = {
  APPROVE: { label: "Approve", cls: "btn-success", icon: Check, help: "Authorises Sentinel to capture the PayPal order (if one exists)." },
  REJECT: { label: "Reject", cls: "btn-danger", icon: ShieldX, help: "Payment will not be captured. No funds move." },
  ESCALATE: { label: "Escalate", cls: "btn-amber", icon: ArrowUpRight, help: "Hands the decision to an ADMIN. Payment stays held." },
};

export default function DecisionPanel({ txnId, status, riskLevel, recommendation }: {
  txnId: string; status: string; riskLevel: string | null; recommendation?: string | null;
}) {
  const { user } = useAuth();
  const qc = useQueryClient();
  const [open, setOpen] = useState<Decision | null>(null);
  const [reason, setReason] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const m = useMutation({
    mutationFn: (d: Decision) => api(`/api/reviews/${txnId}/decision`, { method: "POST", json: { decision: d, reason, password, confirm_transaction_id: confirm } }),
    onSuccess: () => {
      setOpen(null);
      setReason(""); setPassword(""); setConfirm("");
      ["txn", "transactions", "queue", "dashboard", "audit", "paypal-orders"].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
    },
  });
  const reviewable = ["HELD_FOR_REVIEW", "HELD_FOR_VERIFICATION", "ESCALATED"].includes(status);
  const escalated = status === "ESCALATED";
  const allowed = canReview(user) && reviewable && (!escalated || user?.role === "ADMIN");

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        {(Object.keys(META) as Decision[]).map((d) => {
          const M = META[d];
          return (
            <button key={d} className={`${M.cls} px-3 py-1.5 text-xs ${recommendation && recMatches(recommendation, d) ? "ring-2 ring-offset-2 ring-offset-ink-850 ring-cyan-400/60" : ""}`}
              disabled={!allowed || (d === "ESCALATE" && escalated)} onClick={() => { m.reset(); setOpen(d); }}>
              <M.icon className="h-3.5 w-3.5" />{M.label}
            </button>
          );
        })}
      </div>
      <div className="mt-2 text-[11px] text-fog-500">
        {!canReview(user) ? "Your role cannot decide payments (REVIEWER or ADMIN required)." :
          !reviewable ? `Transaction is ${status.replaceAll("_", " ").toLowerCase()} — no decision pending.` :
            escalated && user?.role !== "ADMIN" ? "Escalated: ADMIN decision required." :
              "Decisions require re-authentication and typed confirmation. Recorded in the audit trail."}
      </div>
      <Modal open={!!open} onClose={() => setOpen(null)} title={open ? `${META[open].label} payment ${txnId}` : ""}>
        {open && (
          <form onSubmit={(e) => { e.preventDefault(); m.mutate(open); }} className="space-y-3">
            <div className="flex items-center gap-2 text-sm text-fog-300">Current risk <RiskBadge level={riskLevel} /> {recommendation && <span className="text-xs">· agent recommends <b className="text-cyan-300">{recommendation}</b></span>}</div>
            <p className="rounded-lg border border-ink-700 bg-ink-900/60 p-2.5 text-xs text-fog-300">{META[open].help}</p>
            <div>
              <label className="label">Reason {open === "APPROVE" && (riskLevel === "HIGH" || riskLevel === "CRITICAL") && "(min 20 chars for high risk)"}</label>
              <textarea className="input mt-1 h-20" value={reason} onChange={(e) => setReason(e.target.value)} required minLength={5} placeholder="Document the evidence behind this decision" />
            </div>
            <div>
              <label className="label">Re-enter your password</label>
              <input className="input mt-1" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
            </div>
            <div>
              <label className="label">Type <span className="font-mono normal-case text-cyan-300">{txnId}</span> to confirm</label>
              <input className="input mt-1 font-mono" value={confirm} onChange={(e) => setConfirm(e.target.value)} required />
            </div>
            <ErrorBox error={m.error} />
            <div className="flex justify-end gap-2">
              <button type="button" className="btn-ghost" onClick={() => setOpen(null)}>Cancel</button>
              <button className={META[open].cls} disabled={m.isPending || confirm !== txnId}>{m.isPending && <Spinner />}Confirm {META[open].label.toLowerCase()}</button>
            </div>
          </form>
        )}
      </Modal>
    </div>
  );
}

const recMatches = (rec: string, d: Decision) => (rec === "APPROVE" && d === "APPROVE") || (rec === "REJECT" && d === "REJECT") || (rec === "ESCALATE" && d === "ESCALATE");
