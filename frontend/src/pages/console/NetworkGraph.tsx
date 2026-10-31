import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Network, RefreshCcw, Search, Smartphone, Users, Wallet } from "lucide-react";
import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import GraphView, { type GEdge, type GNode, type GraphData } from "../../components/GraphView";
import { Card, ErrorBox, Loading, PageHeader, SyntheticTag } from "../../components/ui";
import { api } from "../../lib/api";
import { usd } from "../../lib/format";
import { EdgeInspector, NodeInspector } from "./InvestigationWorkspace";

interface Cluster { cluster_id: number; customers: string[]; devices: string[]; destinations: string[]; reasons: string[]; mean_risk: number; max_risk: number }
interface Overview {
  summary: Record<string, any>; clusters: Cluster[];
  shared_devices: { device: string; customers: string[]; account_count: number; high_risk_accounts: number }[];
  cycles: { customers: string[]; length: number; total_amount: number; hops: { from: string; to: string; transfers: number; amount: number }[] }[];
  flagged_destinations: { destination: string; label: string; reason: string; customers: string[]; payment_count: number; total_amount: number }[];
  graph: GraphData;
}

const typeOf = (ref: string) => ({ CUS: "CUSTOMER", DEV: "DEVICE", DST: "DESTINATION", MER: "MERCHANT", TXN: "TRANSACTION" } as Record<string, string>)[ref.split("_")[0]];

export default function NetworkGraph() {
  const [params, setParams] = useSearchParams();
  const entity = params.get("entity");
  const [input, setInput] = useState(entity ?? "");
  const [highlight, setHighlight] = useState<Set<string> | undefined>();
  const [selNode, setSelNode] = useState<GNode | null>(null);
  const [selEdge, setSelEdge] = useState<GEdge | null>(null);
  const ov = useQuery({ queryKey: ["graph", "overview"], queryFn: () => api<Overview>("/api/graph/overview") });
  const ent = useQuery({ queryKey: ["graph", "entity", entity], enabled: !!entity, queryFn: () => api<GraphData>(`/api/graph/entity/${entity}?hops=2`) });
  const data = entity ? ent.data : ov.data?.graph;

  const hl = (refs: string[]) => setHighlight(new Set(refs.map((r) => `${typeOf(r)}:${r}`)));
  const s = ov.data?.summary;
  const flaggedSet = useMemo(() => new Set(ov.data?.flagged_destinations.map((f) => f.destination)), [ov.data]);

  return (
    <div>
      <PageHeader title="Network Graph" subtitle={<span className="flex items-center gap-2">Graph intelligence over stored relationships (NetworkX) <SyntheticTag /></span>}
        actions={
          <form className="flex items-center gap-2" onSubmit={(e) => { e.preventDefault(); setHighlight(undefined); setParams(input.trim() ? { entity: input.trim().toUpperCase() } : {}); }}>
            <div className="relative"><Search className="absolute left-2.5 top-2.5 h-4 w-4 text-fog-500" />
              <input className="input w-64 pl-8 font-mono" placeholder="CUS_0003, DEV_0147, DST_MULE_01" value={input} onChange={(e) => setInput(e.target.value)} /></div>
            <button className="btn-primary">Explore</button>
            {entity && <button type="button" className="btn-ghost" onClick={() => { setParams({}); setInput(""); }}><RefreshCcw className="h-3.5 w-3.5" />Overview</button>}
          </form>
        } />
      {s && (
        <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-6">
          {[["Entities", s.nodes], ["Relationships", s.edges], ["Suspicious clusters", s.suspicious_clusters], ["Shared devices", s.shared_devices], ["Circular loops", s.cycles], ["Flagged destinations", s.flagged_destinations]].map(([l, v]) => (
            <div key={l} className="card p-3"><div className="label">{l}</div><div className="mt-1 font-mono text-xl font-semibold">{(v as number).toLocaleString()}</div></div>
          ))}
        </div>
      )}
      <div className="grid gap-4 xl:grid-cols-12">
        <Card title={entity ? `Neighbourhood of ${entity}` : "Suspicious network overview"} icon={<Network className="h-4 w-4" />} className="xl:col-span-8" bodyClass="p-0"
          actions={highlight && <button className="text-xs text-cyan-300" onClick={() => setHighlight(undefined)}>Clear highlight</button>}>
          {(ov.isLoading || ent.isLoading) && <Loading label="Computing graph" />}
          <ErrorBox error={ov.error || ent.error} />
          {data && <GraphView data={data} height={660} highlight={highlight} onSelectNode={(n) => { setSelNode(n); setSelEdge(null); }} onSelectEdge={(e) => { setSelEdge(e); setSelNode(null); }} />}
          {(selNode || selEdge) && <div className="border-t border-ink-700 p-4 text-sm">{selNode && <NodeInspector n={selNode} />}{selEdge && <EdgeInspector e={selEdge} />}</div>}
        </Card>
        <div className="max-h-[780px] space-y-4 overflow-y-auto xl:col-span-4">
          <Card title="Suspicious clusters" icon={<Users className="h-4 w-4" />} bodyClass="p-2">
            {ov.data?.clusters.map((c) => (
              <button key={c.cluster_id} onClick={() => { if (entity) setParams({}); hl([...c.customers, ...c.devices, ...c.destinations]); }}
                className="mb-1.5 w-full rounded-lg border border-ink-700 bg-ink-900/60 p-2.5 text-left hover:border-rose-400/40">
                <div className="flex items-center justify-between text-xs"><span className="font-semibold">Cluster #{c.cluster_id}</span><span className="font-mono text-rose-300">mean risk {c.mean_risk.toFixed(2)}</span></div>
                <div className="mt-1 text-[11px] text-fog-400">{c.customers.length} accounts · {c.devices.length} devices · {c.destinations.length} wallets</div>
                {c.reasons.map((r) => <div key={r} className="mt-0.5 text-[11px] text-amber-200">⚑ {r}</div>)}
              </button>
            ))}
          </Card>
          <Card title="Shared devices" icon={<Smartphone className="h-4 w-4" />} bodyClass="p-2">
            {ov.data?.shared_devices.map((d) => (
              <button key={d.device} onClick={() => setParams({ entity: d.device })} className="mb-1.5 w-full rounded-lg border border-ink-700 bg-ink-900/60 p-2.5 text-left hover:border-amber-400/40">
                <div className="flex justify-between text-xs"><span className="font-mono">{d.device}</span><span className="text-amber-300">{d.account_count} accounts</span></div>
                <div className="mt-1 font-mono text-[10.5px] text-fog-400">{d.customers.join(" · ")}</div>
              </button>
            ))}
          </Card>
          <Card title="Circular payment loops" icon={<RefreshCcw className="h-4 w-4" />} bodyClass="p-2">
            {ov.data?.cycles.map((c, i) => (
              <button key={i} onClick={() => { if (entity) setParams({}); hl(c.customers); }} className="mb-1.5 w-full rounded-lg border border-ink-700 bg-ink-900/60 p-2.5 text-left hover:border-rose-400/40">
                <div className="font-mono text-[11px] text-fog-200">{[...c.customers, c.customers[0]].join(" → ")}</div>
                <div className="mt-1 text-[11px] text-fog-400">{c.hops.reduce((a, h) => a + h.transfers, 0)} transfers · {usd(c.total_amount)}</div>
              </button>
            ))}
            {!ov.data?.cycles.length && <div className="p-2 text-xs text-fog-500">None detected.</div>}
          </Card>
          <Card title="Flagged destinations" icon={<Wallet className="h-4 w-4" />} bodyClass="p-2">
            {ov.data?.flagged_destinations.map((f) => (
              <button key={f.destination} onClick={() => setParams({ entity: f.destination })} className="mb-1.5 w-full rounded-lg border border-ink-700 bg-ink-900/60 p-2.5 text-left hover:border-rose-400/40">
                <div className="flex justify-between text-xs"><span className="font-mono">{f.destination}</span><span className="text-rose-300">{f.payment_count} payments · {usd(f.total_amount, 0)}</span></div>
                <div className="mt-1 flex gap-1 text-[10.5px] text-fog-400"><AlertTriangle className="h-3 w-3 shrink-0 text-rose-400" />{f.reason}</div>
                <div className="mt-1 text-[10.5px] text-fog-500">{f.customers.length} paying accounts {flaggedSet.size > 1 && ""}</div>
              </button>
            ))}
          </Card>
        </div>
      </div>
    </div>
  );
}
