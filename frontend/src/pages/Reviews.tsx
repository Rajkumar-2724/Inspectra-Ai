import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  ClipboardCheck,
  FileText,
  RotateCcw,
  ShieldAlert,
  XCircle,
} from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import toast from "react-hot-toast";
import { z } from "zod";
import { ResultView } from "../components/ResultView";
import { Card, DecisionBadge, Empty, ErrorState, PageHeader, Spinner } from "../components/ui";
import { useAuth } from "../contexts/AuthContext";
import { Api, errMsg } from "../services/api";
import { fmtDate, fmtScore, title } from "../utils/format";

const schema = z.object({ comment: z.string().max(2000) });

export default function Reviews() {
  const { has } = useAuth();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["pending"], queryFn: Api.pendingReviews });
  const [sel, setSel] = useState<number | null>(null);
  const { register, getValues, reset } = useForm<{ comment: string }>({
    resolver: zodResolver(schema),
    defaultValues: { comment: "" },
  });

  if (q.isLoading) return <Spinner label="Loading pending review queue" />;
  if (q.isError) return <ErrorState message={errMsg(q.error)} onRetry={() => q.refetch()} />;

  const items = q.data!;
  const cur = items.find((i) => i.id === sel) ?? items[0];
  const canAct = has("reviewer");

  const act = async (decision: string) => {
    const comment = getValues("comment").trim();
    if (decision === "reject" && !comment)
      return toast.error("A comment explaining the rejection rationale is required");
    try {
      await Api.decide(cur.id, decision, comment);
      toast.success(`Review decision recorded: ${decision.toUpperCase()}`);
      reset();
      setSel(null);
      qc.invalidateQueries();
    } catch (e) {
      toast.error(errMsg(e));
    }
  };

  return (
    <>
      <PageHeader
        title="Human Review Workstation"
        subtitle="Human-in-the-loop quality review for border-line anomaly scores. Review decisions are recorded alongside the original AI inference."
      />

      {!items.length ? (
        <Card>
          <Empty
            title="Review Queue Clear"
            hint="No units currently require human sign-off. Inspections falling between the review threshold and fail threshold will populate here automatically."
          />
        </Card>
      ) : (
        <div className="grid gap-4 xl:grid-cols-12 items-start">
          {/* Left Column: Pending Review Queue */}
          <Card className="xl:col-span-4 !p-3 space-y-2">
            <div className="flex items-center justify-between border-b border-white/10 pb-2 px-1">
              <span className="text-xs font-mono font-bold tracking-wider text-white uppercase flex items-center gap-1.5">
                <ClipboardCheck size={14} className="text-amber-400" />
                Queue Items ({items.length})
              </span>
              <span className="text-[10px] font-mono text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/30">
                AWAITING SIGNOFF
              </span>
            </div>

            <ul className="space-y-1.5 max-h-[680px] overflow-y-auto pr-1" aria-label="Pending reviews">
              {items.map((i) => (
                <li key={i.id}>
                  <button
                    onClick={() => setSel(i.id)}
                    className={`w-full rounded border p-2.5 text-left transition font-mono ${
                      cur.id === i.id
                        ? "border-sky-400/60 bg-sky-500/15 ring-1 ring-sky-500/30 text-white"
                        : "border-white/5 bg-ink-950/60 hover:bg-white/[0.04] text-slate-300"
                    }`}
                  >
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-bold text-white">
                        #{i.id} {i.product_name}
                      </span>
                      <span className="text-amber-400 font-semibold">{fmtScore(i.score)}</span>
                    </div>
                    <div className="mt-1 flex items-center justify-between text-[11px] text-slate-400">
                      <span>Defect: {title(i.defect_class)}</span>
                      <span>{fmtDate(i.created_at)}</span>
                    </div>
                    {i.simulated && (
                      <div className="mt-1 text-[10px] text-amber-300/80 uppercase">
                        simulated test pattern
                      </div>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          </Card>

          {/* Right Column: Active Inspection Inspection & Decision Box */}
          <div className="space-y-4 xl:col-span-8">
            <ResultView insp={cur} compact />

            {/* Quality Sign-Off Decision Box */}
            <Card className="space-y-3">
              <div className="flex items-center justify-between border-b border-white/10 pb-2">
                <h3 className="text-xs font-mono font-bold tracking-wider text-white uppercase">
                  Quality Inspector Sign-Off on #{cur.id}
                </h3>
                <div className="flex items-center gap-2 text-xs font-mono">
                  <span className="text-slate-400">AI Proposed:</span>
                  <DecisionBadge d={cur.decision} />
                </div>
              </div>

              {canAct ? (
                <>
                  <div>
                    <label className="label" htmlFor="rc">
                      Reviewer Assessment & Commentary (Required for rejection)
                    </label>
                    <textarea
                      id="rc"
                      rows={3}
                      className="input font-mono !text-xs"
                      placeholder="Detail specific observations, defect confirmation, tolerance variance, or reason for rejection…"
                      {...register("comment")}
                    />
                  </div>

                  <div className="flex flex-wrap gap-2 pt-1">
                    <button
                      className="btn-success !px-4 !py-2 text-xs font-mono font-semibold"
                      onClick={() => act("approve")}
                    >
                      <CheckCircle2 size={15} />
                      Approve Unit (Mark PASS)
                    </button>
                    <button
                      className="btn-danger !px-4 !py-2 text-xs font-mono font-semibold"
                      onClick={() => act("reject")}
                    >
                      <XCircle size={15} />
                      Reject Unit (Mark FAIL)
                    </button>
                    <button
                      className="btn-ghost !px-3 !py-2 text-xs font-mono"
                      onClick={() => act("reinspect")}
                    >
                      <RotateCcw size={14} />
                      Request Sensor Re-Inspection
                    </button>
                  </div>
                </>
              ) : (
                <p className="text-xs font-mono text-slate-400 py-2">
                  Only users with Quality Reviewer or Administrator permissions can record sign-off decisions.
                </p>
              )}
            </Card>
          </div>
        </div>
      )}
    </>
  );
}
