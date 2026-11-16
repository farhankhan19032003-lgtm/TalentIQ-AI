import io

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.errors import AppError
from ..models import db as M
from ..schemas.api import AnalyzeIn, JobIn
from ..services import pipeline
from ..services.security import sanitize_filename
from .deps import require_access
from .views import job_out

router = APIRouter(prefix="/jobs", tags=["jobs"], dependencies=[Depends(require_access)])


def _get(db, job_id) -> M.Job:
    j = db.get(M.Job, job_id)
    if not j:
        raise AppError("Job not found.", 404, "not_found")
    return j


def _apply(job: M.Job, body: JobIn):
    a = pipeline.build_job_analysis(body.description, body.title)
    if body.requirements is not None:
        reqs = pipeline.normalize_requirements([r.model_dump() for r in body.requirements])
    else:
        reqs = [dict(r) for r in a["requirements"]]
    reqs = pipeline.merge_user_skills(reqs, body.required_skills, body.optional_skills)
    job.title, job.role, job.category, job.description = body.title.strip(), body.role, body.category, body.description
    job.analysis = a
    job.requirements = reqs
    job.min_experience_years = body.min_experience_years if body.min_experience_years is not None else a["experience"]["min_years"]
    job.preferred_experience_years = body.preferred_experience_years if body.preferred_experience_years is not None else a["experience"]["preferred_years"]
    job.education_level = body.education_level if body.education_level is not None else a["education"]["required_level"]
    job.preferred_education_level = body.preferred_education_level if body.preferred_education_level is not None else a["education"]["preferred_level"]
    job.is_template = body.is_template


@router.post("/analyze")
def analyze(body: AnalyzeIn):
    """Preview AI extraction before saving; recruiters can then correct requirements."""
    return pipeline.build_job_analysis(body.description, body.title)


@router.post("/extract-text")
async def extract_text(file: UploadFile = File(...)):
    data = await file.read()
    name = sanitize_filename(file.filename or "")
    if len(data) > 2 * 1024 * 1024:
        raise AppError("Job description file exceeds 2 MB.", 413, "file_too_large")
    if name.lower().endswith(".txt"):
        text = data.decode("utf-8", errors="replace")
    elif name.lower().endswith((".docx", ".pdf")):
        # the same safety checks and parsers as resume uploads (magic bytes, size/page limits, active content, OCR for scanned PDFs)
        from ..services.document_parser import DocumentError, parse_docx, parse_pdf
        from ..services.security import UploadRejected, validate_upload
        try:
            validate_upload(name, data)
            text = (parse_pdf if name.lower().endswith(".pdf") else parse_docx)(data).text
        except (UploadRejected, DocumentError) as e:
            raise AppError(getattr(e, "message", str(e)), 400, "invalid_document")
    else:
        raise AppError("Only .txt, .docx and .pdf job descriptions are supported.", 400, "unsupported_type")
    return {"filename": name, "text": text.strip(), "analysis": pipeline.build_job_analysis(text, None)}


@router.post("", status_code=201)
def create(body: JobIn, db: Session = Depends(get_db)):
    j = M.Job()
    _apply(j, body)
    db.add(j)
    db.flush()
    pipeline.audit(db, "job.created", "job", j.id, {"requirements": len(j.requirements)})
    db.commit()
    return job_out(j)


@router.get("")
def list_jobs(templates: bool | None = None, page: int = 1, page_size: int = 50, db: Session = Depends(get_db)):
    page_size = max(1, min(page_size, 100))
    q = select(M.Job).order_by(M.Job.id.desc())
    if templates is not None:
        q = q.where(M.Job.is_template == templates)
    items = list(db.scalars(q))
    total = len(items)
    sl = items[(max(page, 1) - 1) * page_size: max(page, 1) * page_size]
    return {"total": total, "page": page, "page_size": page_size, "items": [job_out(j) for j in sl]}


@router.get("/{job_id}")
def get_job(job_id: int, db: Session = Depends(get_db)):
    return job_out(_get(db, job_id))


@router.put("/{job_id}")
def update(job_id: int, body: JobIn, db: Session = Depends(get_db)):
    j = _get(db, job_id)
    if not body.reanalyze and body.requirements is None:
        body.requirements = [__import__("app.schemas.api", fromlist=["RequirementIn"]).RequirementIn(**r) for r in j.requirements]
    _apply(j, body)
    pipeline.audit(db, "job.updated", "job", j.id, {"requirements": len(j.requirements)})
    db.commit()
    return job_out(j)


@router.delete("/{job_id}", status_code=204)
def delete(job_id: int, db: Session = Depends(get_db)):
    j = _get(db, job_id)
    db.delete(j)
    pipeline.audit(db, "job.deleted", "job", job_id, {})
    db.commit()
