import { useQuery } from "@tanstack/react-query";
import { AllCommunityModule, ModuleRegistry, themeQuartz, type ColDef, type ICellRendererParams } from "ag-grid-community";
import { AgGridReact } from "ag-grid-react";
import { Download, Search } from "lucide-react";
import { useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ErrorBox, Loading, PageHeader, RiskBadge, StatusPill, SyntheticTag } from "../../components/ui";
import { api } from "../../lib/api";
import { RISK_COLORS, usd } from "../../lib/format";

ModuleRegistry.registerModules([AllCommunityModule]);

export const gridTheme = themeQuartz.withParams({
  backgroundColor: "#0b0f16", foregroundColor: "#c9d2e0", headerBackgroundColor: "#0f141c", headerTextColor: "#9aa6ba",
  borderColor: "#1a2130", rowHoverColor: "rgba(34,211,238,0.06)", accentColor: "#22d3ee", fontFamily: "Inter, sans-serif",
  fontSize: 12.5, browserColorScheme: "dark", oddRowBackgroundColor: "#0c1018", selectedRowBackgroundColor: "rgba(34,211,238,0.1)",
  chromeBackgroundColor: "#0f141c", inputBackgroundColor: "#080b11",
});

export interface TxnRow {
  id: string; customer_id: string; customer_name: string; merchant_name: string | null; device_id: string; destination_id: string;
  amount: number; channel: string; status: string; risk_level: string | null; review_status: string; scenario: string | null;
  created_at: string; fraud_probability: number | null; anomaly_score: number | null; is_synthetic: boolean;
}

const LEVELS = ["LOW", "MEDIUM", "HIGH", "CRITICAL"];

export default function LiveTransactions() {
  const nav = useNavigate();
  const grid = useRef<AgGridReact<TxnRow>>(null);
  const [search, setSearch] = useState("");
  const [levels, setLevels] = useState<string[]>([]);
  const [reviewOnly, setReviewOnly] = useState(false);
  const q = useQuery({
    queryKey: ["transactions", "all"],
    queryFn: () => api<{ total: number; items: TxnRow[] }>("/api/transactions?limit=5000"),
    refetchInterval: 20000,
  });

  const rows = useMemo(() => (q.data?.items ?? []).filter((r) =>
    (!levels.length || (r.risk_level && levels.includes(r.risk_level))) && (!reviewOnly || r.review_status === "PENDING_REVIEW" || r.review_status === "ESCALATED"),
  ), [q.data, levels, reviewOnly]);

  const cols = useMemo<ColDef<TxnRow>[]>(() => [
    { field: "created_at", headerName: "Time", width: 165, sort: "desc", filter: "agDateColumnFilter",
      valueFormatter: (p) => new Date(p.value).toLocaleString("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }) },
    { field: "id", headerName: "Transaction", width: 150, cellClass: "font-mono", filter: "agTextColumnFilter" },
    { field: "risk_level", headerName: "Risk", width: 120, filter: "agTextColumnFilter",
      cellRenderer: (p: ICellRendererParams<TxnRow>) => <div className="flex h-full items-center"><RiskBadge level={p.value} /></div>,
      comparator: (a, b) => LEVELS.indexOf(a) - LEVELS.indexOf(b) },
    { field: "fraud_probability", headerName: "p(fraud)", width: 120, filter: "agNumberColumnFilter",
      cellRenderer: (p: ICellRendererParams<TxnRow>) => p.value == null ? "—" : (
        <div className="flex h-full items-center gap-2">
          <div className="h-1 w-12 rounded bg-ink-700"><div className="h-full rounded" style={{ width: `${p.value * 100}%`, background: p.value >= 0.7 ? RISK_COLORS.HIGH : p.value >= 0.3 ? RISK_COLORS.MEDIUM : RISK_COLORS.LOW }} /></div>
          <span className="font-mono text-xs">{p.value.toFixed(3)}</span>
        </div>) },
    { field: "amount", headerName: "Amount", width: 115, filter: "agNumberColumnFilter", type: "rightAligned", valueFormatter: (p) => usd(p.value), cellClass: "font-mono" },
    { field: "customer_name", headerName: "Customer", width: 160, filter: "agTextColumnFilter" },
    { field: "customer_id", headerName: "Customer ID", width: 120, cellClass: "font-mono", hide: false },
    { field: "merchant_name", headerName: "Merchant / Destination", width: 190, filter: "agTextColumnFilter",
      valueGetter: (p) => p.data?.merchant_name ?? `P2P → ${p.data?.destination_id}` },
    { field: "device_id", headerName: "Device", width: 115, cellClass: "font-mono" },
    { field: "status", headerName: "Status", width: 175, filter: "agTextColumnFilter", cellRenderer: (p: ICellRendererParams<TxnRow>) => <div className="flex h-full items-center"><StatusPill status={p.value} /></div> },
    { field: "review_status", headerName: "Review", width: 150, filter: "agTextColumnFilter", cellRenderer: (p: ICellRendererParams<TxnRow>) => <div className="flex h-full items-center">{p.value === "NONE" ? <span className="text-fog-500">—</span> : <StatusPill status={p.value} />}</div> },
    { field: "channel", headerName: "Channel", width: 160, filter: "agTextColumnFilter", cellClass: "font-mono text-xs" },
    { field: "anomaly_score", headerName: "Anomaly pct", width: 120, filter: "agNumberColumnFilter", valueFormatter: (p) => p.value == null ? "—" : p.value.toFixed(3), cellClass: "font-mono" },
  ], []);

  return (
    <div>
      <PageHeader title="Live Transactions" subtitle={<span className="flex items-center gap-2">{q.data ? `${q.data.total.toLocaleString()} transactions` : ""} · updates over WebSocket <SyntheticTag /></span>}
        actions={<button className="btn-ghost text-xs" onClick={() => grid.current?.api.exportDataAsCsv({ fileName: "sentinel-transactions.csv" })}><Download className="h-3.5 w-3.5" />Export CSV</button>} />
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <div className="relative w-72">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-fog-500" />
          <input className="input pl-8" placeholder="Search any field…" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        {LEVELS.map((l) => (
          <button key={l} onClick={() => setLevels((v) => v.includes(l) ? v.filter((x) => x !== l) : [...v, l])}
            className={`rounded-lg border px-2 py-1.5 transition ${levels.includes(l) ? "border-cyan-400/50 bg-cyan-400/10" : "border-ink-600 opacity-70 hover:opacity-100"}`}>
            <RiskBadge level={l} />
          </button>
        ))}
        <label className="ml-2 flex items-center gap-2 text-xs text-fog-300">
          <input type="checkbox" checked={reviewOnly} onChange={(e) => setReviewOnly(e.target.checked)} className="accent-cyan-400" /> Awaiting review only
        </label>
        <span className="ml-auto text-xs text-fog-500">{rows.length.toLocaleString()} shown · click a row to investigate</span>
      </div>
      <ErrorBox error={q.error} />
      {q.isLoading ? <Loading /> : (
        <div className="card overflow-hidden" style={{ height: "calc(100vh - 230px)", minHeight: 420 }}>
          <AgGridReact<TxnRow> ref={grid} theme={gridTheme} rowData={rows} columnDefs={cols} quickFilterText={search}
            defaultColDef={{ sortable: true, resizable: true, floatingFilter: false }} rowHeight={38} headerHeight={38}
            pagination paginationPageSize={100} paginationPageSizeSelector={[50, 100, 250, 500]} animateRows
            getRowId={(p) => p.data.id} onRowClicked={(e) => e.data && nav(`/console/investigate/${e.data.id}`)}
            rowClass="cursor-pointer" />
        </div>
      )}
    </div>
  );
}
