import { AnimatePresence, motion } from "framer-motion";
import { Loader2, X } from "lucide-react";
import type { ReactNode } from "react";
import { createPortal } from "react-dom";
import { RISK_COLORS } from "../lib/format";

export function Card({ title, icon, actions, children, className = "", bodyClass = "p-4" }: {
  title?: ReactNode; icon?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string; bodyClass?: string;
}) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && (
        <header className="card-header">
          <div className="flex items-center gap-2 text-sm font-semibold text-fog-100">
            {icon && <span className="text-cyan-400">{icon}</span>}
            {title}
          </div>
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className={bodyClass}>{children}</div>
    </section>
  );
}

export function RiskBadge({ level, size = "sm" }: { level?: string | null; size?: "sm" | "md" }) {
  if (!level) return <span className="text-xs text-fog-500">—</span>;
  const c = RISK_COLORS[level] ?? "#9aa6ba";
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-md border font-mono font-semibold tracking-wide ${size === "md" ? "px-2.5 py-1 text-xs" : "px-1.5 py-0.5 text-[10.5px]"} ${level === "CRITICAL" ? "pulse-critical" : ""}`}
      style={{ color: c, borderColor: `${c}55`, background: `${c}14` }}
    >
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: c }} />
      {level}
    </span>
  );
}

const STATUS_TONE: Record<string, string> = {
  CAPTURED: "text-emerald-300 border-emerald-400/30 bg-emerald-400/10",
  COMPLETED: "text-emerald-300 border-emerald-400/30 bg-emerald-400/10",
  CLEARED: "text-emerald-300 border-emerald-400/30 bg-emerald-400/10",
  APPROVED: "text-sky-300 border-sky-400/30 bg-sky-400/10",
  APPROVED_AUTO: "text-emerald-300 border-emerald-400/30 bg-emerald-400/10",
  APPROVED_BY_REVIEWER: "text-emerald-300 border-emerald-400/30 bg-emerald-400/10",
  CREATED: "text-fog-200 border-ink-500 bg-ink-700/40",
  AWAITING_APPROVAL: "text-fog-200 border-ink-500 bg-ink-700/40",
  AWAITING_BUYER_APPROVAL: "text-fog-200 border-ink-500 bg-ink-700/40",
  HELD_FOR_REVIEW: "text-orange-300 border-orange-400/30 bg-orange-400/10",
  HELD_FOR_VERIFICATION: "text-amber-300 border-amber-400/30 bg-amber-400/10",
  PENDING_REVIEW: "text-amber-300 border-amber-400/30 bg-amber-400/10",
  ESCALATED: "text-fuchsia-300 border-fuchsia-400/30 bg-fuchsia-400/10",
  REJECTED: "text-rose-300 border-rose-400/30 bg-rose-400/10",
  FAILED: "text-rose-300 border-rose-400/30 bg-rose-400/10",
  CAPTURE_FAILED: "text-rose-300 border-rose-400/30 bg-rose-400/10",
  RUNNING: "text-cyan-300 border-cyan-400/30 bg-cyan-400/10",
};

export function StatusPill({ status }: { status?: string | null }) {
  if (!status) return <span className="text-xs text-fog-500">—</span>;
  return (
    <span className={`inline-flex items-center rounded-md border px-1.5 py-0.5 font-mono text-[10.5px] font-medium tracking-wide ${STATUS_TONE[status] ?? "border-ink-500 bg-ink-700/40 text-fog-200"}`}>
      {status.replaceAll("_", " ")}
    </span>
  );
}

export function Stat({ label, value, sub, icon, tone = "cyan", delay = 0 }: {
  label: string; value: ReactNode; sub?: ReactNode; icon?: ReactNode; tone?: "cyan" | "amber" | "rose" | "emerald" | "fog"; delay?: number;
}) {
  const tones = {
    cyan: "from-cyan-400/15 text-cyan-300", amber: "from-amber-400/15 text-amber-300", rose: "from-rose-500/15 text-rose-300",
    emerald: "from-emerald-400/15 text-emerald-300", fog: "from-fog-400/10 text-fog-200",
  };
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay, duration: 0.35 }}
      className="card relative overflow-hidden p-4">
      <div className={`pointer-events-none absolute inset-0 bg-gradient-to-br ${tones[tone].split(" ")[0]} to-transparent opacity-60`} />
      <div className="relative flex items-start justify-between">
        <div className="label">{label}</div>
        {icon && <div className={tones[tone].split(" ")[1]}>{icon}</div>}
      </div>
      <div className="relative mt-3 font-mono text-[26px] font-semibold leading-none tracking-tight text-fog-100">{value}</div>
      {sub && <div className="relative mt-2 text-xs text-fog-400">{sub}</div>}
    </motion.div>
  );
}

export function Spinner({ className = "" }: { className?: string }) {
  return <Loader2 className={`h-4 w-4 animate-spin ${className}`} />;
}

export function Loading({ label = "Loading" }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-12 text-sm text-fog-400">
      <Spinner /> {label}…
    </div>
  );
}

export function ErrorBox({ error }: { error: unknown }) {
  if (!error) return null;
  return (
    <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-sm text-rose-200">
      {error instanceof Error ? error.message : String(error)}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="py-10 text-center text-sm text-fog-400">{children}</div>;
}

export function SyntheticTag({ text = "SYNTHETIC DEMO DATA" }: { text?: string }) {
  return (
    <span className="inline-flex items-center gap-1 rounded border border-amber-400/30 bg-amber-400/10 px-1.5 py-0.5 font-mono text-[10px] font-semibold tracking-wider text-amber-300">
      {text}
    </span>
  );
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-fog-100">{title}</h1>
        {subtitle && <div className="mt-1 text-sm text-fog-400">{subtitle}</div>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Modal({ open, onClose, title, children, width = "max-w-lg" }: {
  open: boolean; onClose: () => void; title: ReactNode; children: ReactNode; width?: string;
}) {
  // Portal to <body>: ancestors with backdrop-filter would otherwise trap position:fixed.
  return createPortal(
    <AnimatePresence>
      {open && (
        <motion.div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose}>
          <motion.div className={`card w-full ${width}`} initial={{ scale: 0.96, y: 10 }} animate={{ scale: 1, y: 0 }}
            exit={{ scale: 0.96, opacity: 0 }} onClick={(e) => e.stopPropagation()}>
            <div className="card-header">
              <div className="font-semibold">{title}</div>
              <button className="text-fog-400 hover:text-fog-100" onClick={onClose} aria-label="Close"><X className="h-4 w-4" /></button>
            </div>
            <div className="p-4">{children}</div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  );
}

export function KV({ k, v, mono = false }: { k: ReactNode; v: ReactNode; mono?: boolean }) {
  return (
    <div className="flex items-start justify-between gap-3 py-1.5 text-sm">
      <span className="shrink-0 text-fog-400">{k}</span>
      <span className={`text-right text-fog-100 ${mono ? "font-mono text-[12.5px]" : ""}`}>{v}</span>
    </div>
  );
}

export function ProbabilityBar({ value }: { value: number }) {
  const c = value >= 0.9 ? RISK_COLORS.CRITICAL : value >= 0.7 ? RISK_COLORS.HIGH : value >= 0.3 ? RISK_COLORS.MEDIUM : RISK_COLORS.LOW;
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-ink-700">
        <motion.div className="h-full rounded-full" style={{ background: c }} initial={{ width: 0 }} animate={{ width: `${Math.max(2, value * 100)}%` }} transition={{ duration: 0.6 }} />
      </div>
      <span className="w-12 text-right font-mono text-xs" style={{ color: c }}>{value.toFixed(3)}</span>
    </div>
  );
}
