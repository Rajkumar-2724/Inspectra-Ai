import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.model_registry import registry
from app.core.config import get_settings
from app.core.deps import get_current_user, require_roles
from app.database.session import get_db
from app.models import BatchJob, Inspection, InspectionBatch, JobStatus, Mode, Product, Role, User
from app.schemas.schemas import BatchIn, BatchOut, InspectionOut
from app.services import batch_queue, reports
from app.services.inspection_service import storage_file, to_out

router = APIRouter(prefix="/api/batches", tags=["batches"])
inspector = require_roles(Role.inspector)
MAX_FILES = 200


def _out(db: Session, b: InspectionBatch, with_jobs=True) -> BatchOut:
    jobs = db.execute(select(BatchJob).where(BatchJob.batch_id == b.id).order_by(BatchJob.id)).scalars().all()
    ids = [j.inspection_id for j in jobs if j.inspection_id]
    insp = db.execute(select(Inspection).where(Inspection.id.in_(ids))).scalars().all() if ids else []
    counts = {k: sum(1 for i in insp if i.decision.value == k) for k in ("PASS", "REVIEW", "FAIL")}
    jc = {s.value: sum(1 for j in jobs if j.status == s) for s in JobStatus}
    done = jc["DONE"] + jc["FAILED"]
    return BatchOut(id=b.id, batch_code=b.batch_code, product_id=b.product_id, product_name=b.product.name, line_id=b.line_id,
                    mode=b.mode.value, scenario=b.scenario, created_at=b.created_at, total=len(jobs), counts=counts, job_counts=jc,
                    progress=round(done / len(jobs), 4) if jobs else 0.0, jobs=jobs if with_jobs else [])


def _batch(db: Session, bid: int) -> InspectionBatch:
    b = db.get(InspectionBatch, bid)
    if not b:
        raise HTTPException(404, "Batch not found")
    return b


@router.get("", response_model=list[BatchOut])
def list_batches(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.execute(select(InspectionBatch).order_by(InspectionBatch.id.desc()).limit(100)).scalars().all()
    return [_out(db, b, with_jobs=False) for b in rows]


@router.post("", response_model=BatchOut, status_code=201)
def create_batch(body: BatchIn, user: User = Depends(inspector), db: Session = Depends(get_db)):
    p = db.get(Product, body.product_id)
    if not p or p.archived:
        raise HTTPException(404, "Product not found or archived")
    r = registry.product_readiness(db, p)
    if not r["ready"]:
        raise HTTPException(409, {"code": "REAL_MODE_UNAVAILABLE", "message": f"Real AI mode unavailable for product '{p.name}'", "reasons": r["reasons"]})
    b = InspectionBatch(batch_code=body.batch_code, product_id=p.id, line_id=body.line_id, mode=Mode.real,
                        scenario=None, created_by=user.id)
    db.add(b)
    db.commit()
    return _out(db, b)


@router.post("/{bid}/inspect", response_model=BatchOut, status_code=202)
async def batch_inspect(bid: int, files: list[UploadFile] = File(...), _: User = Depends(inspector), db: Session = Depends(get_db)):
    """Queue images. Validation happens per job so a bad file never blocks the others."""
    b = _batch(db, bid)
    if not files or len(files) > MAX_FILES:
        raise HTTPException(422, f"Provide 1-{MAX_FILES} files per request")
    s = get_settings()
    # Fail fast for real mode so users are not given a queue of guaranteed failures
    if b.mode == Mode.real:
        from app.ai.model_registry import registry
        r = registry.product_readiness(db, b.product)
        if not r["ready"]:
            raise HTTPException(409, {"code": "REAL_MODE_UNAVAILABLE", "message": "Real AI mode unavailable for this product", "reasons": r["reasons"]})
    updir = storage_file(f"batches/{b.id}/uploads")
    updir.mkdir(parents=True, exist_ok=True)
    job_ids = []
    for f in files:
        data = await f.read(s.MAX_UPLOAD_MB * 1024 * 1024 + 1)
        name = Path(f.filename or "image").name[:120]
        stored = f"{uuid.uuid4().hex}.bin"  # secure generated name; never trust client filename on disk
        (updir / stored).write_bytes(data)
        job = BatchJob(batch_id=b.id, filename=name, file_path=f"batches/{b.id}/uploads/{stored}")
        db.add(job)
        db.flush()
        job_ids.append(job.id)
    db.commit()
    for jid in job_ids:
        if not batch_queue.enqueue(jid):
            j = db.get(BatchJob, jid)
            j.status, j.error = JobStatus.FAILED, "Queue is full; retry later"
            db.commit()
    return _out(db, b)


@router.post("/{bid}/retry", response_model=BatchOut, status_code=202)
def retry_failed(bid: int, _: User = Depends(inspector), db: Session = Depends(get_db)):
    b = _batch(db, bid)
    failed = db.execute(select(BatchJob).where(BatchJob.batch_id == b.id, BatchJob.status == JobStatus.FAILED)).scalars().all()
    for j in failed:
        j.status, j.error = JobStatus.QUEUED, ""
    db.commit()
    for j in failed:
        if not batch_queue.enqueue(j.id):
            j.status, j.error = JobStatus.FAILED, "Queue is full; retry later"
            db.commit()
    return _out(db, b)


@router.get("/{bid}", response_model=BatchOut)
def get_batch(bid: int, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _out(db, _batch(db, bid))


@router.get("/{bid}/status")
def batch_status(bid: int, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    o = _out(db, _batch(db, bid))
    return {"id": o.id, "progress": o.progress, "job_counts": o.job_counts, "counts": o.counts, "total": o.total,
            "finished": o.total > 0 and o.job_counts["QUEUED"] + o.job_counts["PROCESSING"] == 0}


def _items(db: Session, b: InspectionBatch) -> list[Inspection]:
    return db.execute(select(Inspection).where(Inspection.batch_id == b.id).order_by(Inspection.id)).scalars().all()


@router.get("/{bid}/inspections", response_model=list[InspectionOut])
def batch_inspections(bid: int, decision: str | None = None, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = _items(db, _batch(db, bid))
    return [to_out(i) for i in items if not decision or i.decision.value == decision]


@router.get("/{bid}/report")
def batch_report(bid: int, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    b = _batch(db, bid)
    return Response(reports.batch_pdf(db, b, _items(db, b)), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="batch-{b.id}.pdf"'})


@router.get("/{bid}/export/csv")
def batch_csv(bid: int, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    b = _batch(db, bid)
    return Response(reports.csv_bytes(_items(db, b)), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="batch-{b.id}.csv"'})
