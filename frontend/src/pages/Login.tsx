import { motion } from "framer-motion";
import { ArrowRight } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { ErrorBox, Spinner } from "../components/ui";
import { Logo } from "../layouts/ConsoleLayout";
import { useAuth } from "../lib/auth";

// Seeded synthetic demo accounts (see backend/app/seed/loader.py and SEED_PASSWORD in .env.example)
const DEMO_ACCOUNTS = [
  { email: "reviewer@sentinel.dev", role: "REVIEWER", note: "Review queue & decisions" },
  { email: "admin@sentinel.dev", role: "ADMIN", note: "Policy, retraining, escalations" },
  { email: "analyst@sentinel.dev", role: "ANALYST", note: "Read-only investigation" },
  { email: "ava@shopper.sentinel.dev", role: "SHOPPER", note: "Demo A · normal buyer" },
  { email: "ben@shopper.sentinel.dev", role: "SHOPPER", note: "Demo B · anomalous buyer" },
  { email: "cara@shopper.sentinel.dev", role: "SHOPPER", note: "Demo C · fraud ring member" },
];
const DEMO_PASSWORD = "SentinelDemo!2026";

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [params] = useSearchParams();
  const [email, setEmail] = useState(params.get("email") ?? "");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<unknown>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      const u = await login(email.trim(), password);
      const next = params.get("next");
      nav(next && (u.role === "CUSTOMER") === next.startsWith("/shop") ? next : u.role === "CUSTOMER" ? "/shop" : "/console", { replace: true });
    } catch (ex) {
      setErr(ex);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="grid w-full max-w-4xl gap-6 md:grid-cols-[1fr_1.1fr]">
        <div className="card p-7">
          <Logo />
          <h1 className="mt-8 text-2xl font-semibold tracking-tight">Sign in</h1>
          <p className="mt-1 text-sm text-fog-400">Every transaction. Every connection. Every risk. Understood.</p>
          <form onSubmit={submit} className="mt-6 space-y-3">
            <div>
              <label className="label">Email</label>
              <input className="input mt-1" type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required />
            </div>
            <div>
              <label className="label">Password</label>
              <input className="input mt-1" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
            </div>
            <ErrorBox error={err} />
            <button className="btn-primary w-full" disabled={busy}>{busy ? <Spinner /> : <ArrowRight className="h-4 w-4" />}Sign in</button>
          </form>
        </div>
        <div className="card p-6">
          <div className="label">Synthetic demo accounts</div>
          <p className="mt-1 text-xs text-fog-400">
            All accounts are synthetic. Password for every demo account: <span className="font-mono text-cyan-300">{DEMO_PASSWORD}</span>
          </p>
          <div className="mt-4 space-y-2">
            {DEMO_ACCOUNTS.map((a) => (
              <button key={a.email} type="button" onClick={() => { setEmail(a.email); setPassword(DEMO_PASSWORD); }}
                className="flex w-full items-center justify-between rounded-lg border border-ink-700 bg-ink-900/60 px-3 py-2.5 text-left transition hover:border-cyan-400/40 hover:bg-ink-800">
                <div>
                  <div className="font-mono text-[12.5px] text-fog-100">{a.email}</div>
                  <div className="text-xs text-fog-400">{a.note}</div>
                </div>
                <span className="font-mono text-[10px] tracking-wider text-cyan-300">{a.role}</span>
              </button>
            ))}
          </div>
        </div>
      </motion.div>
    </div>
  );
}
