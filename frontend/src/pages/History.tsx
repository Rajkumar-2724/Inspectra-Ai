import { useQuery } from "@tanstack/react-query";
import { FileDown, Filter, History as HistIcon, Search } from "lucide-react";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  Card,
  DecisionBadge,
  Empty,
  ErrorState,
  ModeBadge,
  PageHeader,
  Pagination,
  Spinner,
} from "../components/ui";
import { Api, download, errMsg } from "../services/api";
import { fmtDate, fmtMs, fmtScore, title } from "../utils/format";

export default function History() {
  const [sp, setSp] = useSearchParams();
  const [page, setPage] = useState(1);

  const f = {
    search: sp.get("search") ?? "",
    decision: sp.get("decision") ?? "",
    mode: sp.get("mode") ?? "",
    product_id: sp.get("product_id") ?? "",
    batch_code: sp.get("batch_code") ?? "",
  };

  const set = (k: string, v: string) => {
    const n = new URLSearchParams(sp);
    v ? n.set(k, v) : n.delete(k);
    setSp(n, { replace: true });
    setPage(1);
  };

  const clean = Object.fromEntries(Object.entries(f).filter(([, v]) => v));
  const q = useQuery({
    queryKey: ["inspections", clean, page],
    queryFn: () => Api.inspections({ ...clean, page, page_size: 15 }),
    placeholderData: (p) => p,
  });
  const products = useQuery({ queryKey: ["products"], queryFn: () => Api.products() });

  return (
    <>
      <PageHeader
        title="Inspection History Ledger"
        subtitle="Complete record of optical inspections, threshold evaluations, decisions, and cryptographic timestamps."
        actions={
          <button
            className="btn-primary"
            onClick={() => download("/api/inspections/export/csv", "inspections-ledger.csv", clean)}
          >
            <FileDown size={14} />
            Export Filtered CSV
          </button>
        }
      />

      {/* Multi-Parameter Filter Card */}
      <Card className="mb-4 space-y-2.5">
        <div className="flex items-center gap-1.5 text-xs font-mono font-bold tracking-wider text-slate-400 uppercase">
          <Filter size={13} className="text-sky-400" />
          Filter Parameters
        </div>
        <div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-5">
          <div className="relative">
            <Search size={13} className="absolute left-2.5 top-2.5 text-slate-500" />
            <input
              aria-label="Search"
              className="input !pl-8 text-xs font-mono"
              placeholder="Search serial, batch, defect…"
              value={f.search}
              onChange={(e) => set("search", e.target.value)}
            />
          </div>
          <select
            aria-label="Decision"
            className="input text-xs font-mono"
            value={f.decision}
            onChange={(e) => set("decision", e.target.value)}
          >
            <option value="">All Decisions</option>
            <option>PASS</option>
            <option>REVIEW</option>
            <option>FAIL</option>
          </select>
          <select
            aria-label="Mode"
            className="input text-xs font-mono"
            value={f.mode}
            onChange={(e) => set("mode", e.target.value)}
          >
            <option value="">All Telemetry</option>
            <option value="real">Real AI Mode (PatchCore)</option>
          </select>
          <select
            aria-label="Product"
            className="input text-xs"
            value={f.product_id}
            onChange={(e) => set("product_id", e.target.value)}
          >
            <option value="">All Products</option>
            {products.data?.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
          <input
            aria-label="Batch"
            className="input text-xs font-mono"
            placeholder="Batch ID filter…"
            value={f.batch_code}
            onChange={(e) => set("batch_code", e.target.value)}
          />
        </div>
      </Card>

      {/* Primary Data Grid */}
      <Card>
        {q.isLoading ? (
          <Spinner label="Loading inspection records" />
        ) : q.isError ? (
          <ErrorState message={errMsg(q.error)} onRetry={() => q.refetch()} />
        ) : !q.data?.items.length ? (
          <Empty
            title="No inspections match the specified query"
            hint="Adjust filters or clear search query to inspect other records."
          />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr>
                    <th className="th">Record #</th>
                    <th className="th">Timestamp</th>
                    <th className="th">Product Type</th>
                    <th className="th">Serial / Batch / Line</th>
                    <th className="th">Anomaly Score</th>
                    <th className="th">AI Decision</th>
                    <th className="th">Defect Class</th>
                    <th className="th">Latency</th>
                    <th className="th">Mode</th>
                    <th className="th">Human Review</th>
                    <th className="th text-right">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {q.data.items.map((i) => (
                    <tr
                      key={i.id}
                      className="border-t border-white/5 hover:bg-white/[0.02] transition"
                    >
                      <td className="td font-mono font-bold text-sky-400">
                        <Link className="hover:underline" to={`/history/${i.id}`}>
                          #{i.id}
                        </Link>
                      </td>
                      <td className="td whitespace-nowrap font-mono text-[11px] text-slate-300">
                        {fmtDate(i.created_at)}
                      </td>
                      <td className="td font-medium text-slate-100">{i.product_name}</td>
                      <td className="td font-mono text-[11px] text-slate-400">
                        {i.product_code || "—"} / {i.batch_code || "—"} / {i.line_id || "—"}
                      </td>
                      <td className="td font-mono font-semibold">{fmtScore(i.score)}</td>
                      <td className="td">
                        <DecisionBadge d={i.decision} />
                      </td>
                      <td className="td font-mono text-[11px] text-slate-300">
                        {i.defect_class === "unclassified_anomaly" ? "Anomaly detected" : title(i.defect_class)}
                      </td>
                      <td className="td font-mono text-[11px] text-slate-400">
                        {fmtMs(i.latency_ms)}
                      </td>
                      <td className="td">
                        <ModeBadge mode={i.mode} simulated={i.simulated} />
                      </td>
                      <td className="td font-mono text-[11px]">
                        {i.review_status === "PENDING" ? (
                          <span className="text-amber-400 font-semibold">Pending Review</span>
                        ) : i.final_decision ? (
                          <DecisionBadge d={i.final_decision} />
                        ) : (
                          <span className="text-slate-500">—</span>
                        )}
                      </td>
                      <td className="td text-right">
                        <Link
                          className="btn-ghost !px-2 !py-0.5 !text-[11px] font-mono text-sky-400 hover:text-white"
                          to={`/history/${i.id}`}
                        >
                          View →
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination
              page={q.data.page}
              pageSize={q.data.page_size}
              total={q.data.total}
              onChange={setPage}
            />
          </>
        )}
      </Card>
    </>
  );
}
