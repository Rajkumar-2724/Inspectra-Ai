"""SQLAlchemy 2.x models. Portable to PostgreSQL (no SQLite-only types)."""
import enum
from datetime import datetime

from sqlalchemy import (Boolean, DateTime, Enum, Float, ForeignKey, Index, Integer, String, Text,
                        UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base
from app.utils.time import utcnow


class Role(str, enum.Enum):
    admin = "admin"
    inspector = "inspector"
    reviewer = "reviewer"


class Decision(str, enum.Enum):
    PASS = "PASS"
    REVIEW = "REVIEW"
    FAIL = "FAIL"


class Mode(str, enum.Enum):
    demo = "demo"
    real = "real"


class ReviewStatus(str, enum.Enum):
    NONE = "NONE"
    PENDING = "PENDING"
    REVIEWED = "REVIEWED"
    REINSPECT = "REINSPECT"


class ReviewDecision(str, enum.Enum):
    approve = "approve"
    reject = "reject"
    reinspect = "reinspect"


class ModelStatus(str, enum.Enum):
    NOT_CONFIGURED = "NOT_CONFIGURED"
    FILE_MISSING = "FILE_MISSING"
    INVALID = "INVALID"
    READY = "READY"
    ERROR = "ERROR"


class JobStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    DONE = "DONE"
    FAILED = "FAILED"


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(128), default="")
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role, native_enum=False, length=16), default=Role.inspector)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    category: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(Text, default="")
    reference_image_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    review_threshold: Mapped[float] = mapped_column(Float, default=0.40)
    fail_threshold: Mapped[float] = mapped_column(Float, default=0.70)
    patchcore_model_id: Mapped[int | None] = mapped_column(ForeignKey("model_versions.id", ondelete="SET NULL", use_alter=True, name="fk_products_patchcore"), nullable=True)
    classifier_model_id: Mapped[int | None] = mapped_column(ForeignKey("model_versions.id", ondelete="SET NULL", use_alter=True, name="fk_products_classifier"), nullable=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    defect_classes: Mapped[list["ProductDefectClass"]] = relationship(
        back_populates="product", cascade="all, delete-orphan", lazy="selectin")


class ProductDefectClass(Base):
    __tablename__ = "product_defect_classes"
    __table_args__ = (UniqueConstraint("product_id", "name"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(64))
    product: Mapped[Product] = relationship(back_populates="defect_classes")


class ModelVersion(Base):
    __tablename__ = "model_versions"
    __table_args__ = (UniqueConstraint("name", "version"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    version: Mapped[str] = mapped_column(String(32))
    model_type: Mapped[str] = mapped_column(String(32))  # patchcore | classifier
    format: Mapped[str] = mapped_column(String(16))  # onnx | torchscript
    file_path: Mapped[str] = mapped_column(String(512))
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL", use_alter=True, name="fk_model_versions_product"), nullable=True)
    status: Mapped[ModelStatus] = mapped_column(Enum(ModelStatus, native_enum=False, length=20), default=ModelStatus.NOT_CONFIGURED)
    status_detail: Mapped[str] = mapped_column(Text, default="")
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    runtime: Mapped[str] = mapped_column(String(64), default="")
    file_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_validated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class InspectionBatch(Base):
    __tablename__ = "inspection_batches"
    id: Mapped[int] = mapped_column(primary_key=True)
    batch_code: Mapped[str] = mapped_column(String(64), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    line_id: Mapped[str] = mapped_column(String(64), default="")
    mode: Mapped[Mode] = mapped_column(Enum(Mode, native_enum=False, length=8), default=Mode.demo)
    scenario: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    product: Mapped[Product] = relationship(lazy="joined")
    jobs: Mapped[list["BatchJob"]] = relationship(back_populates="batch", cascade="all, delete-orphan")


class Inspection(Base):
    __tablename__ = "inspections"
    __table_args__ = (Index("ix_insp_created", "created_at"), Index("ix_insp_prod_dec", "product_id", "decision"))
    id: Mapped[int] = mapped_column(primary_key=True)
    uid: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    product_code: Mapped[str] = mapped_column(String(64), default="")  # physical item / serial id
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("inspection_batches.id", ondelete="SET NULL"), nullable=True, index=True)
    batch_code: Mapped[str] = mapped_column(String(64), default="", index=True)
    line_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    mode: Mapped[Mode] = mapped_column(Enum(Mode, native_enum=False, length=8), index=True)
    simulated: Mapped[bool] = mapped_column(Boolean, default=False)
    scenario: Mapped[str | None] = mapped_column(String(32), nullable=True)
    score: Mapped[float] = mapped_column(Float)
    decision: Mapped[Decision] = mapped_column(Enum(Decision, native_enum=False, length=8), index=True)
    defect_class: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    review_threshold: Mapped[float] = mapped_column(Float)
    fail_threshold: Mapped[float] = mapped_column(Float)
    model_version: Mapped[str] = mapped_column(String(128))
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    notes: Mapped[str] = mapped_column(Text, default="")
    image_sha256: Mapped[str] = mapped_column(String(64))
    image_width: Mapped[int] = mapped_column(Integer, default=0)
    image_height: Mapped[int] = mapped_column(Integer, default=0)
    review_status: Mapped[ReviewStatus] = mapped_column(Enum(ReviewStatus, native_enum=False, length=12), default=ReviewStatus.NONE, index=True)
    final_decision: Mapped[Decision | None] = mapped_column(Enum(Decision, native_enum=False, length=8), nullable=True)
    explanation_json: Mapped[str] = mapped_column(Text, default="{}")
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    product: Mapped[Product] = relationship(lazy="joined")
    images: Mapped[list["InspectionImage"]] = relationship(cascade="all, delete-orphan", lazy="selectin")
    defects: Mapped[list["InspectionDefect"]] = relationship(cascade="all, delete-orphan", lazy="selectin")
    reviews: Mapped[list["ReviewAction"]] = relationship(cascade="all, delete-orphan", lazy="selectin", order_by="ReviewAction.id")


class InspectionImage(Base):
    __tablename__ = "inspection_images"
    __table_args__ = (UniqueConstraint("inspection_id", "kind"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    inspection_id: Mapped[int] = mapped_column(ForeignKey("inspections.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(24))  # original|processed|heatmap|overlay|annotated|reference_patch
    path: Mapped[str] = mapped_column(String(512))
    width: Mapped[int] = mapped_column(Integer, default=0)
    height: Mapped[int] = mapped_column(Integer, default=0)


class InspectionDefect(Base):
    __tablename__ = "inspection_defects"
    id: Mapped[int] = mapped_column(primary_key=True)
    inspection_id: Mapped[int] = mapped_column(ForeignKey("inspections.id", ondelete="CASCADE"), index=True)
    x: Mapped[int] = mapped_column(Integer)
    y: Mapped[int] = mapped_column(Integer)
    w: Mapped[int] = mapped_column(Integer)
    h: Mapped[int] = mapped_column(Integer)
    area: Mapped[int] = mapped_column(Integer, default=0)
    peak_score: Mapped[float] = mapped_column(Float, default=0.0)
    label: Mapped[str] = mapped_column(String(64), default="unknown_defect")
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)


class BatchJob(Base):
    __tablename__ = "batch_jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("inspection_batches.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(512))
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus, native_enum=False, length=12), default=JobStatus.QUEUED, index=True)
    error: Mapped[str] = mapped_column(Text, default="")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    inspection_id: Mapped[int | None] = mapped_column(ForeignKey("inspections.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    batch: Mapped[InspectionBatch] = relationship(back_populates="jobs")


class ReviewAction(Base):
    __tablename__ = "review_actions"
    id: Mapped[int] = mapped_column(primary_key=True)
    inspection_id: Mapped[int] = mapped_column(ForeignKey("inspections.id", ondelete="CASCADE"), index=True)
    reviewer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewer_name: Mapped[str] = mapped_column(String(128), default="")
    decision: Mapped[ReviewDecision] = mapped_column(Enum(ReviewDecision, native_enum=False, length=12))
    comment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AuditEvent(Base):
    """Append-only. No API updates or deletes rows of this table."""
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    seq: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    event_type: Mapped[str] = mapped_column(String(32), index=True)  # INSPECTION | REVIEW
    inspection_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    payload_json: Mapped[str] = mapped_column(Text)  # canonical JSON
    prev_hash: Mapped[str] = mapped_column(String(64))
    record_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AppSetting(Base):
    __tablename__ = "app_settings"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class EvaluationLabel(Base):
    """Verified ground truth. Metrics are computed ONLY from rows in this table."""
    __tablename__ = "evaluation_labels"
    id: Mapped[int] = mapped_column(primary_key=True)
    inspection_id: Mapped[int] = mapped_column(ForeignKey("inspections.id", ondelete="CASCADE"), unique=True)
    ground_truth: Mapped[str] = mapped_column(String(16))  # good | defective
    true_defect_class: Mapped[str | None] = mapped_column(String(64), nullable=True)
    labeled_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
