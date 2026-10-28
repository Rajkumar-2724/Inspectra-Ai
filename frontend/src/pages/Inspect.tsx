import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  CheckCircle2,
  Crosshair,
  FileCheck,
  Gauge,
  Info,
  Layers,
  Loader2,
  Play,
  RotateCcw,
  ScanSearch,
  Sliders,
  UploadCloud,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";
import { useDropzone } from "react-dropzone";
import { Controller, useForm } from "react-hook-form";
import toast from "react-hot-toast";
import { z } from "zod";
import { ProductSelect } from "../components/Selectors";
import { ResultView } from "../components/ResultView";
import { Card, DecisionBadge, FieldError, ModeBadge, PageHeader } from "../components/ui";
import { useMode } from "../contexts/ModeContext";
import { Api, errMsg } from "../services/api";
import type { Inspection } from "../types";

const MAX_MB = 15;
const schema = z.object({
  product_id: z.number({ invalid_type_error: "Select a product" }),
  product_code: z.string().max(64).optional(),
  batch_code: z.string().max(64).optional(),
  line_id: z.string().max(64).optional(),
  notes: z.string().max(2000).optional(),
});
type F = z.infer<typeof schema>;

export default function Inspect() {
  const { mode } = useMode();
  const qc = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<Inspection | null>(null);

  const products = useQuery({ queryKey: ["products"], queryFn: () => Api.products() });

  const {
    control,
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors },
  } = useForm<F>({
    resolver: zodResolver(schema),
    defaultValues: {
      product_code: "",
      batch_code: "",
      line_id: "",
      notes: "",
    },
  });

  const selectedProductId = watch("product_id");
  const selectedProduct = products.data?.find((p) => p.id === selectedProductId);

  // Auto-select first real-ready product if none selected
  useEffect(() => {
    if (!selectedProductId && products.data?.length) {
      const readyProd = products.data.find((p) => p.real_mode_ready) || products.data[0];
      setValue("product_id", readyProd.id);
    }
  }, [products.data, selectedProductId, setValue]);

  useEffect(() => {
    if (!file) {
      setPreview(null);
      return;
    }
    const u = URL.createObjectURL(file);
    setPreview(u);
    return () => URL.revokeObjectURL(u);
  }, [file]);

  const dz = useDropzone({
    accept: { "image/jpeg": [".jpg", ".jpeg"], "image/png": [".png"], "image/webp": [".webp"] },
    multiple: false,
    maxSize: MAX_MB * 1024 * 1024,
    onDropAccepted: (f) => {
      setFile(f[0]);
      setResult(null); // Clear previous result when new image is loaded
    },
    onDropRejected: (r) =>
      toast.error(
        r[0]?.errors[0]?.code === "file-too-large"
          ? `File exceeds ${MAX_MB} MB limit`
          : "Format must be JPG, PNG or WEBP"
      ),
  });

  const submit = async (v: F) => {
    if (!file) return toast.error("Select or drop an optical inspection image first");
    const fd = new FormData();
    fd.append("file", file);
    fd.append("product_id", String(v.product_id));
    fd.append("mode", "real");
    (["product_code", "batch_code", "line_id", "notes"] as const).forEach((k) =>
      fd.append(k, v[k] ?? "")
    );
    setBusy(true);
    try {
      const r = await Api.inspect(fd);
      setResult(r);
      ["stats", "trends", "recent", "pending", "inspections"].forEach((k) =>
        qc.invalidateQueries({ queryKey: [k] })
      );
      toast.success(`Pipeline complete: ${r.decision}`);
    } catch (e) {
      toast.error(errMsg(e), { duration: 7000 });
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <PageHeader
        title="AI Inspection Workstation"
        subtitle="Automated visual anomaly detection, localized heatmaps, defect classification, and threshold telemetry."
        actions={
          <div className="flex items-center gap-2">
            <ModeBadge mode={mode} simulated={mode === "demo"} />
            {result && (
              <button
                type="button"
                className="btn-ghost"
                onClick={() => {
                  setResult(null);
                  setFile(null);
                }}
              >
                <RotateCcw size={13} />
                New Inspection
              </button>
            )}
          </div>
        }
      />

      {/* Main 3-Column Inspection Workstation Layout */}
      <div className="grid gap-4 xl:grid-cols-12 items-start">
        {/* ========================================================================= */}
        {/* LEFT PANEL: Control, Image Acquisition, Batch Settings & Trigger          */}
        {/* ========================================================================= */}
        <form
          onSubmit={handleSubmit(submit)}
          className="xl:col-span-4 space-y-4"
          aria-label="Inspection form"
        >
          {/* Step 1: Image Acquisition Card */}
          <Card className="space-y-3">
            <div className="flex items-center justify-between border-b border-white/10 pb-2">
              <span className="text-xs font-mono font-bold tracking-wider text-white uppercase flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-sky-400" />
                1. Image Acquisition
              </span>
              <span className="text-[10px] font-mono text-slate-400">JPG/PNG/WEBP ≤ 15MB</span>
            </div>

            {/* Dropzone */}
            <div
              {...dz.getRootProps()}
              className={`flex min-h-[140px] cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border border-dashed p-3 text-center transition ${
                dz.isDragActive
                  ? "border-sky-400 bg-sky-500/10"
                  : preview
                  ? "border-sky-500/40 bg-sky-500/5 hover:border-sky-400/60"
                  : "border-white/15 bg-ink-950/40 hover:border-sky-400/50 hover:bg-white/[0.02]"
              }`}
            >
              <input {...dz.getInputProps()} aria-label="Image file" data-testid="file-input" />
              {preview ? (
                <div className="relative group w-full flex flex-col items-center">
                  <div className="relative inline-block">
                    <img
                      src={preview}
                      alt="Selected upload preview"
                      className="max-h-36 rounded border border-white/10 object-contain shadow-sm"
                    />
                    <button
                      type="button"
                      aria-label="Remove image"
                      className="absolute -right-2 -top-2 rounded-full bg-slate-900 border border-white/20 p-1 text-slate-300 hover:text-white hover:bg-rose-900 transition"
                      onClick={(e) => {
                        e.stopPropagation();
                        setFile(null);
                        setResult(null);
                      }}
                    >
                      <X size={12} />
                    </button>
                  </div>
                  <div className="mt-2 text-[11px] font-mono text-slate-400 truncate max-w-full">
                    {file?.name} · {((file?.size || 0) / 1024).toFixed(0)} KB
                  </div>
                </div>
              ) : (
                <>
                  <UploadCloud className="text-sky-400" size={26} />
                  <div className="text-xs font-medium text-slate-200">
                    Drop product image here or click to browse
                  </div>
                  <div className="text-[11px] text-slate-500">
                    Industrial camera capture or raw optical scan
                  </div>
                </>
              )}
            </div>

          </Card>

          {/* Step 2: Target Product & Inspection Parameters Card */}
          <Card className="space-y-3">
            <div className="flex items-center justify-between border-b border-white/10 pb-2">
              <span className="text-xs font-mono font-bold tracking-wider text-white uppercase flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-sky-400" />
                2. Inspection Parameters
              </span>
              {selectedProduct && (
                <span className="text-[10px] font-mono text-slate-400">
                  {selectedProduct.category}
                </span>
              )}
            </div>

            {/* Product selection */}
            <div>
              <label className="label" htmlFor="product">
                Target Product Type
              </label>
              <Controller
                control={control}
                name="product_id"
                render={({ field }) => (
                  <ProductSelect
                    value={field.value ?? ""}
                    onChange={(v) => field.onChange(v === "" ? undefined : v)}
                  />
                )}
              />
              <FieldError msg={errors.product_id?.message} />

              {/* Selected product quality thresholds preview */}
              {selectedProduct && (
                <div className="mt-2 rounded bg-ink-950/60 border border-white/5 p-2 text-[11px] font-mono grid grid-cols-2 gap-2 text-slate-400">
                  <div>
                    Review Threshold:{" "}
                    <span className="text-amber-400 font-bold">
                      {selectedProduct.review_threshold.toFixed(2)}
                    </span>
                  </div>
                  <div>
                    Fail Threshold:{" "}
                    <span className="text-rose-400 font-bold">
                      {selectedProduct.fail_threshold.toFixed(2)}
                    </span>
                  </div>
                  <div className="col-span-2 truncate">
                    Supported Detection:{" "}
                    <span className="text-slate-300">
                      PatchCore Anomaly Detection
                    </span>
                  </div>
                </div>
              )}
            </div>

            {/* Production Metadata Grid */}
            <div className="grid grid-cols-3 gap-2">
              <div>
                <label className="label" htmlFor="pc">
                  Serial ID
                </label>
                <input
                  id="pc"
                  className="input font-mono !text-xs"
                  placeholder="SN-1001"
                  {...register("product_code")}
                />
              </div>
              <div>
                <label className="label" htmlFor="bc">
                  Batch ID
                </label>
                <input
                  id="bc"
                  className="input font-mono !text-xs"
                  placeholder="BATCH-A1"
                  {...register("batch_code")}
                />
              </div>
              <div>
                <label className="label" htmlFor="ln">
                  Line ID
                </label>
                <input
                  id="ln"
                  className="input font-mono !text-xs"
                  placeholder="LINE-01"
                  {...register("line_id")}
                />
              </div>
            </div>

            {/* Operator Notes */}
            <div>
              <label className="label" htmlFor="notes">
                Operator Station Notes
              </label>
              <textarea
                id="notes"
                rows={2}
                className="input !text-xs"
                placeholder="Optional inspection notes, surface condition, lighting adjustments…"
                {...register("notes")}
              />
            </div>

            {/* Start Pipeline Execution Button */}
            <button
              type="submit"
              className="btn-primary w-full !py-2.5 !text-sm font-semibold tracking-wide flex items-center justify-center gap-2"
              disabled={busy || !file}
            >
              {busy ? (
                <>
                  <Loader2 className="animate-spin" size={16} />
                  <span>Executing PatchCore Pipeline…</span>
                </>
              ) : (
                <>
                  <Play size={16} className="fill-white" />
                  <span>
                    Execute Inspection (PatchCore ONNX)
                  </span>
                </>
              )}
            </button>
          </Card>
        </form>

        {/* ========================================================================= */}
        {/* CENTER & RIGHT PANELS: Inspection Workstation / Live Result Telemetry     */}
        {/* ========================================================================= */}
        <div className="xl:col-span-8">
          {result ? (
            /* Result View: Full 2-Panel Center Optical Workstation & Right Telemetry */
            <ResultView insp={result} />
          ) : (
            /* Standby State: Live Viewfinder Preview & Station Readiness Panel */
            <div className="grid gap-4 lg:grid-cols-12">
              {/* Standby Optical Viewfinder */}
              <Card className="lg:col-span-7 xl:col-span-8 flex flex-col justify-between">
                <div className="mb-2 flex items-center justify-between text-xs font-mono text-slate-400 border-b border-white/10 pb-2">
                  <span className="font-semibold text-white tracking-wider uppercase flex items-center gap-1.5">
                    <Crosshair size={14} className="text-sky-400" />
                    Optical Acquisition Viewport
                  </span>
                  <span>{preview ? "FRAME LOADED" : "AWAITING SENSOR INGESTION"}</span>
                </div>

                <div className="relative min-h-[380px] sm:min-h-[440px] flex items-center justify-center rounded-lg border border-white/10 bg-[#050811] p-4 inspection-reticle overflow-hidden">
                  {preview ? (
                    <div className="relative max-h-full flex flex-col items-center">
                      <img
                        src={preview}
                        alt="Acquisition preview"
                        className="max-h-[360px] w-auto rounded object-contain shadow-md"
                      />
                      <div className="absolute top-2 left-2 rounded bg-black/70 border border-white/10 px-2 py-0.5 text-[10px] font-mono text-sky-400">
                        RAW ACQUISITION READY · CLICK EXECUTE INSPECTION
                      </div>
                    </div>
                  ) : (
                    <div className="flex flex-col items-center gap-3 text-center p-6 max-w-sm">
                      <div className="grid h-12 w-12 place-items-center rounded-full bg-sky-500/10 border border-sky-400/30 text-sky-400">
                        <ScanSearch size={24} />
                      </div>
                      <div className="text-sm font-semibold text-white tracking-wide">
                        Optical Sensor Standby
                      </div>
                      <p className="text-xs text-slate-400 leading-relaxed">
                        Drop an image on the left panel or click to upload a high-resolution frame to initiate real PatchCore ONNX visual inspection.
                      </p>
                    </div>
                  )}
                </div>

                <div className="mt-2 flex items-center justify-between text-[11px] font-mono text-slate-500 border-t border-white/5 pt-1.5">
                  <span>STATION: WORKBENCH-01</span>
                  <span>ENGINE: PATCHCORE ONNX (REAL)</span>
                </div>
              </Card>

              {/* Station Readiness & Telemetry Standby Panel */}
              <Card className="lg:col-span-5 xl:col-span-4 flex flex-col justify-between space-y-4">
                <div>
                  <div className="mb-3 border-b border-white/10 pb-2 flex items-center justify-between">
                    <span className="text-xs font-mono font-bold tracking-wider text-white uppercase">
                      Station Telemetry
                    </span>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded border border-pass/40 bg-pass/10 text-pass">
                      STANDBY
                    </span>
                  </div>

                  {/* Quality Checklist */}
                  <div className="space-y-2 text-xs">
                    <div className="text-[10px] font-mono uppercase text-slate-400">
                      Pre-Inspection Verification
                    </div>
                    <div className="space-y-1.5 font-mono text-[11px]">
                      <div className="flex items-center justify-between p-2 rounded bg-ink-950/60 border border-white/5">
                        <span className="text-slate-300">1. Product Config</span>
                        <span className={selectedProduct ? "text-pass" : "text-amber-400"}>
                          {selectedProduct ? "VERIFIED" : "PENDING"}
                        </span>
                      </div>
                      <div className="flex items-center justify-between p-2 rounded bg-ink-950/60 border border-white/5">
                        <span className="text-slate-300">2. Optical Stream</span>
                        <span className={file ? "text-pass" : "text-amber-400"}>
                          {file ? "FRAME LOADED" : "AWAITING IMAGE"}
                        </span>
                      </div>
                      <div className="flex items-center justify-between p-2 rounded bg-ink-950/60 border border-white/5">
                        <span className="text-slate-300">3. Pipeline Engine</span>
                        <span className="text-sky-400">
                          REAL ONNX PATCHCORE
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Thresholds Explanation */}
                  {selectedProduct && (
                    <div className="mt-4 space-y-2 text-xs">
                      <div className="text-[10px] font-mono uppercase text-slate-400">
                        Operational Threshold Ranges (Provisional)
                      </div>
                      <div className="space-y-1.5 text-[11px] font-mono">
                        <div className="flex items-center justify-between p-1.5 rounded border border-pass/30 bg-pass/5 text-pass">
                          <span>PASS ZONE:</span>
                          <span>0.00 → {selectedProduct.review_threshold.toFixed(2)}</span>
                        </div>
                        <div className="flex items-center justify-between p-1.5 rounded border border-review/30 bg-review/5 text-review">
                          <span>REVIEW ZONE:</span>
                          <span>
                            {selectedProduct.review_threshold.toFixed(2)} →{" "}
                            {selectedProduct.fail_threshold.toFixed(2)}
                          </span>
                        </div>
                        <div className="flex items-center justify-between p-1.5 rounded border border-fail/30 bg-fail/5 text-fail">
                          <span>FAIL ZONE:</span>
                          <span>{selectedProduct.fail_threshold.toFixed(2)} → 1.00</span>
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                <div className="rounded border border-white/10 bg-slate-950/60 p-3 text-xs text-slate-400">
                  <div className="flex items-center gap-1.5 text-slate-300 font-semibold mb-1 font-mono text-[11px]">
                    <Info size={13} className="text-sky-400" />
                    Standard Inspection Flow
                  </div>
                  <p className="text-[11px] leading-relaxed">
                    Once executed, the PatchCore ONNX engine performs feature extraction, anomaly map generation, score calculation, morphological bounding-box localization, and provisional quality threshold validation.
                  </p>
                </div>
              </Card>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
