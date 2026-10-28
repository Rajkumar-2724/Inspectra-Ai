from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.models.models import Decision, JobStatus, ModelStatus, ReviewDecision, ReviewStatus, Role

CATEGORIES = ["PCB", "Metal surface", "Bottle or cap", "Fabric", "Machined component", "Other"]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class RegisterIn(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    full_name: str = Field(default="", max_length=128)
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    username: str
    password: str


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class UserOut(ORM):
    id: int
    email: str
    username: str
    full_name: str
    role: Role
    is_active: bool
    created_at: datetime


class UserAdminIn(RegisterIn):
    role: Role = Role.inspector


class UserAdminPatch(BaseModel):
    role: Role | None = None
    is_active: bool | None = None


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class _Thresholds(BaseModel):
    review_threshold: float = 0.40
    fail_threshold: float = 0.70


class ProductIn(_Thresholds):
    name: str = Field(min_length=2, max_length=128)
    category: str = Field(min_length=2, max_length=64)
    description: str = Field(default="", max_length=2000)
    defect_classes: list[str] = []
    patchcore_model_id: int | None = None
    classifier_model_id: int | None = None

    @model_validator(mode="after")
    def _chk(self):
        if not (0 <= self.review_threshold < self.fail_threshold <= 1):
            raise ValueError("Thresholds must satisfy 0 <= review < fail <= 1")
        return self

    @field_validator("defect_classes")
    @classmethod
    def _classes(cls, v):
        out = []
        for n in v:
            n = n.strip().lower().replace(" ", "_")
            if n and n not in out and n != "unknown_defect":
                out.append(n[:64])
        return out


class ProductPatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=128)
    category: str | None = None
    description: str | None = None
    defect_classes: list[str] | None = None
    review_threshold: float | None = None
    fail_threshold: float | None = None
    patchcore_model_id: int | None = None
    classifier_model_id: int | None = None
    archived: bool | None = None
    clear_patchcore_model: bool = False
    clear_classifier_model: bool = False


class ProductOut(ORM):
    id: int
    name: str
    category: str
    description: str
    review_threshold: float
    fail_threshold: float
    patchcore_model_id: int | None
    classifier_model_id: int | None
    archived: bool
    has_reference_image: bool = False
    defect_classes: list[str] = []
    inspection_count: int = 0
    real_mode_ready: bool = False
    created_at: datetime


class DefectOut(ORM):
    id: int
    x: int
    y: int
    w: int
    h: int
    area: int
    peak_score: float
    label: str
    confidence: float | None
    region_id: int | None = None
    shape: str = "ellipse"
    center_x: float | None = None
    center_y: float | None = None
    radius_x: float | None = None
    radius_y: float | None = None
    angle: float | None = None
    crop_kind: str | None = None


class ReviewOut(ORM):
    id: int
    reviewer_id: int | None
    reviewer_name: str
    decision: ReviewDecision
    comment: str
    created_at: datetime


class InspectionOut(BaseModel):
    id: int
    uid: str
    product_id: int
    product_name: str
    product_category: str
    product_code: str
    batch_id: int | None
    batch_code: str
    line_id: str
    mode: Literal["demo", "real"]
    simulated: bool
    scenario: str | None
    score: float
    decision: Decision
    defect_class: str | None
    confidence: float | None
    review_threshold: float
    fail_threshold: float
    model_version: str
    latency_ms: float
    notes: str
    image_sha256: str
    image_width: int = 0
    image_height: int = 0
    review_status: ReviewStatus
    final_decision: Decision | None
    explanation: dict[str, Any] = {}
    defects: list[DefectOut] = []
    reviews: list[ReviewOut] = []
    images: list[str] = []
    created_at: datetime


class InspectionPage(BaseModel):
    items: list[InspectionOut]
    total: int
    page: int
    page_size: int


class ReviewIn(BaseModel):
    decision: ReviewDecision
    comment: str = Field(default="", max_length=2000)


class BatchIn(BaseModel):
    batch_code: str = Field(min_length=1, max_length=64)
    product_id: int
    line_id: str = Field(default="", max_length=64)
    mode: Literal["demo", "real"] = "real"
    scenario: str | None = None


class JobOut(ORM):
    id: int
    filename: str
    status: JobStatus
    error: str
    attempts: int
    inspection_id: int | None


class BatchOut(BaseModel):
    id: int
    batch_code: str
    product_id: int
    product_name: str
    line_id: str
    mode: str
    scenario: str | None
    created_at: datetime
    total: int
    counts: dict[str, int]
    job_counts: dict[str, int]
    progress: float
    jobs: list[JobOut] = []


class ModelRegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=128)
    version: str = Field(min_length=1, max_length=32)
    model_type: Literal["patchcore", "classifier"]
    format: Literal["onnx", "torchscript"]
    file_path: str = Field(min_length=1, max_length=512, description="Path inside the models directory")
    product_id: int | None = None
    assign_to_product: bool = False


class ModelOut(ORM):
    id: int
    name: str
    version: str
    model_type: str
    format: str
    file_name: str = ""
    product_id: int | None
    status: ModelStatus
    status_detail: str
    runtime: str
    last_validated_at: datetime | None
    metadata_summary: dict[str, Any] = {}
    created_at: datetime


class GroundTruthIn(BaseModel):
    inspection_id: int
    ground_truth: Literal["good", "defective"]
    true_defect_class: str | None = None


class SettingsIn(BaseModel):
    values: dict[str, str]
