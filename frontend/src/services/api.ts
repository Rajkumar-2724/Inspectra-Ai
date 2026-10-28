import axios, { AxiosError } from "axios";
import type { AuditEvent, Batch, Inspection, ModelsStatus, ModelVersion, Page, Product, Scenario, User } from "../types";

export const API_URL: string = (import.meta.env.VITE_API_URL as string) || "http://127.0.0.1:8000";
export const TOKEN_KEY = "avis_token";

export const api = axios.create({ baseURL: API_URL, timeout: 60000 });
api.interceptors.request.use((cfg) => {
  const t = localStorage.getItem(TOKEN_KEY);
  if (t) cfg.headers.Authorization = `Bearer ${t}`;
  return cfg;
});
api.interceptors.response.use(
  (r) => r,
  (e: AxiosError) => {
    if (e.response?.status === 401 && !e.config?.url?.includes("/auth/login")) {
      localStorage.removeItem(TOKEN_KEY);
      window.dispatchEvent(new Event("avis:logout"));
    }
    return Promise.reject(e);
  }
);

/** Turns any API failure into a readable sentence. */
export function errMsg(e: unknown): string {
  const ae = e as AxiosError<any>;
  if (ae?.response) {
    const d = ae.response.data?.detail;
    if (typeof d === "string") return d;
    if (d?.message) return d.message + (d.reasons?.length ? ` (${d.reasons.join("; ")})` : "");
    if (ae.response.data?.errors?.length) return ae.response.data.errors.map((x: any) => `${x.field}: ${x.message}`).join("; ");
    return `Request failed (${ae.response.status})`;
  }
  if (ae?.code === "ERR_NETWORK") return "Cannot reach the backend. Is it running on " + API_URL + "?";
  return (e as Error)?.message || "Unexpected error";
}

const get = <T,>(url: string, params?: object) => api.get<T>(url, { params }).then((r) => r.data);

export const Api = {
  login: (username: string, password: string) => api.post<{ access_token: string; user: User }>("/api/auth/login", { username, password }).then((r) => r.data),
  register: (b: { email: string; username: string; full_name: string; password: string }) => api.post<User>("/api/auth/register", b).then((r) => r.data),
  me: () => get<User>("/api/auth/me"),
  changePassword: (current_password: string, new_password: string) => api.post("/api/auth/change-password", { current_password, new_password }),
  users: () => get<User[]>("/api/users"),
  createUser: (b: object) => api.post<User>("/api/users", b).then((r) => r.data),
  patchUser: (id: number, b: object) => api.patch<User>(`/api/users/${id}`, b).then((r) => r.data),

  products: (include_archived = false) => get<Product[]>("/api/products", { include_archived }),
  categories: () => get<string[]>("/api/products/categories"),
  createProduct: (b: object) => api.post<Product>("/api/products", b).then((r) => r.data),
  patchProduct: (id: number, b: object) => api.patch<Product>(`/api/products/${id}`, b).then((r) => r.data),
  archiveProduct: (id: number) => api.delete<Product>(`/api/products/${id}`).then((r) => r.data),
  uploadReference: (id: number, file: File) => { const f = new FormData(); f.append("file", file); return api.post<Product>(`/api/products/${id}/reference-image`, f).then((r) => r.data); },

  inspect: (f: FormData) => api.post<Inspection>("/api/inspect", f).then((r) => r.data),
  inspections: (params: object) => get<Page<Inspection>>("/api/inspections", params),
  inspection: (id: number) => get<Inspection>(`/api/inspections/${id}`),

  createBatch: (b: object) => api.post<Batch>("/api/batches", b).then((r) => r.data),
  batches: () => get<Batch[]>("/api/batches"),
  batch: (id: number) => get<Batch>(`/api/batches/${id}`),
  batchUpload: (id: number, files: File[]) => { const f = new FormData(); files.forEach((x) => f.append("files", x)); return api.post<Batch>(`/api/batches/${id}/inspect`, f).then((r) => r.data); },
  batchRetry: (id: number) => api.post<Batch>(`/api/batches/${id}/retry`).then((r) => r.data),
  batchInspections: (id: number, decision?: string) => get<Inspection[]>(`/api/batches/${id}/inspections`, { decision }),

  pendingReviews: () => get<Inspection[]>("/api/reviews/pending"),
  decide: (id: number, decision: string, comment: string) => api.post<Inspection>(`/api/reviews/${id}/decision`, { decision, comment }).then((r) => r.data),

  stats: (mode?: string) => get<any>("/api/dashboard/stats", { mode }),
  trends: (days: number, mode?: string) => get<any>("/api/dashboard/trends", { days, mode }),
  recent: (mode?: string) => get<Inspection[]>("/api/dashboard/recent", { mode }),
  defects: (days: number, mode?: string, product_id?: number) => get<any>("/api/analytics/defects", { days, mode, product_id }),
  analyticsTrends: (days: number, mode?: string) => get<any>("/api/analytics/trends", { days, mode }),
  latency: (days: number, mode?: string) => get<any>("/api/analytics/latency", { days, mode }),
  groundTruth: (b: object) => api.post("/api/analytics/ground-truth", b),

  models: () => get<ModelVersion[]>("/api/models"),
  modelsStatus: () => get<ModelsStatus>("/api/models/status"),
  registerModel: (b: object) => api.post<ModelVersion>("/api/models/register", b).then((r) => r.data),
  validateModel: (id: number) => api.post<ModelVersion>(`/api/models/${id}/validate`).then((r) => r.data),

  auditEvents: (params: object) => get<{ items: AuditEvent[]; total: number; page: number; page_size: number }>("/api/audit/events", params),
  auditVerify: () => get<{ valid: boolean; events_checked: number; head_hash: string; problems: { seq: number; problem: string }[]; verified_at: string; note: string }>("/api/audit/verify"),

  systemStatus: () => get<any>("/api/system/status"),
  putSettings: (values: Record<string, string>) => api.put("/api/system/settings", { values }),
  imageBlob: (id: number, kind: string) => api.get(`/api/inspections/${id}/images/${kind}`, { responseType: "blob" }).then((r) => r.data as Blob),
};

export async function download(url: string, filename: string, params?: object) {
  const r = await api.get(url, { responseType: "blob", params });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(r.data);
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}
