import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { API_URL, TOKEN_KEY } from "../services/api";

/** Live updates: refreshes dashboard queries whenever the backend broadcasts a new inspection or review. */
export function useLiveEvents(enabled: boolean) {
  const qc = useQueryClient();
  useEffect(() => {
    if (!enabled) return;
    let ws: WebSocket | null = null, timer: number | undefined, closed = false;
    const connect = () => {
      const token = localStorage.getItem(TOKEN_KEY);
      if (!token) return;
      ws = new WebSocket(API_URL.replace(/^http/, "ws") + "/ws/events?token=" + encodeURIComponent(token));
      ws.onmessage = () => ["stats", "trends", "recent", "pending", "inspections", "defects"].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
      ws.onclose = () => { if (!closed) timer = window.setTimeout(connect, 4000); };
    };
    connect();
    return () => { closed = true; window.clearTimeout(timer); ws?.close(); };
  }, [enabled, qc]);
}
