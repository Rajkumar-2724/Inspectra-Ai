import { useQuery } from "@tanstack/react-query";
import {
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  FileText,
  Filter,
  Lock,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import toast from "react-hot-toast";
import { Card, Empty, ErrorState, PageHeader, Pagination, Spinner } from "../components/ui";
import { useAuth } from "../contexts/AuthContext";
import { Api, errMsg } from "../services/api";
import { fmtDate } from "../utils/format";

export default function Audit() {
  const { has } = useAuth();
  const [page, setPage] = useState(1);
  const [type, setType] = useState("");
  const [open, setOpen] = useState<number | null>(null);
  const [verify, setVerify] = useState<Awaited<ReturnType<typeof Api.auditVerify>> | null>(null);
  const [busy, setBusy] = useState(false);

  const q = useQuery({
    queryKey: ["audit", page, type],
    queryFn: () => Api.auditEvents({ page, page_size: 15, event_type: type || undefined }),
  });

  const run = async () => {
    setBusy(true);
    try {
      const res = await Api.auditVerify();
      setVerify(res);
      res.valid
        ? toast.success(`Audit chain verified: ${res.events_checked} records intact`)
        : toast.error("Audit chain integrity warning: discrepancy detected");
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <PageHeader
        title="Cryptographic Audit Trail Ledger"
        subtitle="Append-only, SHA-256 hash-chained immutable event records tracking every visual inspection and human sign-off."
        actions={
          has() && (
            <button className="btn-primary font-mono text-xs" onClick={run} disabled={busy}>
              <ShieldCheck size={15} />
              {busy ? "Verifying Hash Chain…" : "Verify Cryptographic Chain"}
            </button>
          )
        }
      />

      {/* Verification Integrity Result Alert */}
      {verify && (
        <Card
          className={`mb-4 border ${
            verify.valid ? "!border-pass/40 bg-pass/5" : "!border-fail/50 bg-fail/5"
          }`}
        >
          <div className="flex items-start gap-3" role="status">
            {verify.valid ? (
              <ShieldCheck className="text-pass shrink-0 mt-0.5" size={20} />
            ) : (
              <ShieldAlert className="text-fail shrink-0 mt-0.5" size={20} />
            )}
            <div className="space-y-1 font-mono text-xs">
              <div
                className={`font-bold uppercase tracking-wider text-sm ${
                  verify.valid ? "text-pass" : "text-fail"
                }`}
                data-testid="verify-result"
              >
                {verify.valid ? "Chain intact" : "Tampering detected"} — {verify.events_checked} records checked
              </div>
              <div className="break-all text-[11px] text-slate-400">
                HEAD HASH: <span className="text-sky-300">{verify.head_hash}</span>
              </div>
              {verify.problems.map((p, i) => (
                <div key={i} className="text-xs text-fail font-semibold">
                  Record #{p.seq}: {p.problem}
                </div>
              ))}
              <p className="text-[11px] text-slate-400 font-sans">{verify.note}</p>
            </div>
          </div>
        </Card>
      )}

      {/* Filter and Ledger Table Card */}
      <Card className="space-y-3">
        <div className="flex items-center justify-between border-b border-white/10 pb-2">
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono font-bold tracking-wider text-white uppercase flex items-center gap-1.5">
              <Lock size={13} className="text-sky-400" />
              Event Ledger
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-mono text-slate-400 uppercase">Event Filter:</span>
            <select
              aria-label="Event type"
              className="input !w-44 !py-0.5 font-mono text-xs"
              value={type}
              onChange={(e) => {
                setType(e.target.value);
                setPage(1);
              }}
            >
              <option value="">All Event Types</option>
              <option value="INSPECTION">Inspections Only</option>
              <option value="REVIEW">Reviews Only</option>
            </select>
          </div>
        </div>

        {q.isLoading ? (
          <Spinner label="Verifying ledger records" />
        ) : q.isError ? (
          <ErrorState message={errMsg(q.error)} />
        ) : !q.data?.items.length ? (
          <Empty title="No audit records found" />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-left font-mono">
                <thead>
                  <tr>
                    <th className="th">Sequence #</th>
                    <th className="th">Event Type</th>
                    <th className="th">Target Inspection</th>
                    <th className="th">Timestamp</th>
                    <th className="th">Record SHA-256 Hash</th>
                    <th className="th text-right">Payload</th>
                  </tr>
                </thead>
                <tbody>
                  {q.data.items.map((e) => (
                    <>
                      <tr
                        key={e.id}
                        className="border-t border-white/5 hover:bg-white/[0.02] text-xs"
                      >
                        <td className="td font-bold text-white">#{e.seq}</td>
                        <td className="td">
                          <span
                            className={`px-1.5 py-0.2 rounded text-[10px] font-bold border ${
                              e.event_type === "INSPECTION"
                                ? "border-sky-500/40 bg-sky-500/10 text-sky-400"
                                : "border-amber-500/40 bg-amber-500/10 text-amber-300"
                            }`}
                          >
                            {e.event_type}
                          </span>
                        </td>
                        <td className="td">
                          {e.inspection_id ? (
                            <Link
                              className="text-sky-400 hover:underline font-semibold"
                              to={`/history/${e.inspection_id}`}
                            >
                              Inspection #{e.inspection_id}
                            </Link>
                          ) : (
                            <span className="text-slate-500">—</span>
                          )}
                        </td>
                        <td className="td whitespace-nowrap text-[11px] text-slate-300">
                          {fmtDate(e.created_at)}
                        </td>
                        <td className="td text-[11px] text-slate-400 select-all">
                          {e.record_hash.slice(0, 20)}…
                        </td>
                        <td className="td text-right">
                          <button
                            className="btn-ghost !px-2 !py-0.5 text-[11px] text-sky-400 hover:text-white"
                            onClick={() => setOpen(open === e.id ? null : e.id)}
                          >
                            {open === e.id ? "Hide JSON" : "Inspect Payload"}
                          </button>
                        </td>
                      </tr>
                      {open === e.id && (
                        <tr key={`${e.id}d`}>
                          <td colSpan={6} className="bg-[#050811] p-3 border-t border-white/10">
                            <div className="space-y-1.5 text-xs font-mono">
                              <div className="text-[11px] text-slate-400">
                                <strong>PREVIOUS BLOCK HASH:</strong>{" "}
                                <span className="text-slate-300">{e.prev_hash}</span>
                              </div>
                              <div className="text-[11px] text-slate-400">
                                <strong>RECORD BLOCK HASH:</strong>{" "}
                                <span className="text-sky-300">{e.record_hash}</span>
                              </div>
                              <div className="pt-2">
                                <span className="text-[10px] uppercase text-slate-400 block mb-1">
                                  Cryptographic Payload Data:
                                </span>
                                <pre className="overflow-x-auto rounded border border-white/10 bg-black/60 p-2 text-[11px] text-slate-200">
                                  {JSON.stringify(e.payload, null, 2)}
                                </pre>
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </>
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
