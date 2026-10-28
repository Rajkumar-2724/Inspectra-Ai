import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Boxes,
  CheckCircle2,
  FileDown,
  Layers,
  Loader2,
  Play,
  RefreshCw,
  UploadCloud,
  XCircle,
} from "lucide-react";
import { useState } from "react";
import { useDropzone } from "react-dropzone";
import { Controller, useForm } from "react-hook-form";
import toast from "react-hot-toast";
import { Link } from "react-router-dom";
import { z } from "zod";
import { ProductSelect } from "../components/Selectors";
import { Card, DecisionBadge, Empty, FieldError, ModeBadge, PageHeader } from "../components/ui";
import { useMode } from "../contexts/ModeContext";
import { Api, download, errMsg } from "../services/api";
import { fmtScore, title } from "../utils/format";

const schema = z.object({
  product_id: z.number({ invalid_type_error: "Select a product" }),
  batch_code: z.string().min(1, "Enter a batch ID").max(64),
  line_id: z.string().max(64).optional(),
});
type F = z.infer<typeof schema>;

const STATUS_BADGE = {
  QUEUED: "border-slate-700 bg-slate-800 text-slate-400",
  PROCESSING: "border-sky-500/40 bg-sky-500/10 text-sky-400 animate-pulse",
  DONE: "border-pass/40 bg-pass/10 text-pass",
  FAILED: "border-fail/40 bg-fail/10 text-fail",
} as const;

export default function Batch() {
  const { mode } = useMode();
  const qc = useQueryClient();
  const [files, setFiles] = useState<File[]>([]);
  const [batchId, setBatchId] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [filter, setFilter] = useState("");

  const {
    control,
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<F>({
    resolver: zodResolver(schema),
    defaultValues: { batch_code: "", line_id: "" },
  });

  const dz = useDropzone({
    accept: { "image/jpeg": [], "image/png": [], "image/webp": [] },
    maxSize: 15 * 1024 * 1024,
    onDrop: (a) => setFiles((f) => [...f, ...a].slice(0, 200)),
    onDropRejected: () => toast.error("Some files rejected (must be JPG/PNG/WEBP ≤ 15MB)"),
  });

  const batch = useQuery({
    queryKey: ["batch", batchId],
    enabled: !!batchId,
    queryFn: () => Api.batch(batchId!),
    refetchInterval: (q) => {
      const d = q.state.data;
      return d && d.job_counts.QUEUED + d.job_counts.PROCESSING > 0 ? 1000 : false;
    },
  });

  const items = useQuery({
    queryKey: ["batch-items", batchId, batch.data?.job_counts?.DONE, filter],
    enabled: !!batchId,
    queryFn: () => Api.batchInspections(batchId!, filter || undefined),
  });

  const past = useQuery({ queryKey: ["batches"], queryFn: Api.batches });

  const submit = async (v: F) => {
    if (!files.length) return toast.error("Add at least one image file to batch queue");
    setBusy(true);
    try {
      const b = await Api.createBatch({
        product_id: v.product_id,
        batch_code: v.batch_code,
        line_id: v.line_id ?? "",
        mode: "real",
        scenario: null,
      });
      setBatchId(b.id);
      await Api.batchUpload(b.id, files);
      setFiles([]);
      qc.invalidateQueries({ queryKey: ["batches"] });
      toast.success(`Batch #${b.id} queued for processing`);
    } catch (e) {
      toast.error(errMsg(e), { duration: 7000 });
    } finally {
      setBusy(false);
    }
  };

  const retry = async () => {
    try {
      await Api.batchRetry(batchId!);
      batch.refetch();
      toast.success("Retrying failed units");
    } catch (e) {
      toast.error(errMsg(e));
    }
  };

  const b = batch.data;
  const byInsp = new Map(items.data?.map((i) => [i.id, i]));

  return (
    <>
      <PageHeader
        title="Batch Quality Inspection"
        subtitle="High-throughput batch inspection queue powered by the trained PatchCore ONNX model."
        actions={<ModeBadge mode="real" simulated={false} />}
      />

      {/* Batch Setup & Upload Grid */}
      <form
        onSubmit={handleSubmit(submit)}
        className="grid gap-4 lg:grid-cols-2"
        aria-label="Batch form"
      >
        <Card className="space-y-3">
          <div className="border-b border-white/10 pb-2">
            <span className="text-xs font-mono font-bold tracking-wider text-white uppercase flex items-center gap-1.5">
              <Boxes size={14} className="text-sky-400" />
              1. Batch Setup & Identification
            </span>
          </div>

          <div>
            <label className="label">Target Product Type</label>
            <Controller
              control={control}
              name="product_id"
              render={({ field }) => (
                <ProductSelect
                  id="bp"
                  value={field.value ?? ""}
                  onChange={(v) => field.onChange(v === "" ? undefined : v)}
                />
              )}
            />
            <FieldError msg={errors.product_id?.message} />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label" htmlFor="bcode">
                Batch Lot Code
              </label>
              <input
                id="bcode"
                className="input font-mono"
                placeholder="e.g. LOT-2026-B08"
                {...register("batch_code")}
              />
              <FieldError msg={errors.batch_code?.message} />
            </div>
            <div>
              <label className="label" htmlFor="bline">
                Assembly Line ID
              </label>
              <input
                id="bline"
                className="input font-mono"
                placeholder="e.g. LINE-3A"
                {...register("line_id")}
              />
            </div>
          </div>

          <button
            type="submit"
            className="btn-primary w-full !py-2.5 font-semibold text-xs tracking-wide"
            disabled={busy || !files.length}
          >
            {busy ? (
              <>
                <Loader2 className="animate-spin" size={15} />
                <span>Queueing Batch Pipeline…</span>
              </>
            ) : (
              <>
                <Play size={15} />
                <span>
                  Inspect Batch Queue ({files.length} Image{files.length === 1 ? "" : "s"})
                </span>
              </>
            )}
          </button>
        </Card>

        {/* Multi-Image File Dropzone */}
        <Card className="space-y-3">
          <div className="border-b border-white/10 pb-2 flex items-center justify-between">
            <span className="text-xs font-mono font-bold tracking-wider text-white uppercase flex items-center gap-1.5">
              <UploadCloud size={14} className="text-sky-400" />
              2. Batch Image Queue
            </span>
            <span className="text-[10px] font-mono text-slate-400">Up to 200 files</span>
          </div>

          <div
            {...dz.getRootProps()}
            className="flex min-h-[160px] cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-white/15 bg-ink-950/40 p-4 text-center hover:border-sky-400/50 hover:bg-white/[0.02] transition"
          >
            <input {...dz.getInputProps()} aria-label="Batch image files" />
            <UploadCloud className="text-sky-400" size={32} />
            <span className="text-xs font-medium text-slate-200">
              Drag multiple inspection images here, or click to browse
            </span>
            <span className="text-[10px] font-mono text-slate-500">
              JPG, PNG, or WEBP · max 15MB each
            </span>
          </div>

          {files.length > 0 && (
            <div className="flex items-center justify-between text-xs font-mono border-t border-white/5 pt-2 text-slate-300">
              <span>{files.length} image files queued for upload</span>
              <button
                type="button"
                className="text-rose-400 hover:text-rose-300 hover:underline"
                onClick={() => setFiles([])}
              >
                Clear Queue
              </button>
            </div>
          )}
        </Card>
      </form>

      {/* Active Batch Progress Monitor */}
      {b && (
        <Card className="mt-5 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 pb-3">
            <div>
              <div className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-sky-400" />
                <h2 className="text-sm font-mono font-bold text-white uppercase tracking-wider">
                  Batch Execution #{b.id}: {b.batch_code}
                </h2>
                <span className="text-xs font-normal text-slate-400">({b.product_name})</span>
              </div>
              <p className="text-[11px] font-mono text-slate-400 mt-0.5">
                {b.job_counts.DONE} of {b.total} complete · {b.job_counts.FAILED} failed ·{" "}
                {b.job_counts.QUEUED + b.job_counts.PROCESSING} in progress
              </p>
            </div>

            {/* Batch Report Export Actions */}
            <div className="flex flex-wrap gap-2">
              {b.job_counts.FAILED > 0 && (
                <button className="btn-ghost !px-2.5 !py-1 text-xs" onClick={retry}>
                  <RefreshCw size={13} />
                  Retry Failed ({b.job_counts.FAILED})
                </button>
              )}
              <button
                className="btn-ghost !px-2.5 !py-1 text-xs"
                onClick={() => download(`/api/batches/${b.id}/export/csv`, `batch-${b.id}.csv`)}
              >
                <FileDown size={13} />
                Export CSV
              </button>
              <button
                className="btn-primary !px-2.5 !py-1 text-xs"
                onClick={() => download(`/api/batches/${b.id}/report`, `batch-${b.id}.pdf`)}
              >
                <FileDown size={13} />
                PDF Quality Certificate
              </button>
            </div>
          </div>

          {/* Progress Bar */}
          <div
            className="h-2.5 overflow-hidden rounded bg-slate-800 border border-white/5"
            role="progressbar"
            aria-valuenow={Math.round(b.progress * 100)}
            aria-valuemin={0}
            aria-valuemax={100}
          >
            <div
              className="h-full bg-sky-500 transition-all duration-300"
              style={{ width: `${b.progress * 100}%` }}
            />
          </div>

          {/* Yield Metrics Bar & Table Filter */}
          <div className="flex flex-wrap items-center justify-between gap-3 text-xs font-mono border-y border-white/5 py-2">
            <div className="flex items-center gap-4">
              <span className="text-pass font-semibold flex items-center gap-1">
                <CheckCircle2 size={13} /> PASS: {b.counts.PASS}
              </span>
              <span className="text-review font-semibold flex items-center gap-1">
                REVIEW: {b.counts.REVIEW}
              </span>
              <span className="text-fail font-semibold flex items-center gap-1">
                <XCircle size={13} /> FAIL: {b.counts.FAIL}
              </span>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-slate-400">Filter Decision:</span>
              <select
                aria-label="Filter decision"
                className="input !w-36 !py-0.5 font-mono text-xs"
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
              >
                <option value="">All Decisions</option>
                <option value="PASS">PASS Only</option>
                <option value="REVIEW">REVIEW Only</option>
                <option value="FAIL">FAIL Only</option>
              </select>
            </div>
          </div>

          {/* Granular Batch Items Table */}
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr>
                  <th className="th">File Name</th>
                  <th className="th">Pipeline Status</th>
                  <th className="th">Decision</th>
                  <th className="th">Anomaly Score</th>
                  <th className="th">Defect Class</th>
                  <th className="th text-right">Details</th>
                </tr>
              </thead>
              <tbody>
                {b.jobs
                  .filter((j) => !filter || (j.inspection_id && byInsp.has(j.inspection_id)))
                  .map((j) => {
                    const i = j.inspection_id ? byInsp.get(j.inspection_id) : undefined;
                    return (
                      <tr key={j.id} className="border-t border-white/5 hover:bg-white/[0.02]">
                        <td className="td font-mono text-xs max-w-[200px] truncate text-slate-200">
                          {j.filename}
                        </td>
                        <td className="td">
                          <span
                            className={`px-1.5 py-0.5 rounded text-[10px] font-mono border ${
                              STATUS_BADGE[j.status]
                            }`}
                          >
                            {j.status}
                          </span>
                          {j.error && (
                            <div className="text-[10px] font-mono text-fail mt-0.5">{j.error}</div>
                          )}
                        </td>
                        <td className="td">{i ? <DecisionBadge d={i.decision} /> : "—"}</td>
                        <td className="td font-mono">{i ? fmtScore(i.score) : "—"}</td>
                        <td className="td font-mono">{i ? title(i.defect_class) : "—"}</td>
                        <td className="td text-right">
                          {i && (
                            <Link
                              className="btn-ghost !px-2 !py-0.5 !text-[11px] font-mono text-sky-400 hover:text-white"
                              to={`/history/${i.id}`}
                            >
                              Inspect →
                            </Link>
                          )}
                        </td>
                      </tr>
                    );
                  })}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Previous Batches Ledger */}
      <Card className="mt-5">
        <h3 className="mb-2 text-xs font-mono font-bold tracking-wider text-white uppercase">
          Previous Batch Runs
        </h3>
        {!past.data?.length ? (
          <Empty title="No archived batches" />
        ) : (
          <div className="flex flex-wrap gap-2">
            {past.data.map((p) => (
              <button
                key={p.id}
                className={`btn-ghost !px-3 !py-1 text-xs font-mono ${
                  batchId === p.id ? "bg-sky-500/20 text-sky-300 border-sky-400" : ""
                }`}
                onClick={() => setBatchId(p.id)}
              >
                <span>{p.batch_code}</span>
                <span className="text-[10px] text-slate-400 ml-1.5">
                  ({p.job_counts.DONE}/{p.total})
                </span>
              </button>
            ))}
          </div>
        )}
      </Card>
    </>
  );
}
