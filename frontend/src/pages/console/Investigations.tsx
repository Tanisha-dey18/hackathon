import { useQuery } from "@tanstack/react-query";
import { Bot, Sparkles } from "lucide-react";
import { Link } from "react-router-dom";
import { Card, Empty, ErrorBox, Loading, PageHeader, RiskBadge, StatusPill } from "../../components/ui";
import { api } from "../../lib/api";
import { dt } from "../../lib/format";

interface InvRow { id: string; transaction_id: string; status: string; mode: string; recommendation: string | null; risk_level: string | null; created_at: string; findings: number }

export default function Investigations() {
  const q = useQuery({ queryKey: ["investigations"], queryFn: () => api<InvRow[]>("/api/investigations"), refetchInterval: 5000 });
  const health = useQuery({ queryKey: ["integrations"], queryFn: () => api<any>("/api/settings/integrations") });
  return (
    <div>
      <PageHeader title="AI Investigations" subtitle="LangGraph agent runs: tools executed, evidence collected, recommendations routed to human reviewers"
        actions={health.data && (
          <span className={`rounded-lg border px-2.5 py-1 font-mono text-xs ${health.data.groq.configured ? "border-fuchsia-400/40 text-fuchsia-300" : "border-amber-400/40 text-amber-300"}`}>
            {health.data.groq.configured ? `Groq · ${health.data.groq.model}` : "Groq not configured → deterministic fallback"}
          </span>
        )} />
      <Card title="Agent pipeline" icon={<Bot className="h-4 w-4" />} className="mb-4">
        <div className="flex flex-wrap items-center gap-2 text-[11.5px]">
          {["TransactionHistoryTool", "CustomerBehaviourTool", "FraudPredictionTool", "GraphInvestigationTool", "MerchantRiskTool", "EvidenceCollectionTool", "LLM analysis / fallback", "InvestigationReportTool", "Human reviewer"].map((s, i, a) => (
            <span key={s} className="flex items-center gap-2">
              <span className={`rounded-md border px-2 py-1 font-mono ${i === a.length - 1 ? "border-emerald-400/40 text-emerald-300" : "border-ink-600 bg-ink-900/60 text-fog-200"}`}>{s}</span>
              {i < a.length - 1 && <span className="text-fog-500">→</span>}
            </span>
          ))}
        </div>
        <p className="mt-3 text-xs text-fog-400">The agent can only recommend. Every finding must cite evidence keys produced by tools; unsupported statements are removed before the report is stored.</p>
      </Card>
      {q.isLoading && <Loading />}
      <ErrorBox error={q.error} />
      {q.data && !q.data.length && <Empty>No investigations yet — open any transaction and press INVESTIGATE, or run demo C.</Empty>}
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {q.data?.map((i) => (
          <Link key={i.id} to={`/console/investigate/${i.transaction_id}`} className="card block p-4 transition hover:border-cyan-400/40">
            <div className="flex items-center justify-between"><span className="flex items-center gap-1.5 font-mono text-xs text-fog-300"><Sparkles className="h-3.5 w-3.5 text-fuchsia-300" />{i.id}</span><StatusPill status={i.status} /></div>
            <div className="mt-2 font-mono text-sm">{i.transaction_id}</div>
            <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
              <RiskBadge level={i.risk_level} />
              {i.recommendation && <span className="rounded border border-cyan-400/30 bg-cyan-400/10 px-1.5 py-0.5 font-mono text-[10.5px] text-cyan-200">{i.recommendation}</span>}
              <span className="text-fog-400">{i.findings} findings</span>
            </div>
            <div className="mt-2 flex justify-between text-[11px] text-fog-500"><span>{i.mode === "LLM_AGENT" ? "LLM agent" : "Deterministic fallback"}</span><span>{dt(i.created_at)}</span></div>
          </Link>
        ))}
      </div>
    </div>
  );
}
