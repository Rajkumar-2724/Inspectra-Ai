import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  Cpu,
  FileCheck,
  FileCode,
  Info,
  Layers,
  Plus,
  RefreshCw,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import toast from "react-hot-toast";
import { z } from "zod";
import { Card, Empty, ErrorState, FieldError, Modal, PageHeader, Spinner } from "../components/ui";
import { useAuth } from "../contexts/AuthContext";
import { Api, errMsg } from "../services/api";
import type { ModelVersion } from "../types";
import { fmtDate } from "../utils/format";

const COLOR: Record<ModelVersion["status"], string> = {
  READY: "text-pass border-pass/30 bg-pass/10",
  FILE_MISSING: "text-amber-400 border-amber-500/30 bg-amber-500/10",
  INVALID: "text-fail border-fail/30 bg-fail/10",
  ERROR: "text-fail border-fail/30 bg-fail/10",
  NOT_CONFIGURED: "text-slate-400 border-white/10 bg-white/5",
};

const schema = z.object({
  name: z.string().min(2),
  version: z.string().min(1),
  model_type: z.enum(["patchcore", "classifier"]),
  format: z.enum(["onnx", "torchscript"]),
  file_path: z.string().min(1, "Enter the file path inside models/"),
  product_id: z.string().optional(),
  assign_to_product: z.boolean().optional(),
});
type F = z.infer<typeof schema>;

export default function Models() {
  const { has } = useAuth();
  const qc = useQueryClient();
  const admin = has();
  const [open, setOpen] = useState(false);

  const models = useQuery({ queryKey: ["models"], queryFn: Api.models });
  const status = useQuery({ queryKey: ["models-status"], queryFn: Api.modelsStatus });
  const products = useQuery({ queryKey: ["products"], queryFn: () => Api.products() });

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<F>({
    resolver: zodResolver(schema),
    defaultValues: { model_type: "patchcore", format: "onnx", assign_to_product: true },
  });

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["models"] });
    qc.invalidateQueries({ queryKey: ["models-status"] });
    qc.invalidateQueries({ queryKey: ["products"] });
  };

  const submit = async (v: F) => {
    try {
      const m = await Api.registerModel({
        ...v,
        product_id: v.product_id ? Number(v.product_id) : null,
        assign_to_product: !!v.product_id && !!v.assign_to_product,
      });
      m.status === "READY"
        ? toast.success("Model validated and registered as READY")
        : toast(`Registered, status: ${m.status} (${m.status_detail})`, {
            icon: "⚠️",
            duration: 7000,
          });
      setOpen(false);
      reset();
      refresh();
    } catch (e) {
      toast.error(errMsg(e));
    }
  };

  const revalidate = async (id: number) => {
    try {
      const m = await Api.validateModel(id);
      toast(`${m.name}: ${m.status}`);
      refresh();
    } catch (e) {
      toast.error(errMsg(e));
    }
  };

  const prodName = (id: number | null) =>
    products.data?.find((p) => p.id === id)?.name ?? "Unassigned";

  return (
    <>
      <PageHeader
        title="AI Model Registry & Artifact Management"
        subtitle="Hardware runtime validation, ONNX model registration, and product readiness matrix for Real AI inference."
        actions={
          admin && (
            <button className="btn-primary" onClick={() => setOpen(true)}>
              <Plus size={15} />
              Register Model Artifact
            </button>
          )
        }
      />

      {/* Model Readiness Matrix Card */}
      <Card className="mb-4 space-y-3">
        <div className="flex items-center justify-between border-b border-white/10 pb-2">
          <h3 className="text-xs font-mono font-bold tracking-wider text-white uppercase flex items-center gap-1.5">
            <Cpu size={14} className="text-sky-400" />
            Product AI Readiness Matrix
          </h3>
          <span className="text-[10px] font-mono text-slate-400">Inference Engine Status</span>
        </div>

        {status.data && (
          <>
            <p
              className={`text-xs font-mono font-semibold ${
                status.data.real_mode_available ? "text-pass" : "text-amber-400"
              }`}
              data-testid="real-status"
            >
              {status.data.message}
            </p>

            <div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-3 pt-1">
              {Object.entries(status.data.products).map(([id, p]) => (
                <div
                  key={id}
                  className="rounded border border-white/10 bg-ink-950/70 p-3 text-xs font-mono space-y-1"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-white truncate pr-2">{p.product}</span>
                    <span
                      className={`px-1.5 py-0.2 rounded text-[10px] font-bold ${
                        p.ready
                          ? "border border-pass/40 bg-pass/10 text-pass"
                          : "border border-slate-700 bg-slate-800 text-slate-400"
                      }`}
                    >
                      {p.ready ? "REAL AI READY" : "DEMO ONLY"}
                    </span>
                  </div>
                  {!p.ready && (
                    <p className="text-[11px] text-amber-300/80 leading-tight">{p.reasons[0]}</p>
                  )}
                  {p.version && (
                    <div className="text-[10px] text-sky-400 pt-0.5">Pipeline: {p.version}</div>
                  )}
                </div>
              ))}
            </div>
          </>
        )}
      </Card>

      {/* Registered Model Artifacts Table */}
      <Card className="space-y-3">
        <div className="flex items-center justify-between border-b border-white/10 pb-2">
          <h3 className="text-xs font-mono font-bold tracking-wider text-white uppercase flex items-center gap-1.5">
            <FileCode size={14} className="text-sky-400" />
            Registered Model Artifacts
          </h3>
          <span className="text-[10px] font-mono text-slate-400">ONNX & TorchScript Weights</span>
        </div>

        {models.isLoading ? (
          <Spinner label="Loading model registry" />
        ) : models.isError ? (
          <ErrorState message={errMsg(models.error)} onRetry={() => models.refetch()} />
        ) : !models.data?.length ? (
          <Empty
            title="No Trained Models Registered"
            hint="Model training is handled off-line. Export a trained PatchCore or Defect Classifier into ONNX format, place it with its .meta.json sidecar inside models/, then register it here."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr>
                  <th className="th">Model Artifact</th>
                  <th className="th">Architecture</th>
                  <th className="th">Format</th>
                  <th className="th">File Path</th>
                  <th className="th">Assigned Product</th>
                  <th className="th">Status</th>
                  <th className="th">Runtime Engine</th>
                  <th className="th">Validated</th>
                  {admin && <th className="th text-right">Actions</th>}
                </tr>
              </thead>
              <tbody>
                {models.data.map((m) => (
                  <tr key={m.id} className="border-t border-white/5 hover:bg-white/[0.02]">
                    <td className="td font-semibold text-white font-mono">
                      {m.name} <span className="text-slate-400 text-xs">v{m.version}</span>
                    </td>
                    <td className="td font-mono text-xs uppercase">{m.model_type}</td>
                    <td className="td font-mono text-xs uppercase">{m.format}</td>
                    <td className="td font-mono text-xs text-sky-400 truncate max-w-xs">{m.file_name}</td>
                    <td className="td font-mono text-xs">{prodName(m.product_id)}</td>
                    <td className="td">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold border ${COLOR[m.status]}`}>
                        {m.status}
                      </span>
                      {m.status_detail && (
                        <div className="text-[10px] font-mono text-slate-400 mt-1 max-w-xs truncate">
                          {m.status_detail}
                        </div>
                      )}
                    </td>
                    <td className="td font-mono text-xs text-slate-300">{m.runtime || "—"}</td>
                    <td className="td font-mono text-[11px] text-slate-400">
                      {m.last_validated_at ? fmtDate(m.last_validated_at) : "never"}
                    </td>
                    {admin && (
                      <td className="td text-right">
                        <button
                          className="btn-ghost !p-1 text-slate-400 hover:text-white"
                          aria-label={`Re-validate ${m.name}`}
                          title="Run Forward Validation Check"
                          onClick={() => revalidate(m.id)}
                        >
                          <RefreshCw size={13} />
                        </button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Model Registration Modal */}
      <Modal open={open} onClose={() => setOpen(false)} title="Register Model Weight Artifact">
        <form onSubmit={handleSubmit(submit)} className="space-y-3 font-mono text-xs" aria-label="Register model">
          <div className="grid grid-cols-2 gap-3 font-sans">
            <div>
              <label className="label" htmlFor="mn">
                Model Name
              </label>
              <input id="mn" className="input font-mono" placeholder="patchcore_pcb_v1" {...register("name")} />
              <FieldError msg={errors.name?.message} />
            </div>
            <div>
              <label className="label" htmlFor="mv">
                Model Version
              </label>
              <input id="mv" className="input font-mono" placeholder="1.0" {...register("version")} />
            </div>
            <div>
              <label className="label" htmlFor="mt">
                Pipeline Type
              </label>
              <select id="mt" className="input" {...register("model_type")}>
                <option value="patchcore">PatchCore (Anomaly Segmentation)</option>
                <option value="classifier">Defect Classifier (Categorization)</option>
              </select>
            </div>
            <div>
              <label className="label" htmlFor="mf">
                Runtime Format
              </label>
              <select id="mf" className="input" {...register("format")}>
                <option value="onnx">ONNX (.onnx)</option>
                <option value="torchscript">TorchScript (.pt)</option>
              </select>
            </div>
          </div>

          <div>
            <label className="label" htmlFor="mp">
              Weight File Path (Relative to models/ directory)
            </label>
            <input
              id="mp"
              className="input font-mono"
              placeholder="pcb/patchcore_v1.onnx"
              {...register("file_path")}
            />
            <FieldError msg={errors.file_path?.message} />
          </div>

          <div>
            <label className="label" htmlFor="mpr">
              Target Product Assignment
            </label>
            <select id="mpr" className="input" {...register("product_id")}>
              <option value="">Unassigned</option>
              {products.data?.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>

          <label className="flex items-center gap-2 text-xs font-mono cursor-pointer pt-1">
            <input
              type="checkbox"
              {...register("assign_to_product")}
              className="rounded border-slate-700 bg-slate-800 text-sky-500"
            />
            <span>Activate for this product immediately upon successful validation</span>
          </label>

          <p className="text-[11px] text-slate-400 font-sans border-t border-white/5 pt-2">
            Safety note: Model registration validates file existence, sidecar .meta.json tensor metadata, input/output dimensions, and executes a dry-run test tensor inference.
          </p>

          <div className="flex justify-end gap-2 pt-2">
            <button type="button" className="btn-ghost" onClick={() => setOpen(false)}>
              Cancel
            </button>
            <button className="btn-primary" disabled={isSubmitting}>
              {isSubmitting ? "Validating Artifact…" : "Validate & Register"}
            </button>
          </div>
        </form>
      </Modal>
    </>
  );
}
