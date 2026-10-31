import {
  Background,
  BackgroundVariant,
  Controls,
  Handle,
  Position,
  ReactFlow,
  ReactFlowProvider,
  useNodesInitialized,
  useReactFlow,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { CreditCard, Smartphone, Store, User, Wallet } from "lucide-react";
import { memo, useEffect, useMemo, useState } from "react";
import { riskColor, usd } from "../lib/format";

export interface GNode {
  id: string;
  type: "CUSTOMER" | "MERCHANT" | "DEVICE" | "DESTINATION" | "TRANSACTION";
  ref_id: string;
  label: string;
  risk: number;
  flagged: boolean;
  flags: string[];
  details: Record<string, any>;
  x: number;
  y: number;
  focus?: boolean;
}
export interface GEdge {
  id: string;
  source: string;
  target: string;
  type: string;
  count: number;
  amount: number;
  suspicious: boolean;
  evidence: string[];
  transaction_ids: string[];
}
export interface GraphData {
  nodes: GNode[];
  edges: GEdge[];
  focus?: string | null;
}

const ICONS = { CUSTOMER: User, MERCHANT: Store, DEVICE: Smartphone, DESTINATION: Wallet, TRANSACTION: CreditCard };
const SIZES = { CUSTOMER: 40, MERCHANT: 46, DEVICE: 34, DESTINATION: 38, TRANSACTION: 50 };
const EDGE_COLORS: Record<string, string> = {
  USES_DEVICE: "#64748b", PAID_TO: "#38bdf8", PAID_MERCHANT: "#475569", OWNS_WALLET: "#a78bfa",
  MADE_PAYMENT: "#22d3ee", VIA_DEVICE: "#22d3ee", PAID_MERCHANT_TXN: "#22d3ee",
};

type EntityData = GNode & { dimmed: boolean } & Record<string, unknown>;

const EntityNode = memo(({ data, selected }: NodeProps<Node<EntityData>>) => {
  const [hover, setHover] = useState(false);
  const Icon = ICONS[data.type] ?? User;
  const size = SIZES[data.type] ?? 38;
  const c = data.type === "MERCHANT" && !data.flagged ? "#64748b" : riskColor(data.risk);
  const isTxn = data.type === "TRANSACTION";
  return (
    <div onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}
      style={{ opacity: data.dimmed ? 0.18 : 1, transition: "opacity .25s" }} className="relative">
      <Handle type="target" position={Position.Top} className="!left-1/2 !top-1/2 !h-1 !w-1 !border-0 !opacity-0" />
      <Handle type="source" position={Position.Bottom} className="!left-1/2 !top-1/2 !h-1 !w-1 !border-0 !opacity-0" />
      <div
        className={`flex items-center justify-center ${isTxn ? "rounded-xl" : data.type === "MERCHANT" ? "rounded-lg" : "rounded-full"}`}
        style={{
          width: size, height: size, background: `radial-gradient(circle at 30% 30%, ${c}33, #0b0f16 70%)`,
          border: `2px solid ${c}`,
          boxShadow: data.focus || selected ? `0 0 0 3px #05070b, 0 0 0 5px #22d3ee, 0 0 22px ${c}88` : data.flagged ? `0 0 18px ${c}99` : "none",
        }}
      >
        <Icon style={{ color: c, width: size * 0.42, height: size * 0.42 }} />
      </div>
      <div className="pointer-events-none absolute left-1/2 top-full mt-1 -translate-x-1/2 whitespace-nowrap font-mono text-[9.5px] text-fog-300">
        {isTxn ? data.label : data.ref_id}
      </div>
      {hover && (
        <div className="absolute bottom-full left-1/2 z-50 mb-2 w-60 -translate-x-1/2 rounded-lg border border-ink-600 bg-ink-900/95 p-2.5 text-left shadow-xl backdrop-blur">
          <div className="flex items-center justify-between">
            <span className="font-mono text-[10px] text-fog-400">{data.type}</span>
            <span className="font-mono text-[10px]" style={{ color: c }}>risk {data.risk.toFixed(2)}</span>
          </div>
          <div className="mt-0.5 text-xs font-semibold text-fog-100">{data.label}</div>
          <div className="font-mono text-[10px] text-fog-400">{data.ref_id}</div>
          {data.flags.map((f) => <div key={f} className="mt-1 text-[10.5px] text-rose-300">⚑ {f}</div>)}
          {Object.entries(data.details).filter(([, v]) => v != null).slice(0, 4).map(([k, v]) => (
            <div key={k} className="mt-0.5 flex justify-between text-[10.5px] text-fog-300">
              <span>{k.replaceAll("_", " ")}</span><span className="font-mono">{k === "amount" ? usd(v as number) : String(v).slice(0, 22)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
});

const nodeTypes = { entity: EntityNode };

function Inner({ data, highlight, onSelectNode, onSelectEdge, height }: GraphProps) {
  const rf = useReactFlow();
  const nodes: Node<EntityData>[] = useMemo(() => data.nodes.map((n) => ({
    id: n.id, type: "entity", position: { x: n.x, y: n.y },
    data: { ...n, dimmed: !!highlight && highlight.size > 0 && !highlight.has(n.id) },
  })), [data, highlight]);
  const edges: Edge[] = useMemo(() => data.edges.map((e) => {
    const dim = !!highlight && highlight.size > 0 && !(highlight.has(e.source) && highlight.has(e.target));
    return {
      id: e.id, source: e.source, target: e.target, type: "straight", data: e as any,
      animated: e.suspicious,
      style: {
        stroke: e.suspicious ? "#f43f5e" : EDGE_COLORS[e.type] ?? "#475569",
        strokeWidth: e.suspicious ? 2.2 : Math.min(1 + Math.log2(e.count || 1) * 0.5, 3),
        opacity: dim ? 0.08 : e.suspicious ? 0.95 : 0.55,
        strokeDasharray: e.type === "USES_DEVICE" || e.type === "VIA_DEVICE" ? "4 3" : undefined,
      },
    };
  }), [data, highlight]);

  // Fit only after React Flow has measured the nodes, otherwise large graphs end up cropped
  const initialized = useNodesInitialized();
  useEffect(() => {
    if (initialized) rf.fitView({ padding: 0.12, duration: 400 });
  }, [initialized, data, rf]);

  return (
    <div style={{ height }} className="relative">
      <ReactFlow colorMode="dark" nodes={nodes} edges={edges} nodeTypes={nodeTypes} fitView minZoom={0.1} maxZoom={2.5}
        proOptions={{ hideAttribution: true }} nodesConnectable={false} zoomOnScroll={false} preventScrolling={false} zoomOnPinch
        onNodeClick={(_, n) => onSelectNode?.(n.data as unknown as GNode)}
        onEdgeClick={(_, e) => onSelectEdge?.(e.data as unknown as GEdge)}>
        <Background variant={BackgroundVariant.Dots} gap={22} size={1} color="#1a2130" />
        <Controls showInteractive={false} />
      </ReactFlow>
      <Legend />
    </div>
  );
}

function Legend() {
  return (
    <div className="pointer-events-none absolute left-3 top-3 flex flex-wrap gap-x-3 gap-y-1 rounded-lg border border-ink-700 bg-ink-900/85 px-2.5 py-1.5 text-[10.5px] text-fog-300 backdrop-blur">
      {Object.entries(ICONS).map(([k, I]) => (
        <span key={k} className="flex items-center gap-1"><I className="h-3 w-3 text-fog-400" />{k.toLowerCase()}</span>
      ))}
      <span className="flex items-center gap-1"><span className="h-0.5 w-4 bg-rose-500" />suspicious link</span>
      <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-risk-low" />low</span>
      <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-risk-medium" />med</span>
      <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-risk-critical" />high</span>
    </div>
  );
}

interface GraphProps {
  data: GraphData;
  highlight?: Set<string>;
  onSelectNode?: (n: GNode) => void;
  onSelectEdge?: (e: GEdge) => void;
  height?: number | string;
}

export default function GraphView(props: GraphProps) {
  return (
    <ReactFlowProvider>
      <Inner {...props} height={props.height ?? 520} />
    </ReactFlowProvider>
  );
}
