import {
  Camera as CamIcon,
  CameraOff,
  CheckCircle2,
  Clock,
  Crosshair,
  Gauge,
  Loader2,
  Play,
  RotateCcw,
  ScanSearch,
  Sliders,
  Square,
  Zap,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import Webcam from "react-webcam";
import toast from "react-hot-toast";
import { ProductSelect } from "../components/Selectors";
import { ResultView } from "../components/ResultView";
import { Card, DecisionBadge, ModeBadge, PageHeader } from "../components/ui";
import { useMode } from "../contexts/ModeContext";
import { Api, errMsg } from "../services/api";
import type { Inspection } from "../types";
import { fmtScore } from "../utils/format";

export default function Camera() {
  const { mode } = useMode();
  const cam = useRef<Webcam>(null);
  const [on, setOn] = useState(false);
  const [err, setErr] = useState("");
  const [pid, setPid] = useState<number | "">("");
  const [frame, setFrame] = useState<string | null>(null);
  const [auto, setAuto] = useState(false);
  const [interval, setIntervalS] = useState(5);
  const [result, setResult] = useState<Inspection | null>(null);
  const [history, setHistory] = useState<Inspection[]>([]);
  const [stats, setStats] = useState({ done: 0, skipped: 0, totalMs: 0, startedAt: 0 });
  const busy = useRef(false);
  const [, force] = useState(0);

  const supported = typeof navigator !== "undefined" && !!navigator.mediaDevices?.getUserMedia;

  const submit = useCallback(
    async (dataUrl: string) => {
      if (!pid) return toast.error("Select target product first");
      if (busy.current) {
        setStats((s) => ({ ...s, skipped: s.skipped + 1 }));
        return;
      }
      busy.current = true;
      force((n) => n + 1);
      const t0 = performance.now();
      try {
        const blob = await (await fetch(dataUrl)).blob();
        const fd = new FormData();
        fd.append("file", new File([blob], "camera_capture.jpg", { type: "image/jpeg" }));
        fd.append("product_id", String(pid));
        fd.append("mode", "real");
        fd.append("notes", "Optical sensor live camera capture");
        const r = await Api.inspect(fd);
        setResult(r);
        setHistory((h) => [r, ...h].slice(0, 8));
        setStats((s) => ({
          ...s,
          done: s.done + 1,
          totalMs: s.totalMs + (performance.now() - t0),
          startedAt: s.startedAt || Date.now(),
        }));
      } catch (e) {
        toast.error(errMsg(e));
        setAuto(false);
      } finally {
        busy.current = false;
        force((n) => n + 1);
      }
    },
    [pid]
  );

  const capture = () => {
    const s = cam.current?.getScreenshot();
    if (s) {
      setFrame(s);
      toast.success("Frame buffer acquired");
    } else {
      toast.error("Could not capture frame buffer from camera");
    }
  };

  useEffect(() => {
    if (!auto || !on) return;
    const id = window.setInterval(() => {
      const s = cam.current?.getScreenshot();
      if (s) {
        setFrame(s);
        submit(s);
      }
    }, Math.max(2, interval) * 1000);
    return () => window.clearInterval(id);
  }, [auto, on, interval, submit]);

  const avg = stats.done ? stats.totalMs / stats.done : 0;
  const perMin =
    stats.done > 1 ? stats.done / ((Date.now() - stats.startedAt) / 60000 + avg / 60000) : 0;

  return (
    <>
      <PageHeader
        title="Live Camera Workstation"
        subtitle="Real-time optical frame acquisition, automated sensor triggering, and genuine PatchCore ONNX inspection."
        actions={
          <div className="flex items-center gap-2">
            <ModeBadge mode="real" simulated={false} />
            <span
              className={`px-2 py-0.5 rounded text-xs font-mono border ${
                on ? "border-pass/30 bg-pass/10 text-pass" : "border-slate-700 bg-slate-800 text-slate-400"
              }`}
            >
              {on ? "CAMERA STREAM ACTIVE" : "SENSOR STANDBY"}
            </span>
          </div>
        }
      />

      {/* Main 2-Panel Camera Station */}
      <div className="grid gap-4 lg:grid-cols-12 items-start">
        {/* Left: Live Camera Viewport & Stream Control */}
        <Card className="lg:col-span-7 space-y-3">
          <div className="flex items-center justify-between border-b border-white/10 pb-2">
            <span className="text-xs font-mono font-bold tracking-wider text-white uppercase flex items-center gap-1.5">
              <Crosshair size={14} className="text-sky-400" />
              Live Optical Viewfinder
            </span>
            <span className="text-[10px] font-mono text-slate-400">
              {on ? "ENVIRONMENT OPTICAL SENSOR" : "CAMERA DISCONNECTED"}
            </span>
          </div>

          {/* Camera Frame Viewport */}
          <div className="relative flex aspect-video items-center justify-center overflow-hidden rounded-lg border border-white/10 bg-[#050811] inspection-reticle">
            {on ? (
              <Webcam
                ref={cam}
                audio={false}
                screenshotFormat="image/jpeg"
                screenshotQuality={0.92}
                className="h-full w-full object-cover"
                videoConstraints={{ facingMode: "environment" }}
                onUserMediaError={(e) => {
                  setOn(false);
                  setAuto(false);
                  setErr(
                    String(
                      (e as any)?.name === "NotAllowedError"
                        ? "Camera permission denied by browser. Grant access in browser URL bar."
                        : "No compatible optical camera device detected."
                    )
                  );
                }}
              />
            ) : (
              <div className="p-8 text-center text-xs font-mono text-slate-500">
                <CameraOff className="mx-auto mb-2 text-slate-600" size={28} />
                <span>Optical Camera Stream Inactive</span>
                <p className="text-[10px] text-slate-600 mt-1">
                  Click &apos;Start Camera Stream&apos; below to activate live sensor feed.
                </p>
              </div>
            )}

            {/* Live Crosshair Center Target */}
            {on && (
              <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
                <div className="h-28 w-28 border border-sky-400/50 rounded-lg flex items-center justify-center">
                  <div className="h-2 w-2 rounded-full bg-sky-400 animate-pulse" />
                </div>
              </div>
            )}
          </div>

          {!supported && (
            <p role="alert" className="text-xs font-mono text-fail">
              getUserMedia not supported in this browser context (requires HTTPS or localhost).
            </p>
          )}
          {err && (
            <p role="alert" className="text-xs font-mono text-fail">
              {err}
            </p>
          )}

          {/* Camera Control Action Buttons */}
          <div className="flex flex-wrap gap-2 pt-1 border-t border-white/5">
            {!on ? (
              <button
                className="btn-primary !px-3"
                disabled={!supported}
                onClick={() => {
                  setErr("");
                  setOn(true);
                }}
              >
                <CamIcon size={14} />
                Start Camera Stream
              </button>
            ) : (
              <button
                className="btn-danger !px-3"
                onClick={() => {
                  setOn(false);
                  setAuto(false);
                }}
              >
                <Square size={14} />
                Stop Stream
              </button>
            )}

            <button className="btn-ghost !px-3" disabled={!on} onClick={capture}>
              Grab Frame Buffer
            </button>

            <button
              className="btn-primary !px-3"
              disabled={!frame || !pid || busy.current}
              onClick={() => frame && submit(frame)}
            >
              {busy.current ? <Loader2 className="animate-spin" size={14} /> : <Zap size={14} />}
              Inspect Captured Frame
            </button>
          </div>

          {/* Target Product Selection */}
          <div className="pt-2">
            <div>
              <label className="label">Target Product Type</label>
              <ProductSelect value={pid} onChange={setPid} />
            </div>
          </div>

          {/* Timed Conveyor Line Automation */}
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-white/10 bg-ink-950/60 p-2.5">
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="auto-capture"
                checked={auto}
                disabled={!on || !pid}
                onChange={(e) => setAuto(e.target.checked)}
                className="rounded border-slate-700 bg-slate-800 text-sky-500 focus:ring-sky-500"
              />
              <label
                htmlFor="auto-capture"
                className="text-xs font-mono text-slate-200 cursor-pointer"
              >
                Simulated Conveyor Line (Auto-trigger every)
              </label>
              <input
                aria-label="Interval seconds"
                type="number"
                min={2}
                max={120}
                className="input !w-16 !py-0.5 text-center font-mono"
                value={interval}
                onChange={(e) => setIntervalS(Number(e.target.value))}
              />
              <span className="text-xs font-mono text-slate-400">sec</span>
            </div>

            {auto && (
              <span className="flex items-center gap-1.5 text-xs font-mono text-pass">
                <span className="h-2 w-2 rounded-full bg-pass animate-ping" />
                CONVEYOR TRIGGER RUNNING
              </span>
            )}
          </div>
        </Card>

        {/* Right: Captured Frame Buffer & Performance Telemetry */}
        <Card className="lg:col-span-5 space-y-4">
          <div>
            <div className="flex items-center justify-between border-b border-white/10 pb-2 mb-2">
              <span className="text-xs font-mono font-bold tracking-wider text-white uppercase">
                Acquired Frame Buffer
              </span>
              <span className="text-[10px] font-mono text-slate-400">
                {frame ? "BUFFER ACTIVE" : "EMPTY"}
              </span>
            </div>

            <div className="min-h-[140px] rounded-lg border border-white/10 bg-[#050811] flex items-center justify-center p-2">
              {frame ? (
                <img
                  src={frame}
                  alt="Captured frame"
                  className="max-h-44 w-auto rounded object-contain border border-white/10"
                />
              ) : (
                <span className="text-xs font-mono text-slate-500">
                  No frame buffer captured yet.
                </span>
              )}
            </div>
          </div>

          {/* Sensor Throughput & Latency Metrics */}
          <div>
            <h4 className="text-xs font-mono font-bold tracking-wider text-white uppercase mb-2">
              Station Telemetry & Throughput
            </h4>
            <div className="grid grid-cols-3 gap-2 text-center">
              <div className="rounded border border-white/10 bg-ink-950/60 p-2.5">
                <div className="text-xl font-bold font-mono text-white">{stats.done}</div>
                <div className="text-[10px] uppercase font-mono text-slate-400">Units Tested</div>
              </div>
              <div className="rounded border border-white/10 bg-ink-950/60 p-2.5">
                <div className="text-xl font-bold font-mono text-sky-400">
                  {stats.done ? `${avg.toFixed(0)} ms` : "—"}
                </div>
                <div className="text-[10px] uppercase font-mono text-slate-400">Avg Round Trip</div>
              </div>
              <div className="rounded border border-white/10 bg-ink-950/60 p-2.5">
                <div className="text-xl font-bold font-mono text-emerald-400">
                  {perMin ? perMin.toFixed(1) : "—"}
                </div>
                <div className="text-[10px] uppercase font-mono text-slate-400">Units / Min</div>
              </div>
            </div>
            {stats.skipped > 0 && (
              <p className="mt-2 text-[11px] font-mono text-amber-400">
                ⚠️ {stats.skipped} frame(s) skipped to prevent queue overflow while pipeline was in-flight.
              </p>
            )}
          </div>

          {/* Session History Stream */}
          {history.length > 0 && (
            <div>
              <h4 className="text-xs font-mono font-bold tracking-wider text-slate-400 uppercase mb-1.5">
                Recent Camera Frames
              </h4>
              <div className="flex flex-wrap gap-1.5">
                {history.map((h) => (
                  <span
                    key={h.id}
                    className="flex items-center gap-1.5 rounded border border-white/10 bg-ink-950/80 px-2 py-1 text-xs font-mono"
                  >
                    <span>#{h.id}</span>
                    <DecisionBadge d={h.decision} />
                    <span className="text-slate-400">{fmtScore(h.score)}</span>
                  </span>
                ))}
              </div>
            </div>
          )}
        </Card>
      </div>

      {/* Result Diagnostics */}
      {result && (
        <div className="mt-5">
          <ResultView insp={result} />
        </div>
      )}
    </>
  );
}
