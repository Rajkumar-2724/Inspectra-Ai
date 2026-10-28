"""Model registry: artifact validation, readiness checks and cached adapter loading.

Safety: only ONNX (.onnx) and TorchScript (.pt/.ts/.torchscript) artifacts located INSIDE the
configured models directory are accepted. Pickle based formats (.pth/.ckpt/.pkl) are rejected.
"""
import hashlib
import json
import threading
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.classifier_adapter import ClassifierAdapter
from app.ai.onnx_adapter import RuntimeLoadError, load_runtime
from app.ai.patchcore_adapter import PatchCoreAdapter
from app.core.config import get_settings
from app.models.models import ModelStatus, ModelVersion, Product
from app.utils.time import utcnow

ALLOWED_EXT = {"onnx": {".onnx"}, "torchscript": {".pt", ".ts", ".torchscript"}}
UNSAFE_EXT = {".pth", ".ckpt", ".pkl", ".pickle", ".joblib"}


class ModelNotReadyError(RuntimeError):
    def __init__(self, reasons: list[str]):
        self.reasons = reasons
        super().__init__("; ".join(reasons))


class ModelPathError(ValueError):
    pass


def resolve_model_path(file_path: str) -> Path:
    base = get_settings().models_path
    p = Path(file_path)
    p = (p if p.is_absolute() else base / p).resolve()
    if not p.is_relative_to(base):
        raise ModelPathError("Model files must be inside the configured models directory")
    return p


def metadata_path(p: Path) -> Path:
    return p.with_suffix(".meta.json")


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class ValidationResult:
    status: ModelStatus
    detail: str
    meta: dict
    runtime: str = ""
    sha256: str | None = None
    runtime_obj: object | None = None


def _validate_meta(model_type: str, meta: dict) -> str | None:
    size = meta.get("input_size")
    if not (isinstance(size, list) and len(size) == 2 and all(isinstance(v, int) and v > 8 for v in size)):
        return "metadata.input_size must be [height, width] integers"
    if model_type == "patchcore":
        for k in ("score_min", "score_max"):
            if not isinstance(meta.get(k), (int, float)):
                return f"metadata.{k} (calibration value) is required"
        if meta["score_max"] <= meta["score_min"]:
            return "metadata.score_max must be greater than score_min"
    else:
        names = meta.get("class_names")
        if not (isinstance(names, list) and len(names) >= 2 and all(isinstance(n, str) for n in names)):
            return "metadata.class_names must list >= 2 class names"
    return None


def validate_artifact(row: ModelVersion) -> ValidationResult:
    try:
        path = resolve_model_path(row.file_path)
    except ModelPathError as e:
        return ValidationResult(ModelStatus.INVALID, str(e), {})
    if path.suffix.lower() in UNSAFE_EXT:
        return ValidationResult(ModelStatus.INVALID, "Pickle-based checkpoints are not loaded for safety; export to ONNX/TorchScript", {})
    if row.format not in ALLOWED_EXT or path.suffix.lower() not in ALLOWED_EXT[row.format]:
        return ValidationResult(ModelStatus.INVALID, f"File extension {path.suffix} does not match format '{row.format}'", {})
    if not path.is_file():
        return ValidationResult(ModelStatus.FILE_MISSING, "Model file not found in models directory", {})
    mp = metadata_path(path)
    if not mp.is_file():
        return ValidationResult(ModelStatus.INVALID, f"Metadata sidecar missing: {mp.name}", {})
    try:
        meta = json.loads(mp.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return ValidationResult(ModelStatus.INVALID, "Metadata sidecar is not valid JSON", {})
    err = _validate_meta(row.model_type, meta)
    if err:
        return ValidationResult(ModelStatus.INVALID, err, meta)
    try:
        sha = sha256_file(path)
        rt = load_runtime(path, row.format)
    except RuntimeLoadError as e:
        msg = str(e)
        st = ModelStatus.ERROR if "not installed" in msg else ModelStatus.INVALID
        return ValidationResult(st, msg, meta)
    except Exception as e:  # noqa: BLE001
        return ValidationResult(ModelStatus.ERROR, f"Unexpected load error: {e}", meta)
    h, w = meta["input_size"]
    shp = getattr(rt, "input_shape", [])
    if len(shp) == 4:
        for dim, expect in ((2, h), (3, w)):
            if isinstance(shp[dim], int) and shp[dim] != expect:
                return ValidationResult(ModelStatus.INVALID, f"Model input shape {shp} conflicts with metadata input_size {[h, w]}", meta, sha256=sha)
    try:  # dummy forward pass: verify output shapes
        outs = list(rt.run(np.zeros((1, 3, h, w), dtype=np.float32)).values())
        if row.model_type == "patchcore":
            if not any(np.squeeze(o).ndim == 2 for o in outs):
                return ValidationResult(ModelStatus.INVALID, "No 2-D anomaly-map output found", meta, sha256=sha)
        else:
            if outs[0].reshape(-1).size != len(meta["class_names"]):
                return ValidationResult(ModelStatus.INVALID, "Output size does not match metadata.class_names", meta, sha256=sha)
    except Exception as e:  # noqa: BLE001
        return ValidationResult(ModelStatus.INVALID, f"Forward pass failed: {e}", meta, sha256=sha)
    return ValidationResult(ModelStatus.READY, "Artifact, metadata, input and output shapes verified", meta, rt.runtime, sha, rt)


@dataclass
class RealModels:
    patchcore: PatchCoreAdapter
    classifier: ClassifierAdapter | None
    version: str


class ModelRegistry:
    def __init__(self):
        self._cache: dict[int, tuple[tuple, object]] = {}
        self._lock = threading.Lock()

    def validate_and_store(self, db: Session, row: ModelVersion) -> ModelVersion:
        res = validate_artifact(row)
        row.status, row.status_detail = res.status, res.detail
        row.runtime, row.file_sha256 = res.runtime, res.sha256
        row.metadata_json = json.dumps(res.meta)
        row.last_validated_at = utcnow()
        with self._lock:
            self._cache.pop(row.id, None)
            if res.status == ModelStatus.READY:
                self._cache[row.id] = (self._stamp(row), self._build(row, res.meta, res.runtime_obj))
        return row

    @staticmethod
    def _stamp(row: ModelVersion) -> tuple:
        try:
            st = resolve_model_path(row.file_path).stat()
            return (st.st_mtime_ns, st.st_size)
        except (OSError, ModelPathError):
            return ()

    @staticmethod
    def _build(row: ModelVersion, meta: dict, rt):
        return PatchCoreAdapter(rt, meta) if row.model_type == "patchcore" else ClassifierAdapter(rt, meta)

    def _adapter(self, db: Session, model_id: int | None, kind: str, product: Product):
        """Return (adapter, error) for a model id."""
        if not model_id:
            return None, f"No {kind} model assigned to product '{product.name}'"
        row = db.get(ModelVersion, model_id)
        if row is None:
            return None, f"Assigned {kind} model no longer exists"
        if row.product_id != product.id:
            return None, f"{kind} model '{row.name}' is not validated for product '{product.name}' (compatibility check failed)"
        with self._lock:
            cached = self._cache.get(row.id)
        if cached is None or cached[0] != self._stamp(row):  # not loaded yet, or file changed on disk
            self.validate_and_store(db, row)
            db.commit()
            with self._lock:
                cached = self._cache.get(row.id)
        if row.status != ModelStatus.READY or cached is None:
            return None, f"{kind} model '{row.name}' is {row.status.value}: {row.status_detail}"
        return (cached[1], row), None

    def require_ready(self, db: Session, product: Product) -> RealModels:
        reasons: list[str] = []
        pc, err = self._adapter(db, product.patchcore_model_id, "PatchCore", product)
        if err:
            reasons.append(err)
        clf = None
        if product.classifier_model_id:
            clf, err2 = self._adapter(db, product.classifier_model_id, "classifier", product)
            if err2:
                reasons.append(err2)  # an explicitly assigned classifier must also be healthy
        if reasons:
            raise ModelNotReadyError(reasons)
        version = f"{pc[1].name}:{pc[1].version}" + (f" + {clf[1].name}:{clf[1].version}" if clf else "")
        return RealModels(pc[0], clf[0] if clf else None, version)

    def product_readiness(self, db: Session, product: Product) -> dict:
        try:
            m = self.require_ready(db, product)
            return {"ready": True, "version": m.version, "reasons": []}
        except ModelNotReadyError as e:
            return {"ready": False, "version": None, "reasons": e.reasons}

    def overall(self, db: Session) -> dict:
        prods = db.execute(select(Product).where(Product.archived.is_(False))).scalars().all()
        per = {p.id: {"product": p.name, **self.product_readiness(db, p)} for p in prods}
        return {"real_mode_available": any(v["ready"] for v in per.values()), "products": per}


registry = ModelRegistry()
