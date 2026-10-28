import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, CheckCircle2, FileCheck, ShieldCheck, UserCheck, XCircle } from "lucide-react";
import toast from "react-hot-toast";
import { Link, useParams } from "react-router-dom";
import { ResultView } from "../components/ResultView";
import { Card, DecisionBadge, ErrorState, PageHeader, Spinner } from "../components/ui";
import { useAuth } from "../contexts/AuthContext";
import { Api, errMsg } from "../services/api";
import { fmtDate } from "../utils/format";

export default function InspectionDetail() {
  const id = Number(useParams().id);
  const { has } = useAuth();
  const qc = useQueryClient();

  const q = useQuery({ queryKey: ["inspection", id], queryFn: () => Api.inspection(id) });
  const audit = useQuery({
    queryKey: ["audit-insp", id],
    queryFn: () => Api.auditEvents({ inspection_id: id, page_size: 50 }),
  });

  if (q.isLoading) return <Spinner label="Loading inspection details" />;
  if (q.isError) return <ErrorState message={errMsg(q.error)} onRetry={() => q.refetch()} />;

  const i = q.data!;

  const label = async (g: "good" | "defective") => {
    try {
      await Api.groundTruth({ inspection_id: id, ground_truth: g });
      toast.success(`Verified ground-truth recorded: ${g.toUpperCase()}`);
      qc.invalidateQueries({ queryKey: ["defects"] });
    } catch (e) {
      toast.error(errMsg(e));
    }
  };

  return (
    <>
      <PageHeader
        title={`Inspection #${i.id} Details`}
        subtitle={`${i.product_name} · Serial: ${i.product_code || "—"} · Batch: ${
          i.batch_code || "—"
        } · Line: ${i.line_id || "—"}`}
        actions={
          <Link to="/history" className="btn-ghost">
            <ArrowLeft size={14} />
            Back to History Ledger
          </Link>
        }
      />

      {/* Main Inspection View */}
      <ResultView insp={i} />

      {/* Human Review & Cryptographic Audit Records */}
      <div className="mt-5 grid gap-4 lg:grid-cols-2 items-start">
        {/* Human Review Assessment History */}
        <Card>
          <div className="flex items-center justify-between border-b border-white/10 pb-2 mb-3">
            <h3 className="text-xs font-mono font-bold tracking-wider text-white uppercase flex items-center gap-1.5">
              <UserCheck size={14} className="text-sky-400" />
              Human Review & Quality Signoff
            </h3>
            <span className="text-[10px] font-mono text-slate-400">
              {i.reviews.length} Logged Action{i.reviews.length === 1 ? "" : "s"}
            </span>
          </div>

          {!i.reviews.length ? (
            <p className="text-xs font-mono text-slate-500 py-2">
              {i.review_status === "PENDING"
                ? "This unit is currently pending human review."
                : "No human review actions required or recorded for this item."}
            </p>
          ) : (
            <ul className="space-y-2">
              {i.reviews.map((r) => (
                <li
                  key={r.id}
                  className="rounded border border-white/10 bg-ink-950/60 p-3 text-xs font-mono space-y-1"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-white flex items-center gap-1.5">
                      <span className="capitalize">{r.decision}</span>
                      <span className="font-normal text-slate-400">by {r.reviewer_name}</span>
                    </span>
                    <span className="text-[10px] text-slate-500">{fmtDate(r.created_at)}</span>
                  </div>
                  {r.comment && (
                    <p className="text-slate-300 font-sans text-xs pt-1 border-t border-white/5">
                      {r.comment}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          )}

          <div className="mt-3 flex items-center gap-2 border-t border-white/5 pt-2 text-xs font-mono">
            <span className="text-slate-400">Original AI Decision:</span>
            <DecisionBadge d={i.decision} />
            {i.final_decision && (
              <>
                <span className="text-slate-400 ml-2">→ Final Decision:</span>
                <DecisionBadge d={i.final_decision} />
              </>
            )}
          </div>

          {i.notes && (
            <p className="mt-3 text-xs text-slate-300 rounded bg-black/30 p-2 border border-white/5 font-mono">
              <span className="text-slate-400 uppercase text-[10px] block">Operator Notes:</span>
              {i.notes}
            </p>
          )}
        </Card>

        {/* Cryptographic Audit Chain Records */}
        <Card>
          <div className="flex items-center justify-between border-b border-white/10 pb-2 mb-3">
            <h3 className="text-xs font-mono font-bold tracking-wider text-white uppercase flex items-center gap-1.5">
              <ShieldCheck size={14} className="text-sky-400" />
              Cryptographic Audit Chain
            </h3>
            <span className="text-[10px] font-mono text-slate-400">Immutable Ledger</span>
          </div>

          {!audit.data?.items.length ? (
            <p className="text-xs font-mono text-slate-500 py-2">
              No audit chain events recorded yet.
            </p>
          ) : (
            <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
              {audit.data.items.map((e) => (
                <div
                  key={e.id}
                  className="rounded border border-white/10 bg-ink-950/60 p-2.5 font-mono text-xs"
                >
                  <div className="flex items-center justify-between text-slate-300">
                    <span className="font-semibold text-white">
                      Seq #{e.seq} · {e.event_type}
                    </span>
                    <span className="text-[10px] text-slate-500">{fmtDate(e.created_at)}</span>
                  </div>
                  <div className="break-all text-[10px] text-sky-400 mt-1 select-all">
                    HASH: {e.record_hash}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Ground Truth Validation for Metrics */}
          {has("reviewer") && (
            <div className="mt-4 border-t border-white/10 pt-3">
              <div className="text-[10px] font-mono tracking-wider uppercase text-slate-400 mb-1.5">
                Verified Ground Truth (Enables False-Pass / False-Fail Metric Tracking)
              </div>
              <div className="flex gap-2">
                <button
                  type="button"
                  className="btn-success !px-3 !py-1 text-xs font-mono"
                  onClick={() => label("good")}
                >
                  <CheckCircle2 size={13} />
                  Mark Ground Truth: Nominal (Good)
                </button>
                <button
                  type="button"
                  className="btn-danger !px-3 !py-1 text-xs font-mono"
                  onClick={() => label("defective")}
                >
                  <XCircle size={13} />
                  Mark Ground Truth: Defective
                </button>
              </div>
            </div>
          )}
        </Card>
      </div>
    </>
  );
}
