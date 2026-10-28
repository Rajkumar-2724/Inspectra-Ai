"""Bounded in-process job queue for batch inspection (suitable for local/hackathon use).
Job state is persisted in the DB so partial failures never lose completed inspections."""
import logging
import queue
import threading

from sqlalchemy import select

from app.ai.model_registry import ModelNotReadyError
from app.ai.preprocessing import ImageValidationError
from app.core.config import get_settings
from app.database.session import SessionLocal
from app.models import BatchJob, InspectionBatch, JobStatus
from app.services.inspection_service import InspectionError, run_inspection, storage_file

log = logging.getLogger("batch")
_q: queue.Queue | None = None
_threads: list[threading.Thread] = []


def process_job(job_id: int) -> None:
    db = SessionLocal()
    try:
        job = db.get(BatchJob, job_id)
        if job is None or job.status == JobStatus.DONE:
            return
        job.status, job.attempts, job.error = JobStatus.PROCESSING, job.attempts + 1, ""
        db.commit()
        batch = db.get(InspectionBatch, job.batch_id)
        try:
            data = storage_file(job.file_path).read_bytes()
            insp = run_inspection(db, user_id=batch.created_by, product=batch.product, data=data, mode="real",
                                  scenario=None, product_code=job.filename[:64], batch=batch)
            job = db.get(BatchJob, job_id)
            job.status, job.inspection_id = JobStatus.DONE, insp.id
        except (ImageValidationError, InspectionError, ModelNotReadyError, ValueError) as e:
            db.rollback()
            job = db.get(BatchJob, job_id)
            job.status, job.error = JobStatus.FAILED, str(e)[:500]
        except Exception:  # noqa: BLE001
            log.exception("batch job %s crashed", job_id)
            db.rollback()
            job = db.get(BatchJob, job_id)
            job.status, job.error = JobStatus.FAILED, "Internal error while processing this image"
        db.commit()
    finally:
        db.close()


def _worker():
    while True:
        job_id = _q.get()
        try:
            process_job(job_id)
        except Exception:  # noqa: BLE001
            log.exception("worker error")
        finally:
            _q.task_done()


def start_workers() -> None:
    global _q
    s = get_settings()
    if _q is not None:
        return
    _q = queue.Queue(maxsize=s.BATCH_QUEUE_SIZE)
    for n in range(max(1, s.BATCH_WORKERS)):
        t = threading.Thread(target=_worker, name=f"batch-worker-{n}", daemon=True)
        t.start()
        _threads.append(t)
    db = SessionLocal()  # recover jobs interrupted by a restart
    try:
        for job in db.execute(select(BatchJob).where(BatchJob.status.in_([JobStatus.QUEUED, JobStatus.PROCESSING]))).scalars():
            job.status = JobStatus.QUEUED
            try:
                _q.put_nowait(job.id)
            except queue.Full:
                job.status, job.error = JobStatus.FAILED, "Queue full on restart; retry"
        db.commit()
    finally:
        db.close()


def enqueue(job_id: int) -> bool:
    """Returns False if the bounded queue is full (caller marks the job FAILED/retryable)."""
    if get_settings().BATCH_INLINE:
        process_job(job_id)
        return True
    if _q is None:
        start_workers()
    try:
        _q.put_nowait(job_id)
        return True
    except queue.Full:
        return False
