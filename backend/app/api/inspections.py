from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.ai.model_registry import ModelNotReadyError
from app.ai.preprocessing import ImageValidationError
from app.core.config import get_settings
from app.core.deps import get_current_user, require_roles
from app.database.session import get_db
from app.models import Decision, Inspection, Mode, Product, ReviewStatus, Role, User
from app.schemas.schemas import InspectionOut, InspectionPage
from app.services import reports
from app.services.inspection_service import InspectionError, run_inspection, storage_file, to_out

router = APIRouter(prefix="/api", tags=["inspections"])
inspector = require_roles(Role.inspector)


def real_unavailable(e: ModelNotReadyError) -> HTTPException:
    return HTTPException(409, {"code": "REAL_MODE_UNAVAILABLE", "message": "Inference unavailable: required AI model is not ready.", "reasons": e.reasons})


@router.post("/inspect", response_model=InspectionOut, status_code=201)
async def inspect(file: UploadFile = File(...), product_id: int = Form(...), mode: str = Form("real"),
                  scenario: str | None = Form(None), product_code: str = Form(""), batch_code: str = Form(""),
                  line_id: str = Form(""), notes: str = Form(""), user: User = Depends(inspector), db: Session = Depends(get_db)):
    if mode != "real":
        raise HTTPException(422, "Only 'real' inference mode is supported. Demo mode has been removed.")
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(404, "Product not found")
    s = get_settings()
    data = await file.read(s.MAX_UPLOAD_MB * 1024 * 1024 + 1)
    try:
        insp = run_inspection(db, user_id=user.id, product=product, data=data, mode="real",
                              product_code=product_code, batch_code=batch_code, line_id=line_id, notes=notes)
    except ImageValidationError as e:
        raise HTTPException(422, str(e))
    except ModelNotReadyError as e:
        raise real_unavailable(e)
    except InspectionError as e:
        raise HTTPException(422, str(e))
    return to_out(insp)


def _filtered(q, decision, mode, product_id, batch_code, line_id, review_status, search, date_from, date_to):
    if decision:
        q = q.where(Inspection.decision == Decision(decision))
    if mode:
        q = q.where(Inspection.mode == Mode(mode))
    if product_id:
        q = q.where(Inspection.product_id == product_id)
    if batch_code:
        q = q.where(Inspection.batch_code == batch_code)
    if line_id:
        q = q.where(Inspection.line_id == line_id)
    if review_status:
        q = q.where(Inspection.review_status == ReviewStatus(review_status))
    if search:
        like = f"%{search}%"
        q = q.where(or_(Inspection.uid.like(like), Inspection.product_code.like(like), Inspection.batch_code.like(like),
                        Inspection.defect_class.like(like)))
    if date_from:
        q = q.where(Inspection.created_at >= date_from)
    if date_to:
        q = q.where(Inspection.created_at <= date_to)
    return q


@router.get("/inspections", response_model=InspectionPage)
def list_inspections(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200), decision: str | None = Query(None, pattern="^(PASS|REVIEW|FAIL)$"),
                     mode: str | None = Query(None, pattern="^(demo|real)$"), product_id: int | None = None, batch_code: str | None = None,
                     line_id: str | None = None, review_status: str | None = Query(None, pattern="^(NONE|PENDING|REVIEWED|REINSPECT)$"),
                     search: str | None = None, date_from: datetime | None = None, date_to: datetime | None = None,
                     _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = _filtered(select(Inspection), decision, mode, product_id, batch_code, line_id, review_status, search, date_from, date_to)
    total = db.scalar(select(__import__("sqlalchemy").func.count()).select_from(q.subquery())) or 0
    rows = db.execute(q.order_by(Inspection.id.desc()).offset((page - 1) * page_size).limit(page_size)).scalars().all()
    return InspectionPage(items=[to_out(r) for r in rows], total=total, page=page, page_size=page_size)


@router.get("/inspections/export/csv")
def export_csv(decision: str | None = Query(None, pattern="^(PASS|REVIEW|FAIL)$"), mode: str | None = Query(None, pattern="^(demo|real)$"),
               product_id: int | None = None, batch_code: str | None = None, line_id: str | None = None, search: str | None = None,
               _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = _filtered(select(Inspection), decision, mode, product_id, batch_code, line_id, None, search, None, None)
    rows = db.execute(q.order_by(Inspection.id.desc()).limit(50000)).scalars().all()
    return Response(reports.csv_bytes(rows), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="inspections.csv"'})


def _get(db: Session, iid: int) -> Inspection:
    i = db.get(Inspection, iid)
    if not i:
        raise HTTPException(404, "Inspection not found")
    return i


@router.get("/inspections/{iid}", response_model=InspectionOut)
def get_inspection(iid: int, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return to_out(_get(db, iid))


@router.get("/inspections/{iid}/images")
def list_images(iid: int, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    i = _get(db, iid)
    return [{"kind": im.kind, "width": im.width, "height": im.height, "url": f"/api/inspections/{i.id}/images/{im.kind}"} for im in i.images]


@router.get("/inspections/{iid}/images/{kind}")
def get_image(iid: int, kind: str, download: bool = False, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    i = _get(db, iid)
    im = next((x for x in i.images if x.kind == kind), None)
    if not im:
        raise HTTPException(404, "Image not available for this inspection")
    path = storage_file(im.path)
    if not path.is_file():
        raise HTTPException(404, "Image file missing from storage")
    return FileResponse(path, filename=f"inspection-{i.id}-{kind}{path.suffix}" if download else None)


@router.get("/inspections/{iid}/report")
def inspection_report(iid: int, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    i = _get(db, iid)
    return Response(reports.inspection_pdf(db, i), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="inspection-{i.id}.pdf"'})
