import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_roles
from app.database.session import get_db
from app.models import AuditEvent, User
from app.services.audit import verify_chain
from app.utils.time import iso

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("/events")
def events(page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=200), event_type: str | None = Query(None, pattern="^(INSPECTION|REVIEW)$"),
           inspection_id: int | None = None, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = select(AuditEvent)
    if event_type:
        q = q.where(AuditEvent.event_type == event_type)
    if inspection_id:
        q = q.where(AuditEvent.inspection_id == inspection_id)
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.execute(q.order_by(AuditEvent.seq.desc()).offset((page - 1) * page_size).limit(page_size)).scalars().all()
    return {"total": total, "page": page, "page_size": page_size, "items": [
        {"id": r.id, "seq": r.seq, "event_type": r.event_type, "inspection_id": r.inspection_id, "payload": json.loads(r.payload_json),
         "prev_hash": r.prev_hash, "record_hash": r.record_hash, "created_at": iso(r.created_at)} for r in rows]}


@router.get("/verify")
def verify(_: User = Depends(require_roles()), db: Session = Depends(get_db)):
    return verify_chain(db)
