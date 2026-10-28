import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  Activity,
  BarChart3,
  Bell,
  Boxes,
  Camera,
  CheckCircle2,
  ClipboardCheck,
  Cpu,
  FileText,
  History,
  LayoutDashboard,
  LogOut,
  Menu,
  Package,
  ScanSearch,
  Search,
  Settings,
  ShieldCheck,
  X,
} from "lucide-react";
import { FormEvent, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { Segmented } from "../components/ui";

import { useAuth } from "../contexts/AuthContext";
import { useMode } from "../contexts/ModeContext";
import { useLiveEvents } from "../hooks/useEvents";
import { Api } from "../services/api";

const NAV_SECTIONS = [
  {
    title: "OPERATIONS",
    items: [
      { to: "/", label: "Overview Dashboard", icon: LayoutDashboard, end: true },
      { to: "/inspect", label: "AI Inspection", icon: ScanSearch },
      { to: "/camera", label: "Live Camera", icon: Camera },
      { to: "/batch", label: "Batch Inspection", icon: Boxes },
    ],
  },
  {
    title: "QUALITY CONTROL",
    items: [
      { to: "/history", label: "Inspection History", icon: History },
      { to: "/analytics", label: "Defect Analytics", icon: BarChart3 },
      { to: "/reviews", label: "Human Review", icon: ClipboardCheck },
      { to: "/reports", label: "Quality Reports", icon: FileText },
    ],
  },
  {
    title: "SYSTEM & AUDIT",
    items: [
      { to: "/products", label: "Product Catalog", icon: Package },
      { to: "/models", label: "Model Registry", icon: Cpu },
      { to: "/audit", label: "Audit Trail", icon: ShieldCheck },
      { to: "/settings", label: "Station Settings", icon: Settings },
    ],
  },
];

export default function AppLayout() {
  const { user, logout } = useAuth();
  const { mode, setMode, realAvailable, realMessage } = useMode();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const nav = useNavigate();
  const loc = useLocation();
  useLiveEvents(!!user);

  const pending = useQuery({ queryKey: ["pending"], queryFn: Api.pendingReviews, refetchInterval: 20000 });
  const sys = useQuery({ queryKey: ["system"], queryFn: Api.systemStatus, refetchInterval: 20000, retry: false });

  const search = (e: FormEvent) => {
    e.preventDefault();
    if (q.trim()) {
      nav(`/history?search=${encodeURIComponent(q.trim())}`);
    }
  };

  const online = sys.isSuccess;

  return (
    <div
      className="relative flex h-full text-slate-100 overflow-hidden"
      style={{
        backgroundImage: "url('/background.png')",
        backgroundSize: "cover",
        backgroundPosition: "center",
        backgroundRepeat: "no-repeat",
        backgroundAttachment: "fixed",
      }}
    >
      {/* High-Contrast Luminous Glass Film */}
      <div className="absolute inset-0 bg-slate-950/60 backdrop-blur-[1px] pointer-events-none z-0" />
      <div className="absolute inset-0 bg-gradient-to-br from-slate-950/80 via-slate-950/45 to-slate-950/85 pointer-events-none z-0" />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_rgba(14,165,233,0.12),transparent_60%),radial-gradient(ellipse_at_bottom_right,_rgba(16,185,129,0.08),transparent_50%)] pointer-events-none z-0" />

      {open && <div className="fixed inset-0 z-30 bg-black/60 backdrop-blur-sm lg:hidden" onClick={() => setOpen(false)} />}

      {/* Industrial Workstation Sidebar with Frosted Glass */}
      <aside
        className={`fixed inset-y-0 left-0 z-40 w-64 transform border-r border-white/10 bg-slate-950/50 backdrop-blur-2xl p-3.5 flex flex-col justify-between transition-transform duration-200 lg:static lg:translate-x-0 shadow-[4px_0_24px_rgba(0,0,0,0.5)] ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div>
          {/* Station Brand Identity */}
          <div className="mb-5 flex items-center justify-between border-b border-white/10 pb-3.5 px-1.5">
            <div className="flex items-center gap-2.5">
              <div className="grid h-8 w-8 place-items-center rounded-md bg-sky-500/20 border border-sky-400/40 text-sky-300 shadow-[0_0_12px_rgba(14,165,233,0.3)]">
                <ScanSearch size={18} />
              </div>
              <div className="leading-tight">
                <div className="font-display text-xs font-bold tracking-wider text-white uppercase drop-shadow-sm">
                  AVI Workstation
                </div>
                <div className="text-[10px] font-mono text-slate-400 tracking-tight">
                  Industrial Quality AI v1.0
                </div>
              </div>
            </div>
            <button
              className="lg:hidden text-slate-400 hover:text-white p-1"
              aria-label="Close menu"
              onClick={() => setOpen(false)}
            >
              <X size={16} />
            </button>
          </div>

          {/* Grouped Navigation */}
          <nav className="space-y-4 overflow-y-auto" aria-label="Main Navigation">
            {NAV_SECTIONS.map((section) => (
              <div key={section.title}>
                <div className="px-2 mb-1.5 text-[10px] font-bold tracking-widest text-slate-400 uppercase">
                  {section.title}
                </div>
                <div className="space-y-0.5">
                  {section.items.map(({ to, label, icon: Icon, end }) => (
                    <NavLink
                      key={to}
                      to={to}
                      end={end}
                      onClick={() => setOpen(false)}
                      className={({ isActive }) =>
                        `flex items-center gap-2.5 rounded px-2.5 py-1.5 text-xs transition duration-150 ${
                          isActive
                            ? "bg-sky-500/25 text-white font-semibold border-l-2 border-sky-400 backdrop-blur-md shadow-[0_0_15px_rgba(14,165,233,0.25)]"
                            : "text-slate-300 hover:bg-white/[0.08] hover:text-white hover:backdrop-blur-sm"
                        }`
                      }
                    >
                      <Icon size={15} className="shrink-0" />
                      <span className="truncate">{label}</span>
                      {to === "/reviews" && !!pending.data?.length && (
                        <span className="ml-auto rounded-full border border-amber-500/40 bg-amber-500/25 px-1.5 py-0.2 text-[10px] font-mono font-bold text-amber-300 shadow-[0_0_8px_rgba(245,158,11,0.2)]">
                          {pending.data.length}
                        </span>
                      )}
                    </NavLink>
                  ))}
                </div>
              </div>
            ))}
          </nav>
        </div>

        {/* Station System Health Footer */}
        <div className="border-t border-white/10 pt-3 px-2">
          <div className="flex items-center justify-between text-[11px]">
            <span className="text-slate-300 flex items-center gap-1.5">
              <span className={`h-2 w-2 rounded-full ${online ? "bg-pass animate-pulse shadow-[0_0_8px_rgba(16,185,129,0.5)]" : "bg-fail shadow-[0_0_8px_rgba(239,68,68,0.5)]"}`} />
              {online ? "System Active" : "Backend Offline"}
            </span>
            <span className="text-[10px] font-mono text-slate-400">
              {sys.data?.environment || "dev"}
            </span>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex min-w-0 flex-1 flex-col relative z-10">
        {/* Top Operational Command Bar with Frosted Glass */}
        <header className="flex items-center gap-3 border-b border-white/10 bg-slate-950/45 px-4 py-2.5 backdrop-blur-2xl shadow-[0_4px_24px_rgba(0,0,0,0.3)]">
          <button
            className="lg:hidden text-slate-400 hover:text-white"
            aria-label="Open menu"
            onClick={() => setOpen(true)}
          >
            <Menu size={18} />
          </button>

          {/* Quick Search */}
          <form onSubmit={search} className="relative hidden max-w-xs flex-1 sm:block" role="search">
            <Search size={14} className="absolute left-2.5 top-2 text-slate-400" />
            <input
              aria-label="Search inspections"
              className="input !pl-8 !py-1 text-xs"
              placeholder="Search serial, batch, defect…"
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
          </form>

          {/* Right Header Status Controls */}
          <div className="ml-auto flex items-center gap-3">
            {/* System Online Badge */}
            <div
              className={`hidden items-center gap-1.5 text-xs font-mono md:flex px-2.5 py-0.5 rounded border ${
                online
                  ? "border-pass/40 bg-pass/15 text-emerald-300 shadow-[0_0_10px_rgba(16,185,129,0.2)]"
                  : "border-fail/40 bg-fail/15 text-red-300 shadow-[0_0_10px_rgba(239,68,68,0.2)]"
              }`}
              title="Backend Telemetry Status"
            >
              <Activity size={12} />
              <span>{online ? "ONLINE" : "OFFLINE"}</span>
            </div>

            {/* Real AI Model Readiness Indicator */}
            <div className="flex items-center gap-2">
              {realAvailable ? (
                <div className="flex items-center gap-2 px-3 py-1 rounded-full border border-emerald-500/30 bg-emerald-500/10 backdrop-blur-md text-emerald-300 text-xs font-mono font-medium shadow-[0_0_12px_rgba(16,185,129,0.15)]">
                  <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse shadow-[0_0_8px_rgba(16,185,129,0.8)]" />
                  <span>PatchCore ONNX Active</span>
                </div>
              ) : (
                <div className="flex items-center gap-2 px-3 py-1 rounded-full border border-rose-500/30 bg-rose-500/10 backdrop-blur-md text-rose-300 text-xs font-mono font-medium" title={realMessage}>
                  <span className="h-2 w-2 rounded-full bg-rose-400" />
                  <span>Model Offline</span>
                </div>
              )}
            </div>

            {/* Review Queue Notification Bell */}
            <button
              className="relative rounded-lg p-1.5 text-slate-300 hover:bg-white/10 hover:text-white transition backdrop-blur-sm"
              aria-label={`Notifications: ${pending.data?.length ?? 0} pending reviews`}
              onClick={() => nav("/reviews")}
              title={`${pending.data?.length ?? 0} pending reviews`}
            >
              <Bell size={16} />
              {!!pending.data?.length && (
                <span className="absolute right-1 top-1 h-2 w-2 rounded-full bg-review ring-2 ring-ink-900 shadow-[0_0_8px_rgba(245,158,11,0.5)]" />
              )}
            </button>

            {/* User Profile & Role */}
            <div className="flex items-center gap-2 border-l border-white/10 pl-3">
              <div className="text-right leading-tight hidden sm:block">
                <div className="text-xs font-semibold text-white drop-shadow-sm">
                  {user?.full_name || user?.username}
                </div>
                <div className="text-[10px] uppercase tracking-wider text-sky-400 font-mono">
                  {user?.role}
                </div>
              </div>
              <button
                className="rounded-lg p-1.5 text-slate-300 hover:bg-white/10 hover:text-white transition backdrop-blur-sm"
                aria-label="Log out"
                onClick={() => {
                  logout();
                  nav("/login");
                }}
                title="Sign out of station"
              >
                <LogOut size={15} />
              </button>
            </div>
          </div>
        </header>

        {/* Page Content Viewport */}
        <main className="min-h-0 flex-1 overflow-y-auto p-3 sm:p-5">
          <motion.div
            key={loc.pathname}
            initial={{ opacity: 0, y: 3 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.15 }}
          >
            <Outlet />
          </motion.div>
        </main>
      </div>
    </div>
  );
}
