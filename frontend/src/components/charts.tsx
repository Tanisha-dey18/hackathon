import type { ReactNode } from "react";

export const axis = { stroke: "#252e40", tick: { fill: "#6f7b91", fontSize: 11 }, tickLine: false } as const;
export const grid = { stroke: "#1a2130", strokeDasharray: "3 3", vertical: false } as const;

export function ChartTooltip({ active, payload, label, fmt }: { active?: boolean; payload?: any[]; label?: ReactNode; fmt?: (v: number) => string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-ink-600 bg-ink-900/95 px-3 py-2 text-xs shadow-xl backdrop-blur">
      {label != null && <div className="mb-1 font-mono text-fog-300">{label}</div>}
      {payload.map((p) => (
        <div key={p.dataKey ?? p.name} className="flex items-center justify-between gap-4">
          <span className="flex items-center gap-1.5 text-fog-300">
            <span className="h-2 w-2 rounded-sm" style={{ background: p.color ?? p.payload?.fill }} />
            {p.name}
          </span>
          <span className="font-mono text-fog-100">{fmt ? fmt(p.value) : p.value}</span>
        </div>
      ))}
    </div>
  );
}
