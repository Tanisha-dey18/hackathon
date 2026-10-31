import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BrainCircuit, RefreshCw, Trophy } from "lucide-react";
import { useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { axis, ChartTooltip, grid } from "../../components/charts";
import { Card, ErrorBox, Loading, PageHeader, Spinner, SyntheticTag } from "../../components/ui";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { dt } from "../../lib/format";

interface MV { id: number; version: string; algorithm: string; is_active: boolean; is_primary: boolean; training_rows: number; test_rows: number; notes: string; created_at: string;
  metrics: { precision: number; recall: number; f1: number; roc_auc: number; pr_auc: number; best_f1: number; best_f1_threshold: number; threshold: number | string;
    confusion_matrix: { tn: number; fp: number; fn: number; tp: number }; roc_curve: { x: number; y: number }[]; pr_curve: { x: number; y: number }[] } }

const COLORS: Record<string, string> = { xgboost: "#22d3ee", random_forest: "#34d399", logistic_regression: "#a78bfa", isolation_forest: "#fbbf24" };
const NAMES: Record<string, string> = { xgboost: "XGBoost", random_forest: "Random Forest", logistic_regression: "Logistic Regression", isolation_forest: "Isolation Forest" };

export default function ModelAnalytics() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["models"], queryFn: () => api<MV[]>("/api/models") });
  const status = useQuery({ queryKey: ["retrain"], queryFn: () => api<any>("/api/models/retrain"), refetchInterval: (x) => (x.state.data?.running ? 2000 : false) });
  const retrain = useMutation({ mutationFn: () => api("/api/models/retrain", { method: "POST" }), onSuccess: () => setTimeout(() => qc.invalidateQueries({ queryKey: ["retrain"] }), 300) });
  const versions = [...new Set(q.data?.map((m) => m.version))];
  const [ver, setVer] = useState<string | null>(null);
  const active = ver ?? q.data?.find((m) => m.is_active)?.version;
  const ms = (q.data ?? []).filter((m) => m.version === active);
  if (status.data && !status.data.running && status.data.last && !q.data?.some((m) => m.version === status.data.last.version)) qc.invalidateQueries({ queryKey: ["models"] });

  return (
    <div>
      <PageHeader title="Model Analytics" subtitle={<span className="flex items-center gap-2">All metrics computed on a stratified hold-out test set the models never saw <SyntheticTag text="TRAINED ON SYNTHETIC DATA" /></span>}
        actions={<>
          <select className="input w-32" value={active ?? ""} onChange={(e) => setVer(e.target.value)}>{versions.map((v) => <option key={v}>{v}</option>)}</select>
          {user?.role === "ADMIN" && <button className="btn-primary" disabled={retrain.isPending || status.data?.running} onClick={() => retrain.mutate()}>
            {status.data?.running ? <Spinner /> : <RefreshCw className="h-4 w-4" />}{status.data?.running ? "Training…" : "Retrain models"}</button>}
        </>} />
      <ErrorBox error={retrain.error || status.data?.error} />
      {q.isLoading && <Loading />}
      {ms.length > 0 && (
        <>
          <div className="mb-2 text-xs text-fog-400">{ms[0].training_rows.toLocaleString()} training rows · {ms[0].test_rows.toLocaleString()} test rows · trained {dt(ms[0].created_at)} · {ms[0].notes}</div>
          <Card title="Model comparison" icon={<BrainCircuit className="h-4 w-4" />} bodyClass="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b border-ink-700 text-left text-[11px] uppercase tracking-wider text-fog-400">
                  <tr>{["Model", "Precision", "Recall", "F1", "ROC-AUC", "PR-AUC", "Best F1 (thr)", "Confusion matrix (TN FP / FN TP)"].map((h) => <th key={h} className="px-4 py-2.5 font-medium">{h}</th>)}</tr>
                </thead>
                <tbody>
                  {ms.sort((a, b) => b.metrics.pr_auc - a.metrics.pr_auc).map((m) => (
                    <tr key={m.id} className="border-b border-ink-700/50">
                      <td className="px-4 py-3"><span className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full" style={{ background: COLORS[m.algorithm] }} />{NAMES[m.algorithm]}
                        {m.is_primary && <span className="flex items-center gap-1 rounded border border-cyan-400/40 bg-cyan-400/10 px-1.5 font-mono text-[10px] text-cyan-300"><Trophy className="h-3 w-3" />PRIMARY</span>}
                        {m.algorithm === "isolation_forest" && <span className="font-mono text-[10px] text-fog-500">unsupervised</span>}</span></td>
                      {(["precision", "recall", "f1", "roc_auc", "pr_auc"] as const).map((k) => <td key={k} className="px-4 py-3 font-mono">{m.metrics[k].toFixed(3)}</td>)}
                      <td className="px-4 py-3 font-mono text-xs">{m.metrics.best_f1?.toFixed(3)} <span className="text-fog-500">@{typeof m.metrics.best_f1_threshold === "number" ? m.metrics.best_f1_threshold.toFixed(2) : "—"}</span></td>
                      <td className="px-4 py-3"><Confusion cm={m.metrics.confusion_matrix} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="px-4 py-2.5 text-[11px] text-fog-500">Primary model is selected by PR-AUC (appropriate under class imbalance), not accuracy. Supervised metrics at threshold 0.5; Isolation Forest uses its contamination threshold.</div>
          </Card>
          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            <CurveCard title="ROC curve" ms={ms} k="roc_curve" xl="False positive rate" yl="True positive rate" />
            <CurveCard title="Precision-recall curve" ms={ms} k="pr_curve" xl="Recall" yl="Precision" />
          </div>
        </>
      )}
    </div>
  );
}

function CurveCard({ title, ms, k, xl, yl }: { title: string; ms: MV[]; k: "roc_curve" | "pr_curve"; xl: string; yl: string }) {
  return (
    <Card title={title}>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart margin={{ left: -10, right: 10, top: 6, bottom: 10 }}>
          <CartesianGrid {...grid} vertical />
          <XAxis type="number" dataKey="x" domain={[0, 1]} {...axis} label={{ value: xl, position: "insideBottom", offset: -5, fill: "#6f7b91", fontSize: 11 }} />
          <YAxis type="number" domain={[0, 1]} {...axis} label={{ value: yl, angle: -90, position: "insideLeft", offset: 20, fill: "#6f7b91", fontSize: 11 }} />
          <Tooltip content={<ChartTooltip fmt={(v) => v.toFixed(3)} />} />
          <Legend wrapperStyle={{ fontSize: 11, color: "#9aa6ba" }} />
          {ms.map((m) => <Line key={m.algorithm} data={m.metrics[k]} dataKey="y" name={NAMES[m.algorithm]} stroke={COLORS[m.algorithm]} dot={false} strokeWidth={m.is_primary ? 2.4 : 1.4} type="linear" />)}
        </LineChart>
      </ResponsiveContainer>
    </Card>
  );
}

function Confusion({ cm }: { cm: { tn: number; fp: number; fn: number; tp: number } }) {
  const cell = (v: number, good: boolean) => <div className={`rounded px-2 py-1 text-center font-mono text-xs ${good ? "bg-emerald-400/10 text-emerald-300" : v ? "bg-rose-500/10 text-rose-300" : "bg-ink-700 text-fog-400"}`}>{v}</div>;
  return <div className="grid w-32 grid-cols-2 gap-1">{cell(cm.tn, true)}{cell(cm.fp, false)}{cell(cm.fn, false)}{cell(cm.tp, true)}</div>;
}
