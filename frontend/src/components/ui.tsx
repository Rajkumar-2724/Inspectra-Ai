import { AlertTriangle, CheckCircle2, ChevronLeft, ChevronRight, FlaskConical, Inbox, Info, Loader2, ShieldAlert, X } from "lucide-react";
import { ReactNode, useEffect } from "react";
import type { Decision, Mode } from "../types";

export const Card = ({ children, className = "" }: { children: ReactNode; className?: string }) => (
  <div className={`glass p-4 sm:p-5 ${className}`}>{children}</div>
);

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3 border-b border-white/10 pb-4">
      <div>
        <div className="flex items-center gap-2">
          <div className="h-4 w-1 rounded-full bg-sky-400 shadow-[0_0_8px_rgba(14,165,233,0.6)]" />
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-white font-display drop-shadow-sm">{title}</h1>
        </div>
        {subtitle && <p className="mt-1 text-xs sm:text-sm text-slate-300 pl-3">{subtitle}</p>}
      </div>
      <div className="flex flex-wrap items-center gap-2">{actions}</div>
    </div>
  );
}

const DEC_STYLES = {
  PASS: "border-pass/50 bg-pass/20 text-emerald-300 font-bold backdrop-blur-sm shadow-[0_0_8px_rgba(16,185,129,0.15)]",
  REVIEW: "border-review/50 bg-review/20 text-amber-300 font-bold backdrop-blur-sm shadow-[0_0_8px_rgba(245,158,11,0.15)]",
  FAIL: "border-fail/50 bg-fail/20 text-red-300 font-bold backdrop-blur-sm shadow-[0_0_8px_rgba(239,68,68,0.15)]",
};

export const DecisionBadge = ({ d, large }: { d: Decision | null | undefined; large?: boolean }) => {
  if (!d) return <span className="text-slate-400 font-mono text-xs">—</span>;
  return (
    <span
      className={`inline-flex items-center tracking-wider rounded font-mono ${DEC_STYLES[d]} ${
        large ? "px-3.5 py-1 text-sm border font-bold" : "px-2 py-0.5 text-[11px] border"
      }`}
    >
      {d === "PASS" && <span className="mr-1.5 h-1.5 w-1.5 rounded-full bg-emerald-400 shadow-[0_0_6px_rgba(16,185,129,0.8)]" />}
      {d === "REVIEW" && <span className="mr-1.5 h-1.5 w-1.5 rounded-full bg-amber-400 shadow-[0_0_6px_rgba(245,158,11,0.8)]" />}
      {d === "FAIL" && <span className="mr-1.5 h-1.5 w-1.5 rounded-full bg-red-400 shadow-[0_0_6px_rgba(239,68,68,0.8)]" />}
      {d}
    </span>
  );
};

export const ModeBadge = ({ mode, simulated }: { mode: Mode; simulated?: boolean }) =>
  mode === "demo" ? (
    <span className="inline-flex items-center gap-1.5 rounded border border-amber-500/40 bg-amber-500/20 px-2 py-0.5 text-[11px] font-semibold text-amber-300 backdrop-blur-sm shadow-[0_0_8px_rgba(245,158,11,0.15)]">
      <FlaskConical size={11} className="text-amber-400" />
      Historical Record{simulated ? " · simulated" : ""}
    </span>
  ) : (
    <span className="inline-flex items-center gap-1.5 rounded border border-emerald-500/40 bg-emerald-500/15 px-2 py-0.5 text-[11px] font-bold text-emerald-300 backdrop-blur-sm shadow-[0_0_8px_rgba(16,185,129,0.2)] font-mono">
      <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse shadow-[0_0_6px_rgba(16,185,129,0.8)]" />
      PatchCore ONNX
    </span>
  );

export const Stat = ({
  label,
  value,
  hint,
  accent = "text-white",
  icon,
}: {
  label: string;
  value: ReactNode;
  hint?: string;
  accent?: string;
  icon?: ReactNode;
}) => (
  <Card className="!p-3.5 flex flex-col justify-between">
    <div className="flex items-center justify-between text-slate-300">
      <span className="text-[11px] font-semibold tracking-wide uppercase">{label}</span>
      {icon && <span className="text-sky-400">{icon}</span>}
    </div>
    <div className={`mt-2 font-display text-2xl sm:text-3xl font-bold tracking-tight drop-shadow-sm ${accent}`}>
      {value}
    </div>
    {hint && <div className="mt-1 text-[11px] text-slate-400 font-normal">{hint}</div>}
  </Card>
);

export const Spinner = ({ label = "Loading" }: { label?: string }) => (
  <div role="status" className="flex items-center justify-center gap-2 py-10 text-xs text-slate-400">
    <Loader2 className="animate-spin text-volt" size={16} />
    <span className="tracking-wide uppercase font-mono">{label}…</span>
  </div>
);

export const Empty = ({ title, hint, action }: { title: string; hint?: string; action?: ReactNode }) => (
  <div className="flex flex-col items-center gap-2 py-10 text-center">
    <Inbox className="text-slate-600" size={32} />
    <div className="text-sm font-medium text-slate-300">{title}</div>
    {hint && <div className="max-w-md text-xs text-slate-500">{hint}</div>}
    {action && <div className="mt-2">{action}</div>}
  </div>
);

export const ErrorState = ({ message, onRetry }: { message: string; onRetry?: () => void }) => (
  <div role="alert" className="flex flex-col items-center gap-2.5 rounded-lg border border-fail/30 bg-fail/5 p-5 text-center text-xs text-fail">
    <AlertTriangle size={20} />
    <span className="font-medium">{message}</span>
    {onRetry && (
      <button className="btn-ghost !py-1 !px-3 text-xs mt-1" onClick={onRetry}>
        Try again
      </button>
    )}
  </div>
);

export const SimBanner = ({ text }: { text?: string }) => (
  <div role="note" className="flex items-start gap-2.5 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3.5 py-2 text-xs text-amber-200">
    <FlaskConical size={15} className="mt-0.5 shrink-0 text-amber-400" />
    <span className="leading-relaxed">
      {text ?? "Demo mode: every result is simulated by a deterministic demonstration engine. No trained AI model produced it."}
    </span>
  </div>
);

export function Modal({
  open,
  onClose,
  title,
  children,
  wide,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  wide?: boolean;
}) {
  useEffect(() => {
    if (!open) return;
    const h = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm" onMouseDown={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={`glass-solid max-h-[92vh] w-full overflow-auto p-5 sm:p-6 ${wide ? "max-w-3xl" : "max-w-lg"}`}
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between border-b border-white/10 pb-3">
          <h2 className="text-base font-semibold text-white tracking-tight">{title}</h2>
          <button aria-label="Close" className="rounded p-1 text-slate-400 hover:bg-white/10 hover:text-white" onClick={onClose}>
            <X size={16} />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function Pagination({
  page,
  pageSize,
  total,
  onChange,
}: {
  page: number;
  pageSize: number;
  total: number;
  onChange: (p: number) => void;
}) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  return (
    <div className="mt-3 flex items-center justify-between text-xs text-slate-400 border-t border-white/5 pt-3">
      <span className="font-mono text-[11px]">{total} record{total === 1 ? "" : "s"}</span>
      <div className="flex items-center gap-2">
        <button className="btn-ghost !px-2 !py-1 text-xs" disabled={page <= 1} onClick={() => onChange(page - 1)} aria-label="Previous page">
          <ChevronLeft size={13} />
        </button>
        <span className="font-mono text-[11px]">Page {page} of {pages}</span>
        <button className="btn-ghost !px-2 !py-1 text-xs" disabled={page >= pages} onClick={() => onChange(page + 1)} aria-label="Next page">
          <ChevronRight size={13} />
        </button>
      </div>
    </div>
  );
}

export function Segmented<T extends string>({
  value,
  onChange,
  options,
}: {
  value: T;
  onChange: (v: T) => void;
  options: { value: T; label: string; disabled?: boolean }[];
}) {
  return (
    <div className="inline-flex rounded-lg border border-white/15 bg-slate-950/60 backdrop-blur-md p-0.5 shadow-inner" role="tablist">
      {options.map((o) => (
        <button
          key={o.value}
          role="tab"
          aria-selected={value === o.value}
          disabled={o.disabled}
          onClick={() => onChange(o.value)}
          className={`rounded px-2.5 py-1 text-xs font-medium transition duration-150 disabled:opacity-30 ${
            value === o.value
              ? "bg-sky-600/90 text-white font-semibold shadow-md shadow-sky-950/50 border border-sky-400/40"
              : "text-slate-300 hover:text-white hover:bg-white/[0.06]"
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export const FieldError = ({ msg }: { msg?: string }) => (
  msg ? <p role="alert" className="mt-1 text-xs text-fail font-medium">{msg}</p> : null
);
