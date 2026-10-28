"""SHA-256 hash-chained, append-only audit log.

record_hash = SHA256(previous_hash + canonical_record_json)

NOTE: a hash chain gives tamper EVIDENCE, not tamper PREVENTION. A privileged actor with
write access to the database can rewrite the whole chain consistently. For stronger
guarantees, periodically anchor the latest hash externally (WORM storage, signed log, etc.).
"""
import hashlib
import json
import threading
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditEvent, Inspection
from app.utils.time import iso, utcnow

GENESIS_HASH = "0" * 64
_lock = threading.Lock()


def canonical_json(obj: dict) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def compute_hash(prev_hash: str, canonical: str) -> str:
    return hashlib.sha256((prev_hash + canonical).encode("utf-8")).hexdigest()


def inspection_payload(i: Inspection) -> dict:
    return {
        "inspection_id": i.id, "uid": i.uid, "timestamp": iso(i.created_at),
        "product_id": i.product_id, "product_code": i.product_code, "batch_id": i.batch_code,
        "line_id": i.line_id, "image_sha256": i.image_sha256, "anomaly_score": round(i.score, 6),
        "decision": i.decision.value, "defect_class": i.defect_class, "model_version": i.model_version,
        "review_threshold": i.review_threshold, "fail_threshold": i.fail_threshold, "mode": i.mode.value,
    }


def append_event(db: Session, event_type: str, inspection_id: int | None, payload: dict,
                 created_at: datetime | None = None) -> AuditEvent:
    """Append to the chain. Caller commits. A process-wide lock serialises chain growth."""
    with _lock:
        last = db.execute(select(AuditEvent).order_by(AuditEvent.seq.desc()).limit(1)).scalar_one_or_none()
        prev = last.record_hash if last else GENESIS_HASH
        seq = (last.seq + 1) if last else 1
        canonical = canonical_json(payload)
        ev = AuditEvent(seq=seq, event_type=event_type, inspection_id=inspection_id, payload_json=canonical,
                        prev_hash=prev, record_hash=compute_hash(prev, canonical), created_at=created_at or utcnow())
        db.add(ev)
        db.flush()
        return ev


def verify_chain(db: Session) -> dict:
    """Recompute the full chain and cross-check inspection rows against their audit payloads."""
    events = db.execute(select(AuditEvent).order_by(AuditEvent.seq)).scalars().all()
    prev, problems = GENESIS_HASH, []
    insp_cache: dict[int, Inspection] = {}
    for idx, ev in enumerate(events, start=1):
        if ev.seq != idx:
            problems.append({"seq": ev.seq, "problem": f"sequence gap (expected {idx})"})
        if ev.prev_hash != prev:
            problems.append({"seq": ev.seq, "problem": "prev_hash does not match previous record"})
        if compute_hash(ev.prev_hash, ev.payload_json) != ev.record_hash:
            problems.append({"seq": ev.seq, "problem": "record_hash mismatch (payload altered)"})
        if ev.event_type == "INSPECTION" and ev.inspection_id is not None:
            row = insp_cache.get(ev.inspection_id) or db.get(Inspection, ev.inspection_id)
            if row is None:
                problems.append({"seq": ev.seq, "problem": "inspection row missing/deleted"})
            else:
                try:
                    stored = json.loads(ev.payload_json)
                except ValueError:
                    stored = {}
                if canonical_json(inspection_payload(row)) != canonical_json(stored):
                    problems.append({"seq": ev.seq, "problem": "inspection row differs from audited record"})
        prev = ev.record_hash
    return {"valid": not problems, "events_checked": len(events), "head_hash": prev if events else GENESIS_HASH,
            "problems": problems, "verified_at": iso(utcnow()),
            "note": "A hash chain provides tamper evidence, not prevention; privileged DB access can rewrite it consistently."}
