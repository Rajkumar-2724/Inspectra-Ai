from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ai.decision_engine import DecisionEngine, ThresholdError
from app.ai.model_registry import registry
from app.ai.preprocessing import ImageValidationError, validate_image_bytes
from app.core.config import get_settings
from app.core.deps import get_current_user, require_roles
from app.database.session import get_db
from app.models import Inspection, ModelVersion, Product, ProductDefectClass, User
from app.schemas.schemas import CATEGORIES, ProductIn, ProductOut, ProductPatch
from app.services.inspection_service import storage_file

router = APIRouter(prefix="/api/products", tags=["products"])


def _out(db: Session, p: Product) -> ProductOut:
    count = db.scalar(select(func.count(Inspection.id)).where(Inspection.product_id == p.id)) or 0
    return ProductOut(id=p.id, name=p.name, category=p.category, description=p.description,
                      review_threshold=p.review_threshold, fail_threshold=p.fail_threshold,
                      patchcore_model_id=p.patchcore_model_id, classifier_model_id=p.classifier_model_id,
                      archived=p.archived, has_reference_image=bool(p.reference_image_path),
                      defect_classes=[c.name for c in p.defect_classes], inspection_count=count,
                      real_mode_ready=registry.product_readiness(db, p)["ready"], created_at=p.created_at)


def _check_model(db: Session, model_id: int | None, product: Product | None, expect_type: str):
    if model_id is None:
        return
    m = db.get(ModelVersion, model_id)
    if not m or m.model_type != expect_type:
        raise HTTPException(422, f"Model {model_id} not found or not a {expect_type} model")
    if product is not None and m.product_id not in (None, product.id):
        raise HTTPException(422, "Model is registered for a different product (incompatible)")


@router.get("/categories")
def categories(_: User = Depends(get_current_user)):
    return CATEGORIES


@router.get("", response_model=list[ProductOut])
def list_products(include_archived: bool = False, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = select(Product).order_by(Product.name)
    if not include_archived:
        q = q.where(Product.archived.is_(False))
    return [_out(db, p) for p in db.execute(q).scalars().all()]


@router.post("", response_model=ProductOut, status_code=201)
def create_product(body: ProductIn, _: User = Depends(require_roles()), db: Session = Depends(get_db)):
    try:
        DecisionEngine.validate_thresholds(body.review_threshold, body.fail_threshold)
    except ThresholdError as e:
        raise HTTPException(422, str(e))
    p = Product(name=body.name.strip(), category=body.category, description=body.description,
                review_threshold=body.review_threshold, fail_threshold=body.fail_threshold)
    p.defect_classes = [ProductDefectClass(name=n) for n in body.defect_classes]
    db.add(p)
    try:
        db.flush()
        _check_model(db, body.patchcore_model_id, p, "patchcore")
        _check_model(db, body.classifier_model_id, p, "classifier")
        p.patchcore_model_id, p.classifier_model_id = body.patchcore_model_id, body.classifier_model_id
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A product with this name already exists")
    except HTTPException:
        db.rollback()
        raise
    return _out(db, p)


@router.get("/{pid}", response_model=ProductOut)
def get_product(pid: int, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.get(Product, pid)
    if not p:
        raise HTTPException(404, "Product not found")
    return _out(db, p)


@router.patch("/{pid}", response_model=ProductOut)
def patch_product(pid: int, body: ProductPatch, _: User = Depends(require_roles()), db: Session = Depends(get_db)):
    p = db.get(Product, pid)
    if not p:
        raise HTTPException(404, "Product not found")
    review = body.review_threshold if body.review_threshold is not None else p.review_threshold
    fail = body.fail_threshold if body.fail_threshold is not None else p.fail_threshold
    try:
        DecisionEngine.validate_thresholds(review, fail)
    except ThresholdError as e:
        raise HTTPException(422, str(e))
    p.review_threshold, p.fail_threshold = review, fail
    for f in ("name", "category", "description", "archived"):
        v = getattr(body, f)
        if v is not None:
            setattr(p, f, v)
    if body.defect_classes is not None:
        names = list(dict.fromkeys(n.strip().lower().replace(" ", "_") for n in body.defect_classes if n.strip()))
        p.defect_classes = [ProductDefectClass(name=n) for n in names if n != "unknown_defect"]
    if body.clear_patchcore_model:
        p.patchcore_model_id = None
    elif body.patchcore_model_id is not None:
        _check_model(db, body.patchcore_model_id, p, "patchcore")
        p.patchcore_model_id = body.patchcore_model_id
    if body.clear_classifier_model:
        p.classifier_model_id = None
    elif body.classifier_model_id is not None:
        _check_model(db, body.classifier_model_id, p, "classifier")
        p.classifier_model_id = body.classifier_model_id
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A product with this name already exists")
    return _out(db, p)


@router.delete("/{pid}", response_model=ProductOut)
def archive_product(pid: int, _: User = Depends(require_roles()), db: Session = Depends(get_db)):
    """Products are archived (never hard-deleted) so audited inspection history stays intact."""
    p = db.get(Product, pid)
    if not p:
        raise HTTPException(404, "Product not found")
    p.archived = True
    db.commit()
    return _out(db, p)


@router.post("/{pid}/reference-image", response_model=ProductOut)
async def upload_reference(pid: int, file: UploadFile = File(...), _: User = Depends(require_roles()), db: Session = Depends(get_db)):
    p = db.get(Product, pid)
    if not p:
        raise HTTPException(404, "Product not found")
    s = get_settings()
    data = await file.read(s.MAX_UPLOAD_MB * 1024 * 1024 + 1)
    try:
        img, _ext = validate_image_bytes(data, s.MAX_UPLOAD_MB * 1024 * 1024)
    except ImageValidationError as e:
        raise HTTPException(422, str(e))
    rel = f"products/{p.id}/reference.png"
    path = storage_file(rel)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(path, "PNG")
    p.reference_image_path = rel
    db.commit()
    return _out(db, p)


@router.get("/{pid}/reference-image")
def get_reference(pid: int, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.get(Product, pid)
    if not p or not p.reference_image_path:
        raise HTTPException(404, "No reference image")
    return FileResponse(storage_file(p.reference_image_path), media_type="image/png")
