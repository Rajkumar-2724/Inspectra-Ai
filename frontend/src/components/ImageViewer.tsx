import {
  Circle,
  Columns2,
  Crosshair,
  Download,
  Eye,
  Layers,
  Maximize2,
  Minus,
  Plus,
  RotateCcw,
  Sliders,
  Square,
} from "lucide-react";
import { useState } from "react";
import { useAuthImage } from "../hooks/useAuthImage";
import { download } from "../services/api";
import type { Inspection } from "../types";
import { Segmented } from "./ui";

const LABELS: Record<string, string> = {
  original: "Original",
  processed: "Processed",
  heatmap: "Heatmap",
  overlay: "Overlay",
  annotated: "Ellipses & Badges",
  reference_patch: "Reference",
};

export function ImageViewer({ insp }: { insp: Inspection }) {
  const [kind, setKind] = useState("overlay");
  const [zoom, setZoom] = useState(1);
  const [sideBySide, setSideBySide] = useState(false);
  const [showAnnotations, setShowAnnotations] = useState(true);
  const [showBoxes, setShowBoxes] = useState(false);
  const [showReticle, setShowReticle] = useState(false);
  const [heatmapOpacity, setHeatmapOpacity] = useState(70);

  // Images for single view & comparison
  const { url: currentUrl, missing: currentMissing } = useAuthImage(insp.id, kind);
  const { url: origUrl } = useAuthImage(insp.id, "original", sideBySide || kind === "overlay");
  const { url: heatmapUrl } = useAuthImage(insp.id, "heatmap", kind === "overlay");

  const availableKinds = ["original", "processed", "heatmap", "overlay", "annotated", "reference_patch"].filter(
    (k) => insp.images.includes(k)
  );

  // Compute exact coordinate space for SVG overlays from processed image dimensions
  const procSize: [number, number] = (insp.explanation?.preprocessing?.processed_size as [number, number]) || [
    insp.image_width || 640,
    insp.image_height || 640,
  ];
  const vbW = procSize[0];
  const vbH = procSize[1];

  const regions = insp.defects;
  const isUncalibrated = insp.explanation?.localization_status === "uncalibrated";

  return (
    <div className="flex flex-col gap-2.5">
      {/* Top Workstation Viewport Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/10 pb-2.5">
        <div className="flex flex-wrap items-center gap-2">
          {/* Layer Selector */}
          <Segmented
            value={kind}
            onChange={(k) => {
              setKind(k);
              if (sideBySide && k === "original") setSideBySide(false);
            }}
            options={availableKinds.map((k) => ({ value: k, label: LABELS[k] }))}
          />

          {/* Side-by-Side Comparison Toggle */}
          <button
            type="button"
            onClick={() => setSideBySide(!sideBySide)}
            className={`btn-ghost !px-2.5 !py-1 text-xs flex items-center gap-1.5 ${
              sideBySide ? "bg-sky-500/20 text-sky-300 border-sky-400/40" : ""
            }`}
            title="Toggle side-by-side comparison with original acquisition"
          >
            <Columns2 size={13} />
            <span className="hidden sm:inline">Side-by-Side</span>
          </button>

          {/* Ellipse / Circle Annotations Toggle */}
          {regions.length > 0 && (
            <button
              type="button"
              onClick={() => setShowAnnotations(!showAnnotations)}
              className={`btn-ghost !px-2.5 !py-1 text-xs flex items-center gap-1.5 ${
                showAnnotations ? "bg-cyan-500/25 text-cyan-300 border-cyan-400/50" : ""
              }`}
              title="Toggle tight ellipse/circle defect highlights"
            >
              <Circle size={13} />
              <span className="hidden sm:inline">Defect Circles ({regions.length})</span>
            </button>
          )}

          {/* Optional Bounding Boxes Toggle */}
          {regions.length > 0 && (
            <button
              type="button"
              onClick={() => setShowBoxes(!showBoxes)}
              className={`btn-ghost !px-2.5 !py-1 text-xs flex items-center gap-1.5 ${
                showBoxes ? "bg-slate-700 text-slate-200 border-slate-500" : ""
              }`}
              title="Toggle bounding box outlines"
            >
              <Square size={12} />
              <span className="hidden sm:inline">Boxes</span>
            </button>
          )}

          {/* Reticle Toggle */}
          <button
            type="button"
            onClick={() => setShowReticle(!showReticle)}
            className={`btn-ghost !p-1.5 ${showReticle ? "bg-sky-500/20 text-sky-300 border-sky-400/40" : ""}`}
            title="Toggle alignment reticle"
          >
            <Crosshair size={13} />
          </button>
        </div>

        {/* Zoom & Action Controls */}
        <div className="flex items-center gap-1.5">
          {/* Heatmap Opacity Slider (when overlay or heatmap is active) */}
          {(kind === "overlay" || kind === "heatmap") && (
            <div className="hidden sm:flex items-center gap-1.5 px-2 py-0.5 rounded border border-white/10 bg-ink-950/60 text-xs text-slate-300">
              <Sliders size={12} className="text-slate-400" />
              <span className="text-[10px] uppercase font-mono text-slate-400">Opacity</span>
              <input
                type="range"
                min="10"
                max="100"
                value={heatmapOpacity}
                onChange={(e) => setHeatmapOpacity(Number(e.target.value))}
                className="w-16 h-1 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-sky-400"
                title={`Heatmap blend opacity: ${heatmapOpacity}%`}
              />
              <span className="text-[10px] font-mono w-7 text-right">{heatmapOpacity}%</span>
            </div>
          )}

          <div className="flex items-center gap-0.5 rounded border border-white/10 bg-ink-950/80 p-0.5">
            <button
              className="btn-ghost !p-1 !border-0"
              aria-label="Zoom out"
              onClick={() => setZoom((z) => Math.max(0.5, +(z - 0.25).toFixed(2)))}
            >
              <Minus size={13} />
            </button>
            <span className="w-11 text-center font-mono text-[11px] text-slate-300 font-semibold">
              {Math.round(zoom * 100)}%
            </span>
            <button
              className="btn-ghost !p-1 !border-0"
              aria-label="Zoom in"
              onClick={() => setZoom((z) => Math.min(4, +(z + 0.25).toFixed(2)))}
            >
              <Plus size={13} />
            </button>
            <button
              className="btn-ghost !p-1 !border-0"
              aria-label="Reset zoom"
              title="Reset to 100%"
              onClick={() => setZoom(1)}
            >
              <RotateCcw size={12} />
            </button>
          </div>

          <button
            className="btn-ghost !p-1.5"
            aria-label="Download this image"
            title="Download current image view"
            onClick={() =>
              download(`/api/inspections/${insp.id}/images/${kind}`, `inspection-${insp.id}-${kind}.png`, {
                download: true,
              })
            }
          >
            <Download size={13} />
          </button>
        </div>
      </div>

      {/* Primary Inspection Workstation Canvas Viewport */}
      <div
        className={`relative h-[380px] sm:h-[460px] overflow-auto rounded-lg border border-white/10 bg-[#050811] ${
          showReticle ? "inspection-reticle" : ""
        }`}
        data-testid="image-viewer"
      >
        {/* Inspection Telemetry Watermark */}
        <div className="pointer-events-none absolute left-3 top-3 z-20 flex flex-wrap items-center gap-2">
          {insp.simulated && (
            <span className="rounded border border-amber-500/40 bg-amber-500/20 px-2 py-0.5 text-[10px] font-mono font-bold text-amber-300 shadow-sm">
              SIMULATED TEST PATTERN
            </span>
          )}
          <span className="rounded bg-black/60 px-2 py-0.5 text-[10px] font-mono text-slate-300 border border-white/10">
            ID #{insp.id} · {sideBySide ? "COMPARISON: RAW vs DEFECT MAP" : LABELS[kind].toUpperCase()}
          </span>
          {isUncalibrated && (
            <span className="rounded border border-amber-400/40 bg-amber-500/15 px-2 py-0.5 text-[10px] font-mono text-amber-300">
              LOCALIZATION: UNCALIBRATED
            </span>
          )}
        </div>

        {currentMissing ? (
          <div className="flex h-full items-center justify-center text-xs font-mono text-slate-500">
            View channel &apos;{kind}&apos; not available for this record.
          </div>
        ) : !currentUrl ? (
          <div className="flex h-full items-center justify-center text-xs font-mono text-slate-500">
            Fetching optical inspection stream…
          </div>
        ) : sideBySide ? (
          /* Side-by-Side Dual Viewport */
          <div className="grid grid-cols-2 h-full divide-x divide-white/10">
            {/* Left: Original Acquisition */}
            <div className="relative overflow-auto p-2 flex flex-col items-center justify-center bg-black/30">
              <span className="absolute top-2 left-2 z-10 rounded bg-slate-900/80 border border-white/10 px-1.5 py-0.5 text-[10px] font-mono text-slate-300">
                1. RAW OPTICAL ACQUISITION
              </span>
              {origUrl ? (
                <img
                  src={origUrl}
                  alt={`Raw acquisition of inspection ${insp.id}`}
                  style={{ width: `${zoom * 100}%`, maxWidth: "none" }}
                  className="block rounded object-contain"
                />
              ) : (
                <span className="text-xs text-slate-500">Loading original…</span>
              )}
            </div>

            {/* Right: Inspection / Anomaly View */}
            <div className="relative overflow-auto p-2 flex flex-col items-center justify-center bg-black/30">
              <span className="absolute top-2 left-2 z-10 rounded bg-slate-900/80 border border-white/10 px-1.5 py-0.5 text-[10px] font-mono text-cyan-300">
                2. ANOMALY / DEFECT HIGHLIGHTS
              </span>
              <div className="relative inline-block" style={{ width: `${zoom * 100}%`, maxWidth: "none" }}>
                <img
                  src={currentUrl}
                  alt={`${LABELS[kind]} view of inspection ${insp.id}`}
                  className="block w-full rounded object-contain"
                />

                {/* Defect Circle / Ellipse Overlay */}
                {showAnnotations && regions.length > 0 && (
                  <svg
                    className="pointer-events-none absolute inset-0 h-full w-full"
                    viewBox={`0 0 ${vbW} ${vbH}`}
                    preserveAspectRatio="none"
                  >
                    {regions.map((d, idx) => {
                      const shape = d.shape || "ellipse";
                      const cx = d.center_x ?? (d.x + d.w / 2);
                      const cy = d.center_y ?? (d.y + d.h / 2);
                      const rx = Math.max(d.radius_x ?? (d.w / 2), 6);
                      const ry = Math.max(d.radius_y ?? (d.h / 2), 6);
                      const angle = d.angle || 0;
                      const regId = d.region_id || (idx + 1);
                      const labelText =
                        d.label === "unclassified_anomaly"
                          ? "Unclassified anomaly"
                          : (d.label || "Anomaly").replace(/_/g, " ");

                      return (
                        <g key={d.id || idx}>
                          {showBoxes && (
                            <rect
                              x={d.x}
                              y={d.y}
                              width={d.w}
                              height={d.h}
                              fill="none"
                              stroke="rgba(0, 229, 255, 0.4)"
                              strokeWidth="1"
                              strokeDasharray="3 2"
                            />
                          )}

                          {shape === "circle" || Math.abs(rx - ry) < 2 ? (
                            <circle
                              cx={cx}
                              cy={cy}
                              r={Math.max(rx, ry)}
                              fill="rgba(0, 229, 255, 0.12)"
                              stroke="#00e5ff"
                              strokeWidth="2.5"
                              strokeDasharray={isUncalibrated ? "5 3" : undefined}
                            />
                          ) : (
                            <ellipse
                              cx={cx}
                              cy={cy}
                              rx={rx}
                              ry={ry}
                              transform={angle ? `rotate(${angle} ${cx} ${cy})` : undefined}
                              fill="rgba(0, 229, 255, 0.12)"
                              stroke="#00e5ff"
                              strokeWidth="2.5"
                              strokeDasharray={isUncalibrated ? "5 3" : undefined}
                            />
                          )}

                          {/* Number Badge & Label Tag */}
                          <g transform={`translate(${cx}, ${Math.max(16, cy - ry - 6)})`}>
                            <rect
                              x={-Math.min(95, (labelText.length * 5.5 + 24) / 2)}
                              y={-14}
                              width={Math.min(190, labelText.length * 6 + 28)}
                              height={16}
                              rx={4}
                              fill="rgba(11, 19, 36, 0.94)"
                              stroke="#00e5ff"
                              strokeWidth="1"
                            />
                            <text
                              x={0}
                              y={-3}
                              textAnchor="middle"
                              fill="#e0f2fe"
                              fontSize="9"
                              fontWeight="bold"
                              fontFamily="monospace"
                            >
                              #{regId} {labelText}
                            </text>
                          </g>
                        </g>
                      );
                    })}
                  </svg>
                )}
              </div>
            </div>
          </div>
        ) : (
          /* Single Viewport with Layer Blend and SVG Annotations */
          <div className="flex h-full items-center justify-center p-3">
            <div className="relative inline-block" style={{ width: `${zoom * 100}%`, maxWidth: "none" }}>
              {/* If overlay kind: support layered opacity blend */}
              {kind === "overlay" && origUrl && (
                <img
                  src={origUrl}
                  alt={`Base original for inspection ${insp.id}`}
                  className="block w-full rounded object-contain"
                />
              )}

              {/* Top layer image */}
              <img
                src={currentUrl}
                alt={`${LABELS[kind]} view of inspection ${insp.id}`}
                style={
                  kind === "overlay"
                    ? {
                        position: "absolute",
                        top: 0,
                        left: 0,
                        width: "100%",
                        height: "100%",
                        opacity: heatmapOpacity / 100,
                      }
                    : {}
                }
                className="block w-full rounded object-contain"
              />

              {/* Defect Circle / Ellipse Annotation Layer */}
              {showAnnotations && regions.length > 0 && (
                <svg
                  className="pointer-events-none absolute inset-0 h-full w-full"
                  viewBox={`0 0 ${vbW} ${vbH}`}
                  preserveAspectRatio="none"
                >
                  {regions.map((d, idx) => {
                    const shape = d.shape || "ellipse";
                    const cx = d.center_x ?? (d.x + d.w / 2);
                    const cy = d.center_y ?? (d.y + d.h / 2);
                    const rx = Math.max(d.radius_x ?? (d.w / 2), 6);
                    const ry = Math.max(d.radius_y ?? (d.h / 2), 6);
                    const angle = d.angle || 0;
                    const regId = d.region_id || (idx + 1);
                    const labelText =
                      d.label === "unclassified_anomaly"
                        ? "Unclassified anomaly"
                        : (d.label || "Anomaly").replace(/_/g, " ");

                    return (
                      <g key={d.id || idx}>
                        {showBoxes && (
                          <rect
                            x={d.x}
                            y={d.y}
                            width={d.w}
                            height={d.h}
                            fill="none"
                            stroke="rgba(0, 229, 255, 0.4)"
                            strokeWidth="1"
                            strokeDasharray="3 2"
                          />
                        )}

                        {shape === "circle" || Math.abs(rx - ry) < 2 ? (
                          <circle
                            cx={cx}
                            cy={cy}
                            r={Math.max(rx, ry)}
                            fill="rgba(0, 229, 255, 0.12)"
                            stroke="#00e5ff"
                            strokeWidth="2.5"
                            strokeDasharray={isUncalibrated ? "5 3" : undefined}
                          />
                        ) : (
                          <ellipse
                            cx={cx}
                            cy={cy}
                            rx={rx}
                            ry={ry}
                            transform={angle ? `rotate(${angle} ${cx} ${cy})` : undefined}
                            fill="rgba(0, 229, 255, 0.12)"
                            stroke="#00e5ff"
                            strokeWidth="2.5"
                            strokeDasharray={isUncalibrated ? "5 3" : undefined}
                          />
                        )}

                        {/* Number Badge & Label Tag */}
                        <g transform={`translate(${cx}, ${Math.max(16, cy - ry - 6)})`}>
                          <rect
                            x={-Math.min(95, (labelText.length * 5.5 + 24) / 2)}
                            y={-14}
                            width={Math.min(190, labelText.length * 6 + 28)}
                            height={16}
                            rx={4}
                            fill="rgba(11, 19, 36, 0.94)"
                            stroke="#00e5ff"
                            strokeWidth="1"
                          />
                          <text
                            x={0}
                            y={-3}
                            textAnchor="middle"
                            fill="#e0f2fe"
                            fontSize="9"
                            fontWeight="bold"
                            fontFamily="monospace"
                          >
                            #{regId} {labelText}
                          </text>
                        </g>
                      </g>
                    );
                  })}
                </svg>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Workstation Viewport Footer Telemetry */}
      <div className="flex flex-wrap items-center justify-between text-[11px] text-slate-400 border-t border-white/5 pt-1.5 font-mono">
        <div className="flex items-center gap-3">
          <span>PIPELINE: {insp.model_version}</span>
          <span>LATENCY: {insp.latency_ms.toFixed(1)}ms</span>
          <span>REGIONS HIGHLIGHTED: {regions.length}</span>
        </div>
        <div className="flex items-center gap-2">
          <span>RESOLUTION: {procSize[0]}×{procSize[1]}</span>
          <span>SHA-256: {insp.image_sha256.slice(0, 12)}…</span>
        </div>
      </div>
    </div>
  );
}
