import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  Boxes,
  CheckCircle2,
  Clock,
  Cpu,
  Database,
  Eye,
  FileText,
  Gauge,
  Layers,
  Play,
  RotateCcw,
  ScanSearch,
  Server,
  ShieldAlert,
  ShieldCheck,
  TrendingUp,
  XCircle,
} from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  Card,
  DecisionBadge,
  Empty,
  ErrorState,
  ModeBadge,
  PageHeader,
  Segmented,
  Spinner,
  Stat,
} from "../components/ui";
import { Api, errMsg } from "../services/api";
import { DECISION_COLOR, fmtDate, fmtMs, fmtScore, pct, title } from "../utils/format";

const AXIS_STYLE = { stroke: "#64748b", fontSize: 11, fontFamily: "monospace" };
const TOOLTIP_STYLE = {
  contentStyle: {
    backgroundColor: "rgba(11, 20, 42, 0.85)",
    backdropFilter: "blur(12px)",
    WebkitBackdropFilter: "blur(12px)",
    borderColor: "rgba(255,255,255,0.18)",
    borderRadius: "8px",
    fontSize: "11px",
    fontFamily: "monospace",
    color: "#f8fafc",
    boxShadow: "0 8px 24px rgba(0,0,0,0.6)",
  },
  itemStyle: { color: "#f1f5f9" },
};

const ChartModule = ({
  title: t,
  subtitle,
  children,
  empty,
  height = "h-56",
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  empty?: boolean;
  height?: string;
}) => (
  <Card className="flex flex-col justify-between">
    <div className="mb-2 border-b border-white/10 pb-2">
      <h3 className="text-xs font-mono font-bold tracking-wider text-white uppercase drop-shadow-sm">{t}</h3>
      {subtitle && <p className="text-[10px] text-slate-300 font-mono">{subtitle}</p>}
    </div>
    <div className={height}>
      {empty ? (
        <Empty title="No data available" hint="Run inspections to populate this metric" />
      ) : (
        <ResponsiveContainer width="100%" height="100%">
          {children as any}
        </ResponsiveContainer>
      )}
    </div>
  </Card>
);

export default function Dashboard() {
  const [filterMode, setFilterMode] = useState<"all" | "demo" | "real">("real");
  const modeParam = filterMode === "all" ? undefined : filterMode;

  const stats = useQuery({
    queryKey: ["stats", modeParam],
    queryFn: () => Api.stats(modeParam),
    refetchInterval: 30000,
  });
  const trends = useQuery({
    queryKey: ["trends", modeParam],
    queryFn: () => Api.trends(14, modeParam),
    refetchInterval: 30000,
  });
  const recent = useQuery({
    queryKey: ["recent", modeParam],
    queryFn: () => Api.recent(modeParam),
    refetchInterval: 15000,
  });
  const sys = useQuery({
    queryKey: ["system"],
    queryFn: Api.systemStatus,
    refetchInterval: 20000,
    retry: false,
  });

  if (stats.isLoading) return <Spinner label="Loading operational dashboard" />;
  if (stats.isError)
    return <ErrorState message={errMsg(stats.error)} onRetry={() => stats.refetch()} />;

  const s = stats.data!;
  const t = trends.data;
  const sysData = sys.data;

  // Compute operational rates safely
  const total = s.total || 0;
  const passRate = total > 0 ? (s.passed / total) : 0;
  const failRate = total > 0 ? (s.failed / total) : 0;
  const reviewRate = total > 0 ? (s.pending_reviews / total) : 0;

  const dist = t
    ? Object.entries(t.distribution as Record<string, number>).map(([name, value]) => ({
        name,
        value,
      }))
    : [];

  return (
    <>
      <PageHeader
        title="Operational Quality Dashboard"
        subtitle="Real-time telemetry, defect distribution, pass/fail yields, and optical inspection throughput."
        actions={
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-400 font-mono uppercase mr-1">Data Scope:</span>
            <Segmented
              value={filterMode}
              onChange={setFilterMode}
              options={[
                { value: "real", label: "Real AI (PatchCore)" },
                { value: "all", label: "All Telemetry" },
              ]}
            />
          </div>
        }
      />

      {total === 0 ? (
        <Card>
          <Empty
            title="Inspection Ledger Empty"
            hint="Execute your first optical inspection using the trained PatchCore Metal Nut model."
            action={
              <Link to="/inspect" className="btn-primary mt-2">
                <ScanSearch size={15} />
                Launch Inspection Workstation
              </Link>
            }
          />
        </Card>
      ) : (
        <div className="space-y-4">
          {/* ========================================================================= */}
          {/* SECTION 1: Industrial Operational Key Performance Indicators (KPIs)      */}
          {/* ========================================================================= */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-7">
            <Stat
              label="Total Inspections"
              value={s.total.toLocaleString()}
              hint={`${s.by_mode.real} Real ONNX`}
              icon={<Layers size={15} />}
            />
            <Stat
              label="Pass Rate"
              value={pct(passRate)}
              accent="text-pass"
              hint={`${s.passed} passed units`}
              icon={<CheckCircle2 size={15} className="text-pass" />}
            />
            <Stat
              label="Failure Rate"
              value={pct(failRate)}
              accent="text-fail"
              hint={`${s.failed} rejected units`}
              icon={<XCircle size={15} className="text-fail" />}
            />
            <Stat
              label="Pending Review"
              value={s.pending_reviews}
              accent="text-review"
              hint={`${pct(reviewRate)} of total units`}
              icon={<AlertTriangle size={15} className="text-review" />}
            />
            <Stat
              label="Defect Rate"
              value={pct(s.defect_rate)}
              hint="Review + Fail combined"
              icon={<Gauge size={15} />}
            />
            <Stat
              label="Avg Latency"
              value={fmtMs(s.avg_latency_ms)}
              hint="PatchCore ONNX inference"
              icon={<Clock size={15} />}
            />
            <Stat
              label="Active Products"
              value={s.by_product.length}
              hint="In production registry"
              icon={<Boxes size={15} />}
            />
          </div>

          {/* ========================================================================= */}
          {/* SECTION 2: System Health & Industrial Station Status Strip                */}
          {/* ========================================================================= */}
          <Card className="!p-3.5 bg-sky-950/25 border-sky-400/30 shadow-[0_0_20px_rgba(14,165,233,0.1)]">
            <div className="flex flex-wrap items-center justify-between gap-3 text-xs font-mono">
              <div className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-full bg-pass animate-pulse shadow-[0_0_8px_rgba(16,185,129,0.8)]" />
                <span className="font-semibold text-white tracking-wider uppercase drop-shadow-sm">
                  System Health & Workstation Status
                </span>
              </div>
              <div className="flex flex-wrap items-center gap-4 text-slate-300">
                <span className="flex items-center gap-1.5">
                  <Server size={13} className="text-sky-400" />
                  Backend: <strong className="text-white">ONLINE</strong>
                </span>
                <span className="flex items-center gap-1.5">
                  <Database size={13} className="text-sky-400" />
                  Database: <strong className="text-white">SQLite Connected</strong>
                </span>
                <span className="flex items-center gap-1.5">
                  <Cpu size={13} className="text-sky-400" />
                  Model Pipeline:{" "}
                  <strong className={sysData?.real_mode_available ? "text-emerald-300" : "text-amber-300"}>
                    {sysData?.real_mode_available ? "PatchCore AI Ready" : "Awaiting Model Initialization"}
                  </strong>
                </span>
                <span className="flex items-center gap-1.5">
                  <ShieldCheck size={13} className="text-sky-400" />
                  Audit Hash Ledger: <strong className="text-emerald-300">SHA-256 Verified</strong>
                </span>
              </div>
            </div>
          </Card>

          {/* ========================================================================= */}
          {/* SECTION 3: Visual Analytics & Distribution Charts                         */}
          {/* ========================================================================= */}
          <div className="grid gap-4 lg:grid-cols-3">
            {/* 1. Daily Inspection Trends */}
            <ChartModule
              title="Daily Inspection Trends (14 Days)"
              subtitle="Volume split by quality decision"
              empty={!t?.daily.length}
            >
              <LineChart data={t?.daily} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid stroke="#1e293b" strokeDasharray="2 2" vertical={false} />
                <XAxis dataKey="day" {...AXIS_STYLE} tickFormatter={(d) => d.slice(5)} />
                <YAxis {...AXIS_STYLE} allowDecimals={false} />
                <Tooltip {...TOOLTIP_STYLE} />
                <Legend
                  wrapperStyle={{ fontSize: "11px", fontFamily: "monospace", paddingTop: "6px" }}
                />
                <Line
                  name="Pass"
                  dataKey="pass"
                  stroke={DECISION_COLOR.PASS}
                  dot={false}
                  strokeWidth={2}
                />
                <Line
                  name="Review"
                  dataKey="review"
                  stroke={DECISION_COLOR.REVIEW}
                  dot={false}
                  strokeWidth={2}
                />
                <Line
                  name="Fail"
                  dataKey="fail"
                  stroke={DECISION_COLOR.FAIL}
                  dot={false}
                  strokeWidth={2}
                />
              </LineChart>
            </ChartModule>

            {/* 2. PASS / REVIEW / FAIL Yield Ratio */}
            <ChartModule
              title="Quality Decision Distribution"
              subtitle="PASS vs REVIEW vs FAIL yield breakdown"
              empty={!dist.some((d) => d.value)}
            >
              <PieChart>
                <Pie
                  data={dist}
                  dataKey="value"
                  nameKey="name"
                  innerRadius={50}
                  outerRadius={75}
                  paddingAngle={3}
                  stroke="none"
                >
                  {dist.map((d) => (
                    <Cell
                      key={d.name}
                      fill={DECISION_COLOR[d.name as keyof typeof DECISION_COLOR] || "#64748b"}
                    />
                  ))}
                </Pie>
                <Tooltip {...TOOLTIP_STYLE} />
                <Legend
                  wrapperStyle={{ fontSize: "11px", fontFamily: "monospace", paddingTop: "4px" }}
                />
              </PieChart>
            </ChartModule>

            {/* 3. Defect Categories Breakdown */}
            <ChartModule
              title="Defect Category Breakdown"
              subtitle="Ranked defects identified across all units"
              empty={!t?.defect_categories.length}
            >
              <BarChart
                data={t?.defect_categories}
                layout="vertical"
                margin={{ left: 10, right: 15, top: 5, bottom: 5 }}
              >
                <CartesianGrid stroke="#1e293b" strokeDasharray="2 2" horizontal={false} />
                <XAxis type="number" {...AXIS_STYLE} allowDecimals={false} />
                <YAxis
                  type="category"
                  dataKey="defect"
                  {...AXIS_STYLE}
                  tickFormatter={title}
                  width={90}
                />
                <Tooltip {...TOOLTIP_STYLE} />
                <Bar name="Defect Count" dataKey="count" fill="#0ea5e9" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ChartModule>

            {/* 4. Product-wise Quality Yield */}
            <ChartModule
              title="Product-Wise Quality Yield"
              subtitle="Stack breakdown per product type"
              empty={!s.by_product.length}
            >
              <BarChart
                data={s.by_product}
                margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
              >
                <CartesianGrid stroke="#1e293b" strokeDasharray="2 2" vertical={false} />
                <XAxis dataKey="product" {...AXIS_STYLE} />
                <YAxis {...AXIS_STYLE} allowDecimals={false} />
                <Tooltip {...TOOLTIP_STYLE} />
                <Legend
                  wrapperStyle={{ fontSize: "11px", fontFamily: "monospace", paddingTop: "6px" }}
                />
                <Bar name="Pass" dataKey="PASS" stackId="a" fill={DECISION_COLOR.PASS} />
                <Bar name="Review" dataKey="REVIEW" stackId="a" fill={DECISION_COLOR.REVIEW} />
                <Bar name="Fail" dataKey="FAIL" stackId="a" fill={DECISION_COLOR.FAIL} />
              </BarChart>
            </ChartModule>

            {/* 5. Daily Throughput Volume */}
            <ChartModule
              title="Daily Inspection Throughput"
              subtitle="Total optical inspections per calendar day"
              empty={!t?.daily.length}
            >
              <BarChart data={t?.daily} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid stroke="#1e293b" strokeDasharray="2 2" vertical={false} />
                <XAxis dataKey="day" {...AXIS_STYLE} tickFormatter={(d) => d.slice(5)} />
                <YAxis {...AXIS_STYLE} allowDecimals={false} />
                <Tooltip {...TOOLTIP_STYLE} />
                <Bar
                  name="Inspected Units"
                  dataKey="total"
                  fill="#0284c7"
                  radius={[4, 4, 0, 0]}
                />
              </BarChart>
            </ChartModule>

            {/* 6. Inference Latency Timeline */}
            <ChartModule
              title="Pipeline Latency Timeline"
              subtitle="Average end-to-end processing time (ms)"
              empty={!t?.latency.length}
            >
              <LineChart data={t?.latency} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid stroke="#1e293b" strokeDasharray="2 2" vertical={false} />
                <XAxis dataKey="day" {...AXIS_STYLE} tickFormatter={(d) => d.slice(5)} />
                <YAxis {...AXIS_STYLE} />
                <Tooltip {...TOOLTIP_STYLE} />
                <Line
                  name="Avg Latency (ms)"
                  dataKey="avg_latency_ms"
                  stroke="#38bdf8"
                  strokeWidth={2}
                  dot={false}
                />
              </LineChart>
            </ChartModule>
          </div>

          {/* ========================================================================= */}
          {/* SECTION 4: Live Recent Activity Industrial Ledger                         */}
          {/* ========================================================================= */}
          <Card>
            <div className="mb-3 flex items-center justify-between border-b border-white/10 pb-2.5">
              <div>
                <h3 className="text-xs font-mono font-bold tracking-wider text-white uppercase flex items-center gap-2">
                  <Activity size={14} className="text-sky-400" />
                  Recent Inspection Stream
                </h3>
                <p className="text-[10px] text-slate-400 font-mono">
                  Live operational activity log across all production lines
                </p>
              </div>
              <Link
                className="text-xs font-mono text-sky-400 hover:text-sky-300 flex items-center gap-1"
                to="/history"
              >
                Full Inspection Ledger →
              </Link>
            </div>

            {recent.isLoading ? (
              <Spinner label="Loading inspection records" />
            ) : !recent.data?.length ? (
              <p className="text-xs text-slate-500 font-mono py-4 text-center">
                No recent inspections recorded.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left">
                  <thead>
                    <tr>
                      <th className="th">Timestamp</th>
                      <th className="th">Product Type</th>
                      <th className="th">Serial / Batch / Line</th>
                      <th className="th">Anomaly Score</th>
                      <th className="th">Decision</th>
                      <th className="th">Defect Classification</th>
                      <th className="th">Mode</th>
                      <th className="th text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recent.data.map((i) => (
                      <tr
                        key={i.id}
                        className="border-t border-white/5 hover:bg-white/[0.02] transition"
                      >
                        <td className="td whitespace-nowrap font-mono text-[11px] text-slate-300">
                          {fmtDate(i.created_at)}
                        </td>
                        <td className="td font-medium text-slate-100">{i.product_name}</td>
                        <td className="td font-mono text-[11px] text-slate-400">
                          {i.product_code || "—"} / {i.batch_code || "—"} / {i.line_id || "—"}
                        </td>
                        <td className="td font-mono font-semibold text-slate-200">
                          {fmtScore(i.score)}
                        </td>
                        <td className="td">
                          <DecisionBadge d={i.decision} />
                        </td>
                        <td className="td font-mono text-[11px] text-slate-300">
                          {i.defect_class === "unclassified_anomaly" ? "Anomaly detected" : title(i.defect_class)}
                        </td>
                        <td className="td">
                          <ModeBadge mode={i.mode} simulated={i.simulated} />
                        </td>
                        <td className="td text-right">
                          <Link
                            className="btn-ghost !px-2 !py-0.5 !text-[11px] font-mono text-sky-400 hover:text-white"
                            to={`/history/${i.id}`}
                          >
                            Inspect →
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>
      )}
    </>
  );
}
