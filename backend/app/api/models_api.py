import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ai.model_registry import ModelPathError, registry, resolve_model_path
from app.core.deps import get_current_user, require_roles
from app.database.session import get_db
from app.models import ModelStatus, ModelVersion, Product, User
from app.schemas.schemas import ModelOut, ModelRegisterIn

router = APIRouter(prefix="/api/models", tags=["models"])


def _out(m: ModelVersion) -> ModelOut:
    try:
        meta = json.loads(m.metadata_json or "{}")
    except ValueError:
        meta = {}
    keep = {k: meta[k] for k in ("input_size", "class_names", "score_min", "score_max", "min_confidence") if k in meta}
    return ModelOut(id=m.id, name=m.name, version=m.version, model_type=m.model_type, format=m.format,
                    file_name=m.file_path.replace("\\", "/").split("/")[-1], product_id=m.product_id, status=m.status,
                    status_detail=m.status_detail, runtime=m.runtime, last_validated_at=m.last_validated_at,
                    metadata_summary=keep, created_at=m.created_at)


@router.get("", response_model=list[ModelOut])
def list_models(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return [_out(m) for m in db.execute(select(ModelVersion).order_by(ModelVersion.id.desc())).scalars()]


@router.get("/status")
def status(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    o = registry.overall(db)
    n = db.query(ModelVersion).count()
    return {**o, "registered_models": n,
            "message": ("Real AI PatchCore inference is active for supported products." if o["real_mode_available"] else
                        "Real AI mode is unconfigured: no product has valid model artifacts.")}


@router.post("/register", response_model=ModelOut, status_code=201)
def register(body: ModelRegisterIn, _: User = Depends(require_roles()), db: Session = Depends(get_db)):
    """Register a local artifact (path must be inside the models directory) and validate it immediately.
    Registration never fabricates readiness: status reflects the real file/metadata/runtime checks."""
    try:
        resolve_model_path(body.file_path)
    except ModelPathError as e:
        raise HTTPException(422, str(e))
    prod = db.get(Product, body.product_id) if body.product_id else None
    if body.product_id and not prod:
        raise HTTPException(404, "Product not found")
    if body.assign_to_product and not prod:
        raise HTTPException(422, "assign_to_product requires product_id")
    m = ModelVersion(name=body.name, version=body.version, model_type=body.model_type, format=body.format,
                     file_path=body.file_path, product_id=body.product_id, status=ModelStatus.NOT_CONFIGURED)
    db.add(m)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A model with this name and version is already registered")
    registry.validate_and_store(db, m)
    if body.assign_to_product and prod:
        if m.model_type == "patchcore":
            prod.patchcore_model_id = m.id
        else:
            prod.classifier_model_id = m.id
    db.commit()
    return _out(m)


@router.post("/{mid}/validate", response_model=ModelOut)
def revalidate(mid: int, _: User = Depends(require_roles()), db: Session = Depends(get_db)):
    m = db.get(ModelVersion, mid)
    if not m:
        raise HTTPException(404, "Model not found")
    registry.validate_and_store(db, m)
    db.commit()
    return _out(m)
