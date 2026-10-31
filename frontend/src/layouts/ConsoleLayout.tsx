import { motion } from "framer-motion";
import {
  Activity, BrainCircuit, CreditCard, FileClock, Gauge, LogOut, Network, Radar, Settings, ShieldCheck, ShoppingBag, Sparkles,
} from "lucide-react";
import { Navigate, NavLink, Outlet, useLocation } from "react-router-dom";
import { Loading } from "../components/ui";
import { isStaff, useAuth } from "../lib/auth";
import { useLive } from "../lib/live";

const NAV = [
  { to: "/console", label: "Command Centre", icon: Gauge, end: true },
  { to: "/console/transactions", label: "Live Transactions", icon: Activity },
  { to: "/console/intelligence", label: "Fraud Intelligence", icon: Radar },
  { to: "/console/network", label: "Network Graph", icon: Network },
  { to: "/console/investigations", label: "AI Investigations", icon: Sparkles },
  { to: "/console/payments", label: "PayPal Payments", icon: CreditCard },
  { to: "/console/models", label: "Model Analytics", icon: BrainCircuit },
  { to: "/console/audit", label: "Audit Centre", icon: FileClock },
  { to: "/console/settings", label: "Settings", icon: Settings },
];

export function Logo({ sub = "Payment Risk Intelligence" }: { sub?: string }) {
  return (
    <div className="flex items-center gap-2.5">
      <div className="relative flex h-8 w-8 items-center justify-center rounded-lg border border-cyan-400/40 bg-cyan-400/10 shadow-glow">
        <ShieldCheck className="h-4.5 w-4.5 text-cyan-300" style={{ width: 18, height: 18 }} />
      </div>
      <div className="leading-tight">
        <div className="font-mono text-sm font-semibold tracking-[0.22em] text-fog-100">SENTINEL</div>
        <div className="text-[10px] uppercase tracking-[0.14em] text-fog-400">{sub}</div>
      </div>
    </div>
  );
}

export default function ConsoleLayout() {
  const { user, loading, logout } = useAuth();
  const { connected } = useLive();
  const loc = useLocation();
  if (loading) return <Loading label="Restoring session" />;
  if (!isStaff(user)) return <Navigate to={`/login?next=${encodeURIComponent(loc.pathname)}`} replace />;

  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r border-ink-700/70 bg-ink-900/70 backdrop-blur lg:flex">
        <div className="px-4 py-5"><Logo /></div>
        <nav className="flex-1 space-y-0.5 px-2">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end}
              className={({ isActive }) => `group relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition ${isActive ? "bg-cyan-400/10 text-cyan-200" : "text-fog-300 hover:bg-ink-750 hover:text-fog-100"}`}>
              {({ isActive }) => (
                <>
                  {isActive && <motion.span layoutId="nav-active" className="absolute left-0 top-1.5 h-[calc(100%-12px)] w-0.5 rounded-full bg-cyan-400" />}
                  <Icon className="h-4 w-4" />
                  {label}
                </>
              )}
            </NavLink>
          ))}
        </nav>
        <div className="space-y-3 border-t border-ink-700/70 p-4">
          <NavLink to="/shop" className="flex items-center gap-2 text-xs text-fog-400 hover:text-cyan-300">
            <ShoppingBag className="h-3.5 w-3.5" /> Open SENTINEL MERCHANT
          </NavLink>
          <div className="flex items-center gap-2 text-xs">
            <span className={`h-2 w-2 rounded-full ${connected ? "bg-emerald-400 shadow-[0_0_8px_#34d399]" : "bg-rose-500"}`} />
            <span className="text-fog-400">{connected ? "Live stream connected" : "Live stream offline"}</span>
          </div>
          <div className="flex items-center justify-between">
            <div className="min-w-0">
              <div className="truncate text-sm text-fog-100">{user!.full_name}</div>
              <div className="font-mono text-[10px] tracking-wider text-cyan-300">{user!.role}</div>
            </div>
            <button onClick={logout} className="rounded-md p-1.5 text-fog-400 hover:bg-ink-700 hover:text-fog-100" title="Sign out">
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </div>
      </aside>
      <div className="min-w-0 flex-1">
        <div className="sticky top-0 z-30 flex items-center gap-2 overflow-x-auto border-b border-ink-700/70 bg-ink-900/90 px-3 py-2 backdrop-blur lg:hidden">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end} className={({ isActive }) => `flex shrink-0 items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs ${isActive ? "bg-cyan-400/10 text-cyan-200" : "text-fog-300"}`}>
              <Icon className="h-3.5 w-3.5" />{label}
            </NavLink>
          ))}
        </div>
        <main className="mx-auto max-w-[1600px] px-4 py-6 lg:px-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
