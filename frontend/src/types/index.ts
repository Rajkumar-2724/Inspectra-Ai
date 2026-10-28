export type Role = "admin" | "inspector" | "reviewer";
export type Decision = "PASS" | "REVIEW" | "FAIL";
export type Mode = "demo" | "real";
export interface User { id: number; email: string; username: string; full_name: string; role: Role; is_active: boolean; created_at: string }
export interface Product {
  id: number; name: string; category: string; description: string; review_threshold: number; fail_threshold: number;
  patchcore_model_id: number | null; classifier_model_id: number | null; archived: boolean; has_reference_image: boolean;
  defect_classes: string[]; inspection_count: number; real_mode_ready: boolean; created_at: string;
}
export interface Defect {
  id: number;
  x: number;
  y: number;
  w: number;
  h: number;
  area: number;
  peak_score: number;
  label: string;
  confidence: number | null;
  region_id?: number;
  shape?: "ellipse" | "circle" | "box";
  center_x?: number;
  center_y?: number;
  radius_x?: number;
  radius_y?: number;
  angle?: number;
  crop_kind?: string;
  crop_data?: string;
}
export interface DefectRegion {
  id: number;
  shape: "ellipse" | "circle";
  center: [number, number];
  axes: [number, number];
  angle: number;
  box: [number, number, number, number];
  original_box?: [number, number, number, number];
  original_geometry?: {
    shape: "ellipse" | "circle";
    center: [number, number];
    axes: [number, number];
    angle: number;
  };
  contour?: number[][];
  area: number;
  peak_score: number;
  label: string;
  defect_name?: string;
  confidence: number | null;
  crop_kind?: string;
  crop_data?: string;
}
export interface Review { id: number; reviewer_id: number | null; reviewer_name: string; decision: "approve" | "reject" | "reinspect"; comment: string; created_at: string }
export interface Inspection {
  id: number; uid: string; product_id: number; product_name: string; product_category: string; product_code: string;
  batch_id: number | null; batch_code: string; line_id: string; mode: Mode; simulated: boolean; scenario: string | null;
  score: number; decision: Decision; defect_class: string | null; confidence: number | null; review_threshold: number; fail_threshold: number;
  model_version: string; latency_ms: number; notes: string; image_sha256: string; image_width?: number; image_height?: number; review_status: "NONE" | "PENDING" | "REVIEWED" | "REINSPECT";
  final_decision: Decision | null; explanation: Record<string, any>; defects: Defect[]; reviews: Review[]; images: string[]; created_at: string;
}
export interface Page<T> { items: T[]; total: number; page: number; page_size: number }
export interface Job { id: number; filename: string; status: "QUEUED" | "PROCESSING" | "DONE" | "FAILED"; error: string; attempts: number; inspection_id: number | null }
export interface Batch {
  id: number; batch_code: string; product_id: number; product_name: string; line_id: string; mode: Mode; scenario: string | null;
  created_at: string; total: number; counts: Record<Decision, number>; job_counts: Record<string, number>; progress: number; jobs: Job[];
}
export interface ModelVersion {
  id: number; name: string; version: string; model_type: string; format: string; file_name: string; product_id: number | null;
  status: "NOT_CONFIGURED" | "FILE_MISSING" | "INVALID" | "READY" | "ERROR"; status_detail: string; runtime: string;
  last_validated_at: string | null; metadata_summary: Record<string, any>; created_at: string;
}
export interface ModelsStatus { real_mode_available: boolean; registered_models: number; message: string; products: Record<string, { product: string; ready: boolean; version: string | null; reasons: string[] }> }
export interface Scenario { key: string; title: string; expected: string; description: string }
export interface AuditEvent { id: number; seq: number; event_type: string; inspection_id: number | null; payload: Record<string, any>; prev_hash: string; record_hash: string; created_at: string }
