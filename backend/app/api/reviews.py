from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_roles
from app.database.session import get_db
from app.models import Decision, Inspection, ReviewAction, ReviewDecision, ReviewStatus, Role, User
from app.schemas.schemas import InspectionOut, ReviewIn
from app.services import audit
from app.services.events import hub
from app.services.inspection_service import to_out
from app.utils.time import iso, utcnow

router = APIRouter(prefix="/api/reviews", tags=["reviews"])


@router.get("/pending", response_model=list[InspectionOut])
def pending(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.execute(select(Inspection).where(Inspection.review_status == ReviewStatus.PENDING).order_by(Inspection.id)).scalars().all()
    return [to_out(r) for r in rows]


@router.post("/{inspection_id}/decision", response_model=InspectionOut)
def decide(inspection_id: int, body: ReviewIn, user: User = Depends(require_roles(Role.reviewer)), db: Session = Depends(get_db)):
    """Records a human decision. The original AI decision/score fields are never modified."""
    i = db.get(Inspection, inspection_id)
    if not i:
        raise HTTPException(404, "Inspection not found")
    if i.review_status != ReviewStatus.PENDING:
        raise HTTPException(409, "This inspection is not awaiting review")
    if body.decision == ReviewDecision.reject and not body.comment.strip():
        raise HTTPException(422, "A comment is required when rejecting a product")
    now = utcnow()
    name = user.full_name or user.username
    db.add(ReviewAction(inspection_id=i.id, reviewer_id=user.id, reviewer_name=name, decision=body.decision, comment=body.comment, created_at=now))
    if body.decision == ReviewDecision.approve:
        i.final_decision, i.review_status = Decision.PASS, ReviewStatus.REVIEWED
    elif body.decision == ReviewDecision.reject:
        i.final_decision, i.review_status = Decision.FAIL, ReviewStatus.REVIEWED
    else:
        i.final_decision, i.review_status = None, ReviewStatus.REINSPECT
    audit.append_event(db, "REVIEW", i.id, {"inspection_id": i.id, "uid": i.uid, "reviewer_id": user.id, "reviewer": name,
                                            "decision": body.decision.value, "comment": body.comment, "timestamp": iso(now),
                                            "original_ai_decision": i.decision.value}, created_at=now)
    db.commit()
    db.refresh(i)
    hub.publish({"type": "review", "id": i.id, "decision": body.decision.value})
    return to_out(i)
