export const fmtDate = (s: string) => new Date(s + (s.endsWith("Z") ? "" : "Z")).toLocaleString();
export const fmtScore = (n: number | null | undefined) => (n == null ? "—" : n.toFixed(3));
export const fmtMs = (n: number | null | undefined) => (n == null ? "—" : `${n.toFixed(1)} ms`);
export const pct = (n: number | null | undefined) => (n == null ? "—" : `${(n * 100).toFixed(1)}%`);
export const title = (s: string | null | undefined) => (s ? s.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase()) : "—");
export const DECISION_COLOR = { PASS: "#10b981", REVIEW: "#f59e0b", FAIL: "#ef4444" } as const;
