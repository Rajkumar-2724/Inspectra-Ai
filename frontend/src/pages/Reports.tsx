import { useQuery } from "@tanstack/react-query";
import { Download, FileCheck, FileDown, FileSpreadsheet, FileText, Printer, Search } from "lucide-react";
import { useState } from "react";
import toast from "react-hot-toast";
import { Card, DecisionBadge, Empty, PageHeader, Spinner } from "../components/ui";
import { Api, download, errMsg } from "../services/api";
import { fmtDate, fmtScore } from "../utils/format";

export default function Reports() {
  const [mode, setMode] = useState("");
  const [id, setId] = useState("");

  const recent = useQuery({
    queryKey: ["inspections", "reports"],
    queryFn: () => Api.inspections({ page: 1, page_size: 10 }),
  });
  const batches = useQuery({ queryKey: ["batches"], queryFn: Api.batches });

  const run = async (fn: () => Promise<void>) => {
    try {
      await fn();
    } catch (e) {
      toast.error(errMsg(e));
    }
  };

  return (
    <>
      <PageHeader
        title="Quality Assurance Reports & Certificates"
        subtitle="Download official PDF inspection certificates, batch quality summaries, and full CSV compliance logs."
      />

      <div className="grid gap-4 lg:grid-cols-2 items-start">
        {/* 1. Individual Inspection PDF Certificate */}
        <Card className="space-y-3">
          <div className="flex items-center justify-between border-b border-white/10 pb-2">
            <h3 className="text-xs font-mono font-bold tracking-wider text-white uppercase flex items-center gap-1.5">
              <FileCheck size={14} className="text-sky-400" />
              Individual Inspection Certificate (PDF)
            </h3>
            <span className="text-[10px] font-mono text-slate-400">Standard Certificate</span>
          </div>

          <div className="flex gap-2">
            <div className="relative flex-1">
              <input
                aria-label="Inspection ID"
                className="input font-mono !text-xs"
                placeholder="Enter Inspection Record ID (e.g. 89)"
                inputMode="numeric"
                value={id}
                onChange={(e) => setId(e.target.value.replace(/\D/g, ""))}
              />
            </div>
            <button
              className="btn-primary shrink-0 font-mono"
              disabled={!id}
              onClick={() =>
                run(() => download(`/api/inspections/${id}/report`, `inspection-certificate-${id}.pdf`))
              }
            >
              <FileDown size={14} />
              Generate PDF
            </button>
          </div>

          {recent.isLoading ? (
            <Spinner label="Loading recent inspection list" />
          ) : !recent.data?.items.length ? (
            <Empty title="No recent inspections available" />
          ) : (
            <div className="space-y-1 pt-1">
              <div className="text-[10px] font-mono uppercase tracking-wider text-slate-400 mb-1">
                Recent Unit Inspections:
              </div>
              <ul className="divide-y divide-white/5 border border-white/5 rounded-lg bg-ink-950/60 max-h-56 overflow-y-auto">
                {recent.data.items.map((i) => (
                  <li
                    key={i.id}
                    className="flex items-center justify-between p-2 text-xs font-mono hover:bg-white/[0.02]"
                  >
                    <span className="truncate pr-2">
                      <strong className="text-white">#{i.id}</strong> · {i.product_name}
                      <span className="text-[10px] text-slate-500 ml-2">
                        {fmtDate(i.created_at)}
                      </span>
                    </span>
                    <span className="flex items-center gap-2 shrink-0">
                      <span className="text-slate-400">{fmtScore(i.score)}</span>
                      <DecisionBadge d={i.decision} />
                      <button
                        className="btn-ghost !p-1 text-sky-400 hover:text-white"
                        aria-label={`Download report ${i.id}`}
                        title="Download Certificate PDF"
                        onClick={() =>
                          run(() =>
                            download(
                              `/api/inspections/${i.id}/report`,
                              `inspection-certificate-${i.id}.pdf`
                            )
                          )
                        }
                      >
                        <FileDown size={13} />
                      </button>
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Card>

        {/* 2. Batch Quality Reports */}
        <Card className="space-y-3">
          <div className="flex items-center justify-between border-b border-white/10 pb-2">
            <h3 className="text-xs font-mono font-bold tracking-wider text-white uppercase flex items-center gap-1.5">
              <FileText size={14} className="text-sky-400" />
              Production Batch Summaries
            </h3>
            <span className="text-[10px] font-mono text-slate-400">PDF & CSV</span>
          </div>

          {!batches.data?.length ? (
            <Empty
              title="No batches recorded"
              hint="Execute a batch inspection on the Batch Inspection page to generate lot reports."
            />
          ) : (
            <div className="space-y-1">
              <div className="text-[10px] font-mono uppercase tracking-wider text-slate-400 mb-1">
                Completed Production Lots:
              </div>
              <ul className="divide-y divide-white/5 border border-white/5 rounded-lg bg-ink-950/60 max-h-72 overflow-y-auto">
                {batches.data.map((b) => (
                  <li
                    key={b.id}
                    className="flex items-center justify-between p-2.5 text-xs font-mono hover:bg-white/[0.02]"
                  >
                    <div>
                      <div className="font-semibold text-white">{b.batch_code}</div>
                      <div className="text-[10px] text-slate-400">
                        {b.product_name} · {b.job_counts.DONE} units inspected
                      </div>
                    </div>
                    <div className="flex gap-1.5">
                      <button
                        className="btn-ghost !px-2 !py-1 text-xs font-mono"
                        onClick={() =>
                          run(() => download(`/api/batches/${b.id}/report`, `batch-report-${b.id}.pdf`))
                        }
                      >
                        <FileDown size={12} />
                        PDF
                      </button>
                      <button
                        className="btn-ghost !px-2 !py-1 text-xs font-mono"
                        onClick={() =>
                          run(() =>
                            download(`/api/batches/${b.id}/export/csv`, `batch-data-${b.id}.csv`)
                          )
                        }
                      >
                        <FileSpreadsheet size={12} />
                        CSV
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Card>

        {/* 3. Global Compliance CSV Export */}
        <Card className="lg:col-span-2 space-y-3">
          <div className="flex items-center justify-between border-b border-white/10 pb-2">
            <h3 className="text-xs font-mono font-bold tracking-wider text-white uppercase flex items-center gap-1.5">
              <FileSpreadsheet size={14} className="text-emerald-400" />
              Full Inspection History Ledger Export
            </h3>
            <span className="text-[10px] font-mono text-slate-400">CSV Export</span>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <select
              aria-label="Export mode"
              className="input !w-52 font-mono text-xs"
              value={mode}
              onChange={(e) => setMode(e.target.value)}
            >
              <option value="">All Records (Demo + Real)</option>
              <option value="real">Real AI Inspections Only</option>
              <option value="demo">Demo Simulations Only</option>
            </select>

            <button
              className="btn-primary font-mono text-xs"
              onClick={() =>
                run(() => download("/api/inspections/export/csv", "inspections-compliance.csv", mode ? { mode } : {}))
              }
            >
              <Download size={14} />
              Export Complete CSV Ledger
            </button>
          </div>

          <p className="text-xs text-slate-400 font-mono">
            Every exported record explicitly flags the execution mode (REAL vs DEMO) and cryptographic SHA-256 hash to ensure compliance transparency.
          </p>
        </Card>
      </div>
    </>
  );
}
