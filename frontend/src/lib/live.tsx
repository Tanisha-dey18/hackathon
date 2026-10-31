import { useQueryClient } from "@tanstack/react-query";
import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { wsUrl } from "./api";
import { useAuth, isStaff } from "./auth";

export interface LiveEvent {
  event: string;
  data: Record<string, any>;
  ts: number;
}

interface LiveCtx {
  connected: boolean;
  events: LiveEvent[];
}

const Ctx = createContext<LiveCtx>({ connected: false, events: [] });

/** One WebSocket per session; events invalidate the relevant TanStack queries so every view stays live. */
export function LiveProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const qc = useQueryClient();
  const [connected, setConnected] = useState(false);
  const [events, setEvents] = useState<LiveEvent[]>([]);
  const timer = useRef<number>();

  useEffect(() => {
    if (!isStaff(user)) return;
    let ws: WebSocket | null = null;
    let closed = false;
    let ping: number | undefined;
    const connect = () => {
      ws = new WebSocket(wsUrl("/ws/transactions"));
      ws.onopen = () => {
        setConnected(true);
        ping = window.setInterval(() => ws?.readyState === 1 && ws.send("ping"), 25000);
      };
      ws.onclose = () => {
        setConnected(false);
        window.clearInterval(ping);
        if (!closed) timer.current = window.setTimeout(connect, 2500);
      };
      ws.onmessage = (m) => {
        const ev: LiveEvent = JSON.parse(m.data);
        if (ev.event === "connected") return;
        setEvents((prev) => [ev, ...prev].slice(0, 60));
        const keys: string[][] = [["dashboard"]];
        if (ev.event.startsWith("transaction") || ev.event === "decision.made") keys.push(["transactions"], ["queue"], ["txn"]);
        if (ev.event.startsWith("payment")) keys.push(["paypal-orders"], ["paypal-events"], ["txn"]);
        if (ev.event.startsWith("investigation")) keys.push(["investigation"], ["investigations"], ["txn"]);
        if (ev.event === "decision.made") keys.push(["audit"], ["graph"]);
        keys.forEach((k) => qc.invalidateQueries({ queryKey: k }));
      };
    };
    connect();
    return () => {
      closed = true;
      window.clearTimeout(timer.current);
      window.clearInterval(ping);
      ws?.close();
    };
  }, [user, qc]);

  return <Ctx.Provider value={{ connected, events }}>{children}</Ctx.Provider>;
}

export const useLive = () => useContext(Ctx);
