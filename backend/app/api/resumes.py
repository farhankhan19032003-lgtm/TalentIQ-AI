import uuid

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.database import get_db
from ..core.errors import AppError
from ..models import db as M
from ..services import pipeline
from ..services.security import read_stored
from .deps import require_access

router = APIRouter(prefix="/resumes", tags=["resumes"], dependencies=[Depends(require_access)])


def _out(r: M.Resume, blind: bool = False) -> dict:
    return {"id": r.id, "batch_id": r.batch_id, "filename": f"resume_{r.id}.{r.file_type}" if blind else r.original_filename, "file_type": r.file_type,
            "file_size": r.file_size, "status": r.status, "error_code": r.error_code, "error_message": r.error_message,
            "page_count": r.page_count, "candidate_id": r.candidate_id, "processing_ms": r.processing_ms, "created_at": r.created_at.isoformat(),
            "diagnostics": r.diagnostics}


@router.post("/upload")
async def upload(files: list[UploadFile] = File(...), db: Session = Depends(get_db)):
    """Batch upload. Each file is validated and processed in isolation - one bad file never fails the batch."""
    if len(files) > settings.max_batch_files:
        raise AppError(f"A batch may contain at most {settings.max_batch_files} files.", 413, "batch_too_large")
    batch = uuid.uuid4().hex[:12]
    results = []
    for f in files:
        data = await f.read(int(settings.max_upload_mb * 1024 * 1024) + 1)
        try:
            results.append(pipeline.ingest_resume(db, f.filename or "unnamed", data, batch))
        except Exception:  # defence in depth: record and continue
            db.rollback()
            results.append({"filename": f.filename, "status": "failed", "error_code": "processing_error", "error_message": "Unexpected processing error.", "resume_id": None})
    summary = {s: sum(1 for r in results if r["status"] == s) for s in ("parsed", "failed", "duplicate", "rejected")}
    return {"batch_id": batch, "total": len(results), "summary": summary, "results": results}


@router.get("")
def list_resumes(status: str | None = None, batch_id: str | None = None, page: int = 1, page_size: int = 50, blind: bool = False,
                 db: Session = Depends(get_db)):
    page_size = max(1, min(page_size, 100))
    q = select(M.Resume)
    if status:
        q = q.where(M.Resume.status == status)
    if batch_id:
        q = q.where(M.Resume.batch_id == batch_id)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.scalars(q.order_by(M.Resume.id.desc()).offset((max(page, 1) - 1) * page_size).limit(page_size))
    return {"total": total, "page": page, "page_size": page_size, "items": [_out(r, blind) for r in rows]}


@router.get("/stats")
def stats(db: Session = Depends(get_db)):
    total = db.scalar(select(func.count(M.Resume.id)))
    by = dict(db.execute(select(M.Resume.status, func.count()).group_by(M.Resume.status)).all())
    errs = dict(db.execute(select(M.Resume.error_code, func.count()).where(M.Resume.status == "failed").group_by(M.Resume.error_code)).all())
    return {"total": total, "parsed": by.get("parsed", 0), "failed": by.get("failed", 0),
            "success_rate": round(by.get("parsed", 0) / total * 100, 1) if total else None, "failures_by_reason": errs}


@router.get("/batches/{batch_id}")
def batch_status(batch_id: str, db: Session = Depends(get_db)):
    rs = list(db.scalars(select(M.Resume).where(M.Resume.batch_id == batch_id).order_by(M.Resume.id)))
    if not rs:
        raise AppError("Batch not found.", 404, "not_found")
    return {"batch_id": batch_id, "total": len(rs), "parsed": sum(r.status == "parsed" for r in rs), "failed": sum(r.status == "failed" for r in rs),
            "items": [_out(r) for r in rs]}


@router.get("/{resume_id}")
def get_resume(resume_id: int, blind: bool = False, db: Session = Depends(get_db)):
    r = db.get(M.Resume, resume_id)
    if not r:
        raise AppError("Resume not found.", 404, "not_found")
    return _out(r, blind)


@router.post("/{resume_id}/retry")
def retry(resume_id: int, db: Session = Depends(get_db)):
    r = db.get(M.Resume, resume_id)
    if not r:
        raise AppError("Resume not found.", 404, "not_found")
    if r.status != "failed":
        raise AppError("Only failed resumes can be retried.", 409, "not_failed")
    data = read_stored(r.stored_filename) if r.stored_filename else None
    if data is None:
        raise AppError("The original file is not stored, so it cannot be retried. Please re-upload it.", 409, "file_unavailable")
    pipeline.process_resume_record(db, r, data)
    pipeline.audit(db, "resume.retried", "resume", r.id, {"status": r.status, "error": r.error_code})
    db.commit()
    return _out(r)


@router.delete("/{resume_id}", status_code=204)
def delete(resume_id: int, db: Session = Depends(get_db)):
    r = db.get(M.Resume, resume_id)
    if not r:
        raise AppError("Resume not found.", 404, "not_found")
    pipeline.delete_resume(db, r)
