import {
  AlertCircle,
  CheckCircle2,
  Circle,
  Copy,
  ExternalLink,
  FileDown,
  Info,
  Maximize2,
  ShieldCheck,
  X,
  XCircle,
} from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import toast from "react-hot-toast";
import { download } from "../services/api";
import type { Inspection } from "../types";
import { fmtDate, fmtMs, fmtScore, pct, title } from "../utils/format";
import { ImageViewer } from "./ImageViewer";
import { Card, DecisionBadge, ModeBadge, SimBanner } from "./ui";

function ScoreBar({ i }: { i: Inspection }) {
  const c = i.decision === "PASS" ? "#10b981" : i.decision === "REVIEW" ? "#f59e0b" : "#ef4444";
  const pctVal = Math.min(100, Math.max(0, i.score * 100));
  const reviewPct = i.review_threshold * 100;
  const failPct = i.fail_threshold * 100;

  return (
    <div aria-label="Anomaly score against thresholds" className="space-y-1.5">
      {/* 3-Zone Industrial Quality Range Bar */}
      <div className="relative h-3 w-full rounded overflow-hidden bg-slate-800 flex">
        {/* PASS Zone */}
        <div style={{ width: `${reviewPct}%` }} className="bg-emerald-500/30 border-r border-emerald-500/50" />
        {/* REVIEW Zone */}
        <div style={{ width: `${failPct - reviewPct}%` }} className="bg-amber-500/30 border-r border-amber-500/50" />
        {/* FAIL Zone */}
        <div style={{ width: `${100 - failPct}%` }} className="bg-rose-500/30" />

        {/* Current Score Indicator Needle */}
        <div
          className="absolute top-0 bottom-0 w-1.5 -translate-x-1/2 shadow-xs transition-all"
          style={{ left: `${pctVal}%`, backgroundColor: c }}
          title={`Anomaly score: ${i.score.toFixed(3)}`}
        />
      </div>

      {/* Threshold Labels */}
      <div className="flex justify-between text-[10px] font-mono text-slate-400">
        <span className="text-emerald-400">0.0 (PASS)</span>
        <span className="text-amber-400">REV: {i.review_threshold.toFixed(2)}</span>
        <span className="text-rose-400">FAIL: {i.fail_threshold.toFixed(2)}</span>
        <span>1.0</span>
      </div>
      <div className="flex items-center justify-between text-[9px] font-mono text-slate-400 pt-0.5">
        <span className="uppercase tracking-wider text-slate-400">
          Decision Policy: {i.decision}
        </span>
        <span
          className="text-amber-400/90 bg-amber-500/10 border border-amber-500/30 px-1 py-0.2 rounded"
          title="Thresholds are provisional baseline values awaiting validation set ROC calibration"
        >
          Provisional Thresholds
        </span>
      </div>
    </div>
  );
}

const Row = ({ k, v }: { k: string; v: React.ReactNode }) => (
  <div className="flex justify-between items-center gap-3 border-b border-white/5 py-1.5 text-xs">
    <span className="text-slate-400 uppercase tracking-wider text-[11px] font-medium">{k}</span>
    <span className="text-right text-slate-200 font-mono">{v}</span>
  </div>
);

export function ResultView({ insp, compact }: { insp: Inspection; compact?: boolean }) {
  const [copied, setCopied] = useState(false);
  const [previewCrop, setPreviewCrop] = useState<{ src: string; title: string } | null>(null);
  const ref = insp.explanation?.reference_patch;
  const isUncalibrated = insp.explanation?.localization_status === "uncalibrated";
  const locThresh = insp.explanation?.localization_threshold ?? insp.review_threshold;

  const copyHash = () => {
    navigator.clipboard?.writeText(insp.image_sha256);
    setCopied(true);
    toast.success("SHA-256 hash copied");
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-4" data-testid="result-view">
      {insp.simulated && (
        <SimBanner text="SIMULATED RESULT — produced by the deterministic demonstration engine for development/testing. No trained AI model produced this." />
      )}

      {/* Workstation Center & Right Split Grid */}
      <div className="grid gap-4 lg:grid-cols-12">
        {/* Center: Precision Image Viewer */}
        <Card className="lg:col-span-7 xl:col-span-8 flex flex-col justify-between">
          <div className="mb-2 flex items-center justify-between text-xs text-slate-400 font-mono">
            <span className="font-semibold text-white tracking-wider uppercase">Inspection Viewport</span>
            <span>ACQUIRED: {fmtDate(insp.created_at)}</span>
          </div>
          <ImageViewer insp={insp} />
        </Card>

        {/* Right: Telemetry & Decision Diagnostics */}
        <Card className="lg:col-span-5 xl:col-span-4 flex flex-col justify-between">
          <div>
            {/* Decision Header */}
            <div className="mb-3 flex items-center justify-between border-b border-white/10 pb-3">
              <div>
                <div className="text-[10px] font-mono tracking-widest text-slate-400 uppercase">
                  Quality Decision
                </div>
                <div data-testid="decision" className="mt-1">
                  <DecisionBadge d={insp.decision} large />
                </div>
              </div>
              <ModeBadge mode={insp.mode} simulated={insp.simulated} />
            </div>

            {/* Anomaly Score Header */}
            <div className="mb-2">
              <div className="text-[10px] font-mono tracking-widest text-slate-400 uppercase">
                Anomaly Score
              </div>
              <div
                className="text-3xl font-semibold font-mono tracking-tight text-white flex items-baseline gap-2"
                data-testid="score"
              >
                <span>{fmtScore(insp.score)}</span>
                <span className="text-xs font-normal text-slate-400 font-sans">
                  {insp.decision === "PASS"
                    ? "Normal"
                    : insp.decision === "REVIEW"
                    ? "Requires Human Review"
                    : "Defect Threshold Exceeded"}
                </span>
              </div>
            </div>

            {/* Interactive Threshold Bar */}
            <ScoreBar i={insp} />

            {/* Diagnostic Summary */}
            {insp.explanation?.summary && (
              <div className="mt-3 rounded border border-white/10 bg-slate-950/60 p-2.5 text-xs text-slate-300">
                <div className="text-[10px] uppercase font-mono tracking-wider text-slate-400 mb-1">
                  Diagnostic Rationale
                </div>
                <p className="leading-relaxed">{insp.explanation.summary}</p>
              </div>
            )}

            {/* Structured Telemetry Rows */}
            <div className="mt-3">
              <Row
                k="Defect classification"
                v={
                  insp.defect_class === "unclassified_anomaly"
                    ? "Unclassified anomaly"
                    : insp.defect_class
                    ? title(insp.defect_class)
                    : "None (Clear)"
                }
              />
              <Row
                k="Classifier status"
                v={
                  insp.confidence != null ? (
                    pct(insp.confidence)
                  ) : (
                    <span className="text-slate-400 text-[11px]" title="No trained multi-class defect classifier attached to this product">
                      None configured (PatchCore only)
                    </span>
                  )
                }
              />
              <Row
                k="Localization threshold"
                v={
                  <span className="flex items-center gap-1.5">
                    <span>{Number(locThresh).toFixed(3)}</span>
                    <span
                      className={`text-[9px] px-1 py-0.2 rounded font-sans uppercase ${
                        isUncalibrated
                          ? "bg-amber-500/15 text-amber-300 border border-amber-500/30"
                          : "bg-cyan-500/15 text-cyan-300 border border-cyan-500/30"
                      }`}
                    >
                      {isUncalibrated ? "Uncalibrated" : "Provisional"}
                    </span>
                  </span>
                }
              />
              <Row k="Inference latency" v={fmtMs(insp.latency_ms)} />
              <Row k="Active model pipeline" v={insp.model_version} />
              <Row k="Timestamp" v={fmtDate(insp.created_at)} />
              {insp.final_decision && (
                <Row k="Human override decision" v={<DecisionBadge d={insp.final_decision} />} />
              )}
              {insp.review_status === "PENDING" && (
                <Row
                  k="Review status"
                  v={
                    <Link
                      className="text-amber-400 hover:underline flex items-center gap-1 font-semibold"
                      to="/reviews"
                    >
                      Awaiting Human Review →
                    </Link>
                  }
                />
              )}
            </div>
          </div>

          {/* Quick Actions */}
          {!compact && (
            <div className="mt-4 flex flex-wrap gap-2 border-t border-white/10 pt-3">
              <button
                className="btn-primary flex-1"
                onClick={() =>
                  download(`/api/inspections/${insp.id}/report`, `inspection-report-${insp.id}.pdf`)
                }
              >
                <FileDown size={14} />
                PDF Certificate
              </button>
              <Link className="btn-ghost flex-1 text-center" to={`/history/${insp.id}`}>
                Full History Record
              </Link>
            </div>
          )}
        </Card>
      </div>

      {/* Expanded Technical Evidence & Regions */}
      {!compact && (
        <div className="grid gap-4 lg:grid-cols-12">
          {/* Detected Defect Regions with Zoomed Crops */}
          <Card className="lg:col-span-8">
            <div className="mb-3 flex flex-wrap items-center justify-between border-b border-white/10 pb-2.5">
              <div className="flex items-center gap-2">
                <Circle size={14} className="text-cyan-400" />
                <h3 className="text-xs font-semibold tracking-wider text-white uppercase font-mono">
                  Detected Defect Regions ({insp.defects.length})
                </h3>
              </div>
              <div className="flex items-center gap-2 text-[10px] font-mono">
                <span
                  className={`px-1.5 py-0.5 rounded ${
                    isUncalibrated
                      ? "bg-amber-500/15 text-amber-300 border border-amber-500/30"
                      : "bg-cyan-500/15 text-cyan-300 border border-cyan-500/30"
                  }`}
                  title="Pixel-level connected components extracted from PatchCore anomaly distance map"
                >
                  {isUncalibrated ? "UNCAILBRATED LOCALIZATION" : "PROVISIONAL LOCALIZATION"}
                </span>
                <span className="text-slate-400">
                  {insp.image_width && insp.image_height
                    ? `${insp.image_width} × ${insp.image_height} Acquisition`
                    : "Native Coordinates"}
                </span>
              </div>
            </div>

            {insp.defects.length === 0 ? (
              <div className="py-6 px-4 text-center rounded-lg border border-white/5 bg-slate-950/40">
                <p className="text-xs text-slate-300 font-mono mb-1">
                  No suspicious regions exceeded the localization threshold ({Number(locThresh).toFixed(3)}).
                </p>
                <p className="text-[11px] text-slate-500 max-w-md mx-auto">
                  Note: Absence of circled defect regions does not prove the part is defect-free if the global image anomaly score is elevated.
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-white/10 text-[11px] text-slate-400 font-mono">
                      <th className="th !py-2">Region</th>
                      <th className="th !py-2">Zoomed Crop</th>
                      <th className="th !py-2">Defect Label</th>
                      <th className="th !py-2">Shape & Geometry</th>
                      <th className="th !py-2">Bounding Box</th>
                      <th className="th !py-2">Peak Anomaly</th>
                      <th className="th !py-2">Confidence</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5">
                    {insp.defects.map((d, idx) => {
                      const regId = d.region_id || idx + 1;
                      const shape = d.shape || "ellipse";
                      const cx = d.center_x ?? (d.x + d.w / 2);
                      const cy = d.center_y ?? (d.y + d.h / 2);
                      const rx = d.radius_x ?? (d.w / 2);
                      const ry = d.radius_y ?? (d.h / 2);
                      const cropSrc = d.crop_data || `/api/inspections/${insp.id}/images/${d.crop_kind || `crop_${regId}`}`;
                      const isUnclassified = d.label === "unclassified_anomaly";

                      return (
                        <tr key={d.id || idx} className="hover:bg-white/[0.02] transition-colors">
                          {/* Region Number */}
                          <td className="td font-mono font-bold text-cyan-300">
                            <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-cyan-950/70 border border-cyan-400/40 text-xs">
                              #{regId}
                            </span>
                          </td>

                          {/* Zoomed Crop Thumbnail */}
                          <td className="td">
                            <div
                              onClick={() => setPreviewCrop({ src: cropSrc, title: `Region #${regId} Zoomed Crop` })}
                              className="relative group w-12 h-12 rounded overflow-hidden border border-white/20 bg-slate-900 cursor-pointer hover:border-cyan-400 transition-all flex items-center justify-center"
                              title="Click to view high-resolution zoom"
                            >
                              <img
                                src={cropSrc}
                                alt={`Defect region #${regId}`}
                                className="w-full h-full object-cover"
                                onError={(e) => {
                                  // Fallback placeholder if image load fails
                                  (e.target as HTMLImageElement).style.display = "none";
                                }}
                              />
                              <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity">
                                <Maximize2 size={12} className="text-white" />
                              </div>
                            </div>
                          </td>

                          {/* Defect Label */}
                          <td className="td font-medium text-slate-100">
                            {isUnclassified ? (
                              <div className="flex items-center gap-1.5" title="No trained classifier configured for this product. PatchCore flags anomalies based on distance from normal references.">
                                <span className="inline-block px-2 py-0.5 rounded text-[11px] bg-slate-800 border border-slate-700 text-slate-200">
                                  Unclassified anomaly
                                </span>
                                <Info size={12} className="text-slate-400 shrink-0" />
                              </div>
                            ) : (
                              <span className="inline-block px-2 py-0.5 rounded text-[11px] bg-rose-500/20 border border-rose-500/40 text-rose-300">
                                {title(d.label)}
                              </span>
                            )}
                          </td>

                          {/* Geometry & Shape */}
                          <td className="td font-mono text-[11px] text-slate-300">
                            <span className="capitalize font-semibold text-cyan-300">{shape}</span>
                            <div className="text-[10px] text-slate-400">
                              C: ({cx.toFixed(0)}, {cy.toFixed(0)}) · R: {rx.toFixed(0)}×{ry.toFixed(0)}
                              {d.angle ? ` · ∠${d.angle.toFixed(0)}°` : ""}
                            </div>
                          </td>

                          {/* Bounding Box */}
                          <td className="td font-mono text-[11px] text-slate-400">
                            [{d.x}, {d.y}, {d.w}, {d.h}]
                          </td>

                          {/* Peak Anomaly Score */}
                          <td className="td font-mono font-semibold text-slate-100">
                            {d.peak_score.toFixed(3)}
                          </td>

                          {/* Classifier Confidence */}
                          <td className="td font-mono text-slate-400 text-[11px]">
                            {d.confidence != null ? pct(d.confidence) : "n/a (PatchCore)"}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
                <div className="mt-2.5 pt-2 border-t border-white/5 flex items-center gap-2 text-[10px] text-slate-400 font-mono">
                  <Info size={12} className="text-slate-400" />
                  <span>
                    Defect names require a trained multi-class classifier. Without one, all detected regions are reported honestly as &apos;Unclassified anomaly&apos;.
                  </span>
                </div>
              </div>
            )}
          </Card>

          {/* Reference Patch & Cryptographic Evidence */}
          <Card className="lg:col-span-4 flex flex-col justify-between">
            <div>
              <div className="mb-2 flex items-center justify-between border-b border-white/10 pb-2">
                <h3 className="text-xs font-semibold tracking-wider text-white uppercase font-mono flex items-center gap-1.5">
                  <ShieldCheck size={14} className="text-sky-400" />
                  Evidence & Verification
                </h3>
                <span className="text-[10px] text-slate-400 font-mono">SHA-256 Ledger</span>
              </div>

              {/* Nearest reference explanation */}
              <div className="mb-3 text-xs">
                <span className="text-slate-400 font-mono uppercase text-[10px] block mb-0.5">
                  Nearest Nominal Reference
                </span>
                {ref?.available ? (
                  <p className="text-slate-300">
                    Registered reference patch verified.{" "}
                    <span className="text-slate-500 font-mono">({ref.source})</span>
                  </p>
                ) : (
                  <p className="text-slate-400">
                    Unavailable. {ref?.unavailable_reason || "No reference image registered for this product."}
                  </p>
                )}
              </div>

              {/* Cryptographic Image Hash */}
              <div className="rounded border border-white/10 bg-slate-950/70 p-2.5">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[10px] font-mono tracking-wider text-slate-400 uppercase">
                    Image SHA-256 Hash
                  </span>
                  <button
                    type="button"
                    onClick={copyHash}
                    className="text-slate-400 hover:text-sky-400 flex items-center gap-1 text-[10px] font-mono"
                    title="Copy SHA-256 hash"
                  >
                    <Copy size={11} />
                    <span>{copied ? "Copied" : "Copy"}</span>
                  </button>
                </div>
                <p className="break-all font-mono text-[11px] text-sky-300 select-all">
                  {insp.image_sha256}
                </p>
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-white/5 text-[10px] font-mono text-slate-500">
              Artifact Hash: {insp.explanation?.model_artifact_sha256?.slice(0, 16) || "Validated"}…
            </div>
          </Card>
        </div>
      )}

      {/* High-Resolution Zoomed Crop Modal */}
      {previewCrop && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-xs p-4"
          onClick={() => setPreviewCrop(null)}
        >
          <div
            className="relative max-w-sm w-full rounded-xl border border-cyan-500/40 bg-slate-900 p-4 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between pb-3 border-b border-white/10 mb-3">
              <span className="text-xs font-mono font-bold text-white uppercase tracking-wider">
                {previewCrop.title}
              </span>
              <button
                type="button"
                className="btn-ghost !p-1 text-slate-400 hover:text-white"
                onClick={() => setPreviewCrop(null)}
              >
                <X size={14} />
              </button>
            </div>
            <div className="rounded-lg overflow-hidden border border-white/10 bg-black flex items-center justify-center">
              <img
                src={previewCrop.src}
                alt={previewCrop.title}
                className="w-full h-auto object-contain max-h-[320px]"
              />
            </div>
            <div className="mt-3 text-[11px] text-slate-400 font-mono text-center">
              High-resolution contextual crop centered on detected defect coordinates.
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
