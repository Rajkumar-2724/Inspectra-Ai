import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Archive,
  Boxes,
  CheckCircle2,
  FileCheck,
  Layers,
  Pencil,
  Plus,
  RotateCcw,
  Sliders,
  Upload,
  XCircle,
} from "lucide-react";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import toast from "react-hot-toast";
import { z } from "zod";
import { Card, Empty, ErrorState, FieldError, Modal, PageHeader, Spinner } from "../components/ui";
import { useAuth } from "../contexts/AuthContext";
import { Api, errMsg } from "../services/api";
import type { Product } from "../types";

const schema = z
  .object({
    name: z.string().min(2, "At least 2 characters").max(128),
    category: z.string().min(1, "Choose a category"),
    description: z.string().max(2000).optional(),
    defect_classes: z.string().optional(),
    review_threshold: z.coerce.number().min(0).max(1),
    fail_threshold: z.coerce.number().min(0).max(1),
    patchcore_model_id: z.string().optional(),
    classifier_model_id: z.string().optional(),
  })
  .refine((d) => d.review_threshold < d.fail_threshold, {
    path: ["fail_threshold"],
    message: "Fail threshold must be greater than review threshold",
  });
type F = z.infer<typeof schema>;

export default function Products() {
  const { has } = useAuth();
  const qc = useQueryClient();
  const admin = has();
  const [showArchived, setShowArchived] = useState(false);
  const [edit, setEdit] = useState<Product | "new" | null>(null);

  const q = useQuery({
    queryKey: ["products", showArchived],
    queryFn: () => Api.products(showArchived),
  });
  const cats = useQuery({ queryKey: ["categories"], queryFn: Api.categories });
  const models = useQuery({ queryKey: ["models"], queryFn: Api.models });

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<F>({ resolver: zodResolver(schema) });

  useEffect(() => {
    if (edit === "new") {
      reset({
        name: "",
        category: "PCB",
        description: "",
        defect_classes: "scratch, crack, solder_bridge",
        review_threshold: 0.4,
        fail_threshold: 0.7,
        patchcore_model_id: "",
        classifier_model_id: "",
      });
    } else if (edit) {
      reset({
        name: edit.name,
        category: edit.category,
        description: edit.description,
        defect_classes: edit.defect_classes.join(", "),
        review_threshold: edit.review_threshold,
        fail_threshold: edit.fail_threshold,
        patchcore_model_id: edit.patchcore_model_id?.toString() ?? "",
        classifier_model_id: edit.classifier_model_id?.toString() ?? "",
      });
    }
  }, [edit, reset]);

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["products"] });
    qc.invalidateQueries({ queryKey: ["models-status"] });
  };

  const save = async (v: F) => {
    const body: any = {
      name: v.name,
      category: v.category,
      description: v.description ?? "",
      review_threshold: v.review_threshold,
      fail_threshold: v.fail_threshold,
      defect_classes: (v.defect_classes ?? "")
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean),
    };
    try {
      if (edit === "new") {
        if (v.patchcore_model_id) body.patchcore_model_id = Number(v.patchcore_model_id);
        if (v.classifier_model_id) body.classifier_model_id = Number(v.classifier_model_id);
        await Api.createProduct(body);
      } else if (edit) {
        if (v.patchcore_model_id) body.patchcore_model_id = Number(v.patchcore_model_id);
        else body.clear_patchcore_model = true;
        if (v.classifier_model_id) body.classifier_model_id = Number(v.classifier_model_id);
        else body.clear_classifier_model = true;
        await Api.patchProduct(edit.id, body);
      }
      toast.success("Product configuration saved");
      setEdit(null);
      refresh();
    } catch (e) {
      toast.error(errMsg(e));
    }
  };

  const archive = async (p: Product) => {
    if (!confirm(`Archive product configuration for “${p.name}”? Historical records remain preserved.`))
      return;
    try {
      await Api.archiveProduct(p.id);
      toast.success(`Archived ${p.name}`);
      refresh();
    } catch (e) {
      toast.error(errMsg(e));
    }
  };

  const restore = async (p: Product) => {
    try {
      await Api.patchProduct(p.id, { archived: false });
      toast.success(`Restored ${p.name}`);
      refresh();
    } catch (e) {
      toast.error(errMsg(e));
    }
  };

  const upload = async (p: Product, f?: File) => {
    if (!f) return;
    try {
      await Api.uploadReference(p.id, f);
      toast.success("Nominal reference image registered");
      refresh();
    } catch (e) {
      toast.error(errMsg(e));
    }
  };

  return (
    <>
      <PageHeader
        title="Product Inspection Catalog"
        subtitle="Manage inspection parameters, defect classifications, nominal reference images, and dual quality thresholds."
        actions={
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-2 text-xs font-mono text-slate-400 cursor-pointer">
              <input
                type="checkbox"
                checked={showArchived}
                onChange={(e) => setShowArchived(e.target.checked)}
                className="rounded border-slate-700 bg-slate-800 text-sky-500"
              />
              Show Archived Products
            </label>
            {admin && (
              <button className="btn-primary" onClick={() => setEdit("new")}>
                <Plus size={15} />
                New Product Spec
              </button>
            )}
          </div>
        }
      />

      <Card>
        {q.isLoading ? (
          <Spinner label="Loading product catalog" />
        ) : q.isError ? (
          <ErrorState message={errMsg(q.error)} onRetry={() => q.refetch()} />
        ) : !q.data?.length ? (
          <Empty
            title="Product Catalog Empty"
            hint="Create a product configuration to begin visual quality inspections."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr>
                  <th className="th">Product Model</th>
                  <th className="th">Category</th>
                  <th className="th">Defect Classes</th>
                  <th className="th">Review / Fail Threshold</th>
                  <th className="th">Model Pipeline</th>
                  <th className="th">Total Tested</th>
                  <th className="th">Nominal Ref</th>
                  {admin && <th className="th text-right">Actions</th>}
                </tr>
              </thead>
              <tbody>
                {q.data.map((p) => (
                  <tr
                    key={p.id}
                    className={`border-t border-white/5 hover:bg-white/[0.02] ${
                      p.archived ? "opacity-50" : ""
                    }`}
                  >
                    <td className="td font-semibold text-white">
                      {p.name}
                      {p.archived && (
                        <span className="ml-2 rounded border border-slate-700 bg-slate-800 px-1.5 py-0.2 text-[10px] font-mono text-slate-400">
                          ARCHIVED
                        </span>
                      )}
                    </td>
                    <td className="td font-mono text-xs text-slate-300">{p.category}</td>
                    <td className="td font-mono text-[11px] text-slate-300 max-w-xs truncate">
                      {p.defect_classes.join(", ") || "General Anomaly"}
                    </td>
                    <td className="td font-mono text-xs">
                      <span className="text-amber-400 font-semibold">{p.review_threshold.toFixed(2)}</span>
                      {" / "}
                      <span className="text-rose-400 font-semibold">{p.fail_threshold.toFixed(2)}</span>
                    </td>
                    <td className="td">
                      {p.real_mode_ready ? (
                        <span className="inline-flex items-center gap-1 text-[11px] font-mono text-pass">
                          <CheckCircle2 size={12} /> Ready
                        </span>
                      ) : (
                        <span className="text-[11px] font-mono text-slate-500">Demo Simulator</span>
                      )}
                    </td>
                    <td className="td font-mono text-xs text-slate-300">{p.inspection_count}</td>
                    <td className="td font-mono text-xs">
                      {p.has_reference_image ? (
                        <span className="text-emerald-400">Registered</span>
                      ) : (
                        <span className="text-slate-500">None</span>
                      )}
                    </td>
                    {admin && (
                      <td className="td text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          <button
                            className="btn-ghost !p-1 text-slate-400 hover:text-white"
                            aria-label={`Edit ${p.name}`}
                            title="Edit Product Spec"
                            onClick={() => setEdit(p)}
                          >
                            <Pencil size={13} />
                          </button>
                          <label
                            className="btn-ghost !p-1 text-sky-400 hover:text-white cursor-pointer"
                            title="Upload Nominal Reference Image"
                          >
                            <Upload size={13} />
                            <input
                              type="file"
                              accept="image/*"
                              className="hidden"
                              aria-label={`Reference image for ${p.name}`}
                              onChange={(e) => upload(p, e.target.files?.[0])}
                            />
                          </label>
                          {p.archived ? (
                            <button
                              className="btn-ghost !px-2 !py-0.5 text-[11px] font-mono text-amber-400"
                              onClick={() => restore(p)}
                            >
                              Restore
                            </button>
                          ) : (
                            <button
                              className="btn-ghost !p-1 text-rose-400 hover:bg-rose-500/20"
                              aria-label={`Archive ${p.name}`}
                              title="Archive Product"
                              onClick={() => archive(p)}
                            >
                              <Archive size={13} />
                            </button>
                          )}
                        </div>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Edit / New Product Modal */}
      <Modal
        open={!!edit}
        onClose={() => setEdit(null)}
        title={edit === "new" ? "New Product Specification" : `Edit Specification: ${edit?.name}`}
        wide
      >
        <form onSubmit={handleSubmit(save)} className="grid gap-3 sm:grid-cols-2" aria-label="Product form">
          <div>
            <label className="label" htmlFor="pn">
              Product Name / Model
            </label>
            <input
              id="pn"
              className="input font-mono"
              placeholder="e.g. PCB Mainboard Rev 3"
              {...register("name")}
            />
            <FieldError msg={errors.name?.message} />
          </div>

          <div>
            <label className="label" htmlFor="pcat">
              Manufacturing Category
            </label>
            <select id="pcat" className="input" {...register("category")}>
              {cats.data?.map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
          </div>

          <div className="sm:col-span-2">
            <label className="label" htmlFor="pd">
              Product Description & Quality Standards
            </label>
            <textarea
              id="pd"
              rows={2}
              className="input"
              placeholder="Description of the component, surface finish requirements, and tolerance criteria…"
              {...register("description")}
            />
          </div>

          <div className="sm:col-span-2">
            <label className="label" htmlFor="pdc">
              Registered Defect Classes (Comma separated)
            </label>
            <input
              id="pdc"
              className="input font-mono"
              placeholder="e.g. scratch, crack, missing_component, solder_bridge"
              {...register("defect_classes")}
            />
          </div>

          <div>
            <label className="label" htmlFor="prt">
              Review Threshold (0.00 – 1.00)
            </label>
            <input
              id="prt"
              type="number"
              step="0.01"
              className="input font-mono"
              {...register("review_threshold")}
            />
            <FieldError msg={errors.review_threshold?.message} />
          </div>

          <div>
            <label className="label" htmlFor="pft">
              Fail Threshold (0.00 – 1.00)
            </label>
            <input
              id="pft"
              type="number"
              step="0.01"
              className="input font-mono"
              {...register("fail_threshold")}
            />
            <FieldError msg={errors.fail_threshold?.message} />
          </div>

          <div>
            <label className="label" htmlFor="ppm">
              Assigned PatchCore Anomaly Model
            </label>
            <select id="ppm" className="input font-mono text-xs" {...register("patchcore_model_id")}>
              <option value="">None (Use Simulation Engine)</option>
              {models.data
                ?.filter((m) => m.model_type === "patchcore")
                .map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name} v{m.version} ({m.status})
                  </option>
                ))}
            </select>
          </div>

          <div>
            <label className="label" htmlFor="pcm">
              Assigned Defect Classifier Model
            </label>
            <select id="pcm" className="input font-mono text-xs" {...register("classifier_model_id")}>
              <option value="">None (Use Simulation Engine)</option>
              {models.data
                ?.filter((m) => m.model_type === "classifier")
                .map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name} v{m.version} ({m.status})
                  </option>
                ))}
            </select>
          </div>

          <p className="text-[11px] font-mono text-slate-400 sm:col-span-2 pt-1 border-t border-white/5">
            Quality thresholds calibrate the decision boundary: Anomaly score &lt; Review = PASS, between Review and Fail = REVIEW, &gt; Fail = FAIL.
          </p>

          <div className="flex justify-end gap-2 sm:col-span-2 pt-2">
            <button type="button" className="btn-ghost font-mono" onClick={() => setEdit(null)}>
              Cancel
            </button>
            <button className="btn-primary font-mono" disabled={isSubmitting}>
              {isSubmitting ? "Saving Configuration…" : "Save Product Spec"}
            </button>
          </div>
        </form>
      </Modal>
    </>
  );
}
