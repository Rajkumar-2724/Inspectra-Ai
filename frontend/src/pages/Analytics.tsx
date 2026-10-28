import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  BarChart3,
  Calendar,
  CheckCircle2,
  Clock,
  Filter,
  Grid,
  Layers,
  ShieldCheck,
  Zap,
} from "lucide-react";
import { useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card, Empty, ErrorState, PageHeader, Spinner, Stat } from "../components/ui";
import { Api, errMsg } from "../services/api";
import { fmtMs, pct, title } from "../utils/format";

const AXIS_STYLE = { stroke: "#475569", fontSize: 11, fontFamily: "monospace" };
const TOOLTIP_STYLE = {
  contentStyle: {
    backgroundColor: "#070c18",
    borderColor: "rgba(255,255,255,0.12)",
    borderRadius: "6px",
    fontSize: "11px",
    fontFamily: "monospace",
    color: "#f8fafc",
  },
};
const INDUSTRIAL_PALETTE = ["#0ea5e9", "#10b981", "#f59e0b", "#ef4444", "#38bdf8", "#64748b"];

const AnalyticsChart = ({
  t,
  subtitle,
  children,
  empty,
}: {
  t: string;
  subtitle?: string;
  children: any;
  empty: boolean;
}) => (
  <Card className="flex flex-col justify-between">
    <div className="mb-2 border-b border-white/5 pb-2">
      <h3 className="text-xs font-mono font-bold tracking-wider text-white uppercase">{t}</h3>
      {subtitle && <p className="text-[10px] text-slate-400 font-mono">{subtitle}</p>}
    </div>
    <div className="h-60">
      {empty ? (
        <Empty title="Insufficient defect samples" />
      ) : (
        <ResponsiveContainer width="100%" height="100%">
          {children}
        </ResponsiveContainer>
      )}
    </div>
  </Card>
);

export default function Analytics() {
  const [days, setDays] = useState(30);
  const [mode, setMode] = useState("");
  const [pid, setPid] = useState("");
  const m = mode || undefined;

  const d = useQuery({
    queryKey: ["defects", days, m, pid],
    queryFn: () => Api.defects(days, m, pid ? Number(pid) : undefined),
  });
  const lat = useQuery({ queryKey: ["latency", days, m], queryFn: () => Api.latency(days, m) });
  const products = useQuery({ queryKey: ["products"], queryFn: () => Api.products() });

  if (d.isLoading) return <Spinner label="Aggregating defect analytics" />;
  if (d.isError) return <ErrorState message={errMsg(d.error)} onRetry={() => d.refetch()} />;

  const x = d.data!;
  const classes: string[] = Array.from(new Set(x.by_product.flatMap((p: any) => Object.keys(p.by_class))));
  const byProd = x.by_product.map((p: any) => ({ product: p.product, ...p.by_class }));
  const days_: Record<string, any> = {};
  x.category_trends.forEach((r: any) => {
    (days_[r.day] ??= { day: r.day })[r.defect] = r.count;
  });
  const trend = Object.values(days_).sort((a: any, b: any) => a.day.localeCompare(b.day));
  const ev = x.evaluation;
  const maxRegionCount = Math.max(1, ...x.regions.flat());

  return (
    <>
      <PageHeader
        title="Defect Analytics & Spatial Telemetry"
        subtitle="Computed from historical inspection logs. Quality metrics are calculated strictly against verified ground-truth annotations."
      />

      {/* Filter Parameters */}
      <Card className="mb-4 flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-1.5 text-xs font-mono font-bold tracking-wider text-slate-400 uppercase mr-1">
          <Filter size={13} className="text-sky-400" />
          Filter:
        </div>
        <select
          aria-label="Period"
          className="input !w-40 font-mono text-xs"
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
        >
          {[7, 14, 30, 90, 365].map((n) => (
            <option key={n} value={n}>
              Last {n} Days
            </option>
          ))}
        </select>
        <select
          aria-label="Mode"
          className="input !w-48 font-mono text-xs"
          value={mode}
          onChange={(e) => setMode(e.target.value)}
        >
          <option value="">Demo + Real AI</option>
          <option value="real">Real AI Mode Only</option>
          <option value="demo">Demo Simulation Only</option>
        </select>
        <select
          aria-label="Product"
          className="input !w-52 text-xs"
          value={pid}
          onChange={(e) => setPid(e.target.value)}
        >
          <option value="">All Products</option>
          {products.data?.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
      </Card>

      {/* KPI Cards */}
      <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat
          label="Total Sample Volume"
          value={x.total}
          hint="Processed in period"
          icon={<Layers size={15} />}
        />
        <Stat
          label="Human Review Rate"
          value={pct(x.review_rate)}
          accent="text-amber-400"
          hint="Uncertainty threshold"
          icon={<AlertTriangle size={15} className="text-amber-400" />}
        />
        <Stat
          label="Latency p50 / p95"
          value={lat.data?.count ? `${lat.data.p50_ms} / ${lat.data.p95_ms} ms` : "—"}
          hint="Pipeline percentile timing"
          icon={<Clock size={15} />}
        />
        <Stat
          label="Avg Latency"
          value={fmtMs(lat.data?.avg_ms)}
          hint="Mean end-to-end execution"
          icon={<Zap size={15} />}
        />
      </div>

      {/* Defect Analytics Charts Grid */}
      <div className="grid gap-4 lg:grid-cols-2">
        {/* Defect Counts Pareto */}
        <AnalyticsChart t="Defect Counts by Category" empty={!x.counts.length}>
          <BarChart data={x.counts} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
            <CartesianGrid stroke="#1e293b" strokeDasharray="2 2" vertical={false} />
            <XAxis dataKey="defect" {...AXIS_STYLE} tickFormatter={title} />
            <YAxis {...AXIS_STYLE} allowDecimals={false} />
            <Tooltip {...TOOLTIP_STYLE} />
            <Bar name="Count" dataKey="count" fill="#0ea5e9" radius={[4, 4, 0, 0]} />
          </BarChart>
        </AnalyticsChart>

        {/* Defect Category Timeline Trend */}
        <AnalyticsChart t="Defect Category Timeline Trend" empty={!trend.length}>
          <BarChart data={trend} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
            <CartesianGrid stroke="#1e293b" strokeDasharray="2 2" vertical={false} />
            <XAxis dataKey="day" {...AXIS_STYLE} tickFormatter={(s) => s.slice(5)} />
            <YAxis {...AXIS_STYLE} allowDecimals={false} />
            <Tooltip {...TOOLTIP_STYLE} />
            <Legend wrapperStyle={{ fontSize: "11px", fontFamily: "monospace", paddingTop: "4px" }} />
            {Array.from(new Set(x.category_trends.map((r: any) => r.defect))).map((c: any, i) => (
              <Bar
                key={c}
                dataKey={c}
                stackId="a"
                fill={INDUSTRIAL_PALETTE[i % INDUSTRIAL_PALETTE.length]}
              />
            ))}
          </BarChart>
        </AnalyticsChart>

        {/* Product-wise Defect Distribution */}
        <AnalyticsChart
          t="Product-Wise Defect Distribution"
          empty={!byProd.length || !classes.length}
        >
          <BarChart data={byProd} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
            <CartesianGrid stroke="#1e293b" strokeDasharray="2 2" vertical={false} />
            <XAxis dataKey="product" {...AXIS_STYLE} />
            <YAxis {...AXIS_STYLE} allowDecimals={false} />
            <Tooltip {...TOOLTIP_STYLE} />
            <Legend wrapperStyle={{ fontSize: "11px", fontFamily: "monospace", paddingTop: "4px" }} />
            {classes.map((c, i) => (
              <Bar
                key={c}
                dataKey={c}
                stackId="a"
                fill={INDUSTRIAL_PALETTE[i % INDUSTRIAL_PALETTE.length]}
              />
            ))}
          </BarChart>
        </AnalyticsChart>

        {/* Batch-wise Defect Rate */}
        <AnalyticsChart t="Batch-Wise Defect Rate" empty={!x.by_batch.length}>
          <BarChart data={x.by_batch} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
            <CartesianGrid stroke="#1e293b" strokeDasharray="2 2" vertical={false} />
            <XAxis dataKey="batch_code" {...AXIS_STYLE} />
            <YAxis {...AXIS_STYLE} tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} domain={[0, 1]} />
            <Tooltip {...TOOLTIP_STYLE} formatter={(v: any) => pct(v)} />
            <Bar name="Defect Rate" dataKey="defect_rate" fill="#f59e0b" radius={[4, 4, 0, 0]} />
          </BarChart>
        </AnalyticsChart>

        {/* Production Line Comparison */}
        <AnalyticsChart t="Production-Line Defect Comparison" empty={!x.by_line.length}>
          <BarChart data={x.by_line} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
            <CartesianGrid stroke="#1e293b" strokeDasharray="2 2" vertical={false} />
            <XAxis dataKey="line_id" {...AXIS_STYLE} />
            <YAxis {...AXIS_STYLE} tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} domain={[0, 1]} />
            <Tooltip {...TOOLTIP_STYLE} formatter={(v: any) => pct(v)} />
            <Bar name="Defect Rate" dataKey="defect_rate" fill="#ef4444" radius={[4, 4, 0, 0]} />
          </BarChart>
        </AnalyticsChart>

        {/* Spatial 3x3 Heatmap Grid */}
        <Card className="flex flex-col justify-between">
          <div className="border-b border-white/5 pb-2 mb-2">
            <h3 className="text-xs font-mono font-bold tracking-wider text-white uppercase flex items-center gap-1.5">
              <Grid size={13} className="text-sky-400" />
              Spatial Defect Localization Matrix
            </h3>
            <p className="text-[10px] text-slate-400 font-mono">
              Aggregated bounding-box occurrences across a 3 × 3 spatial surface grid
            </p>
          </div>

          <div
            className="mx-auto grid aspect-[4/3] w-full max-w-xs grid-cols-3 gap-1.5 p-2 rounded-lg bg-[#050811] border border-white/10"
            aria-label="Region heat grid"
          >
            {x.regions.flat().map((n: number, i: number) => {
              const intensity = 0.08 + 0.85 * (n / maxRegionCount);
              return (
                <div
                  key={i}
                  className="grid place-items-center rounded border border-white/5 text-xs font-mono font-bold text-white transition hover:scale-105"
                  style={{ backgroundColor: `rgba(239, 68, 68, ${intensity})` }}
                  title={`Zone ${i + 1}: ${n} flagged defect cluster(s)`}
                >
                  <span>{n}</span>
                </div>
              );
            })}
          </div>
          <div className="text-[10px] font-mono text-slate-500 text-center mt-2">
            Top-left [0,0] to Bottom-right [2,2]
          </div>
        </Card>
      </div>

      {/* Detection Quality / Ground Truth Evaluation Module */}
      <Card className="mt-4 space-y-3">
        <div className="flex items-center justify-between border-b border-white/10 pb-2">
          <h3 className="text-xs font-mono font-bold tracking-wider text-white uppercase flex items-center gap-2">
            <ShieldCheck size={15} className="text-emerald-400" />
            Detection Quality & Ground Truth Validation
          </h3>
          <span className="text-[10px] font-mono text-slate-400">
            False-Pass & False-Fail Verification
          </span>
        </div>

        {!ev.evaluated ? (
          <p className="text-xs font-mono text-slate-400 py-2" data-testid="not-evaluated">
            {ev.message}
          </p>
        ) : (
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Stat label="Labeled Samples" value={ev.labeled_samples} />
            <Stat
              label="False Pass (Type II)"
              value={ev.false_pass}
              hint={`rate ${pct(ev.false_pass_rate)}`}
              accent="text-fail"
            />
            <Stat
              label="False Fail (Type I)"
              value={ev.false_fail}
              hint={`rate ${pct(ev.false_fail_rate)}`}
              accent="text-amber-400"
            />
            <Stat
              label="Correct Predictions"
              value={ev.true_flagged + ev.true_good}
              accent="text-pass"
            />
          </div>
        )}

        {ev.evaluated && (
          <p className="text-xs text-slate-400 font-mono">
            {ev.note}
            {ev.includes_demo_samples &&
              " (Includes simulated demonstration inspections; metrics do not represent trained AI models.)"}
          </p>
        )}

        <div className="rounded border border-white/10 bg-slate-950/70 p-2.5 text-xs text-slate-400 font-mono">
          ℹ️ Industrial Note: Accuracy, precision, recall, F1 and AUROC are computed exclusively against held-out, verified ground-truth test sets. No fabricated metrics are displayed.
        </div>
      </Card>
    </>
  );
}
