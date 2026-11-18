from pathlib import Path
import os
import importlib.util
from collections import Counter
from datetime import date

from fastapi import APIRouter, Depends, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.config import ALGORITHM_VERSION, COMPONENT_LABELS, COMPONENTS, DEFAULT_WEIGHTS, ROOT_DIR, settings
from ..core.database import get_db
from ..core.errors import AppError
from ..models import db as M
from ..schemas.api import LoginIn, SavedSearchIn
from ..services import exports, pipeline
from ..services.experience_analyzer import analyze_experience
from ..services.ranking_engine import describe_formula
from .deps import require_access
from .matching import _job, _run
from .views import HIGH_SCORE, rows_for_run, run_info

public = APIRouter(prefix="")
router = APIRouter(dependencies=[Depends(require_access)])


# ---------------------------------------------------------------------------- public
@public.get("/health", tags=["system"])
def health(db: Session = Depends(get_db)):
    db.execute(select(1))
    from ..services.semantic_matcher import SimilarityEngine
    return {"status": "ok", "algorithm_version": ALGORITHM_VERSION, "database": "ok",
            "embedding": {"configured": settings.embedding_backend, "sentence_transformers_installed": importlib.util.find_spec("sentence_transformers") is not None,
                          "model_loaded": SimilarityEngine._model is not None, "model_load_failed": SimilarityEngine._model_failed},
            "ocr": {"enabled": settings.ocr_enabled}, "auth_required": bool(settings.api_key)}


@public.post("/auth/login", tags=["system"])
def login(body: LoginIn):
    """Demo access. If API_KEY is unset the app is open (local demo); otherwise the key must match."""
    import hmac
    if settings.api_key and not hmac.compare_digest(body.api_key, settings.api_key):
        raise AppError("Invalid access key.", 401, "unauthorized")
    return {"ok": True, "auth_required": bool(settings.api_key), "role": "recruiter"}


# ---------------------------------------------------------------------------- analytics
def _bins(values, edges, labels):
    c = Counter()
    for v in values:
        for i in range(len(edges) - 1):
            if edges[i] <= v < edges[i + 1]:
                c[labels[i]] += 1
                break
    return [{"bucket": l, "count": c.get(l, 0)} for l in labels]


@router.get("/analytics/{job_id}", tags=["analytics"])
def analytics(job_id: int, blind: bool = True, db: Session = Depends(get_db)):
    job = _job(db, job_id)
    total_resumes = db.scalar(select(func.count(M.Resume.id)))
    parsed = db.scalar(select(func.count(M.Resume.id)).where(M.Resume.status == "parsed"))
    failed = total_resumes - parsed
    fails = dict(db.execute(select(M.Resume.error_code, func.count()).where(M.Resume.status == "failed").group_by(M.Resume.error_code)).all())
    base = {"job": {"id": job.id, "title": job.title}, "parsing": {"total": total_resumes, "parsed": parsed, "failed": failed,
            "success_rate": round(parsed / total_resumes * 100, 1) if total_resumes else None, "failures_by_reason": fails}, "has_run": False}
    run = pipeline.latest_run(db, job_id)
    if not run:
        return base
    rows = rows_for_run(db, run, blind)
    reqs = [r for r in run.job_snapshot["requirements"] if r["importance"] in ("must", "preferred")]
    n = len(rows)
    sf = Counter(s for r in rows for s in r["candidate_skills"])
    matched = Counter(s for r in rows for s in r["matched_skills"])
    missing = Counter(s for r in rows for s in r["missing_skills"])
    cover = []
    for q in reqs:
        c = Counter(next((x["match_type"] for x in r["requirements"] if x["name"] == q["name"]), "none") for r in rows)
        cover.append({"requirement": q["name"], "importance": q["importance"], "exact_or_synonym": c["exact"] + c["synonym"], "related": c["partial"],
                      "semantic": c["semantic"], "no_evidence": c["none"], "coverage_pct": round((c["exact"] + c["synonym"]) / n * 100, 1) if n else 0})
    return {**base, "has_run": True, "run": run_info(run), "summary": {
        "total_candidates": n, "average_score": round(sum(r["overall"] for r in rows) / n, 2), "high_matching": sum(r["overall"] >= HIGH_SCORE for r in rows),
        "needs_review": sum(r["needs_review"] for r in rows), "high_threshold": HIGH_SCORE},
        "score_distribution": _bins([r["overall"] for r in rows], [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100.01], [f"{i}-{i + 10}" for i in range(0, 100, 10)]),
        "skill_frequency": [{"skill": k, "count": v} for k, v in sf.most_common(15)],
        "top_matching_skills": [{"skill": k, "count": v} for k, v in matched.most_common(10)],
        "most_missing_skills": [{"skill": k, "count": v} for k, v in missing.most_common(10)],
        "experience_distribution": _bins([r["total_years"] for r in rows], [0, 1, 3, 5, 8, 100], ["<1y", "1-3y", "3-5y", "5-8y", "8y+"]),
        "ranking_distribution": [{"rank": r["rank"], "score": r["overall"], "name": r["name"]} for r in rows],
        "requirement_coverage": cover}


@router.get("/analytics/talent-pool/overview", tags=["analytics"])
def talent_pool(job_id: int | None = None, top: int = 15, blind: bool = True, db: Session = Depends(get_db)):
    cands = list(db.scalars(select(M.Candidate).join(M.Resume, M.Resume.candidate_id == M.Candidate.id).where(M.Resume.status == "parsed").order_by(M.Candidate.id)))
    n = len(cands)
    sf = Counter(s.name for c in cands for s in c.skills)
    cat = {s.name: s.category for c in cands for s in c.skills}
    years = []
    for c in cands:
        e = analyze_experience(c.parsed.get("employment", []), {"experience": {}}, set(), date.today(), None)
        years.append(e["total_effective_years"])
    common = [{"skill": k, "count": v, "category": cat[k], "pct": round(v / n * 100, 1)} for k, v in sf.most_common(top)] if n else []
    rare = [{"skill": k, "count": v, "category": cat[k]} for k, v in sorted(sf.items(), key=lambda kv: (kv[1], kv[0])) if v <= max(1, int(0.1 * n))][:top] if n else []
    matrix_skills = [x["skill"] for x in common[:12]]
    matrix = [{"candidate_id": c.id, "name": pipeline.display_name(c, blind), "skills": {s: (s in {x.name for x in c.skills}) for s in matrix_skills}} for c in cands]
    cov = None
    if job_id:
        run = pipeline.latest_run(db, job_id)
        if run:
            rows = rows_for_run(db, run, blind)
            reqs = [r for r in run.job_snapshot["requirements"] if r["importance"] in ("must", "preferred")]
            cov = [{"requirement": q["name"], "importance": q["importance"],
                    "candidates_with_evidence": sum(1 for r in rows if any(x["name"] == q["name"] and x["match_type"] in ("exact", "synonym") for x in r["requirements"])),
                    "total": len(rows)} for q in reqs]
    return {"total_candidates": n, "common_skills": common, "rare_skills": rare,
            "experience_distribution": _bins(years, [0, 1, 3, 5, 8, 100], ["<1y", "1-3y", "3-5y", "5-8y", "8y+"]),
            "skill_matrix": {"skills": matrix_skills, "rows": matrix}, "job_coverage": cov,
            "availability": {"available": False, "note": "Availability is shown only when explicitly provided. Resumes are not mined for availability, and no such field has been collected."}}


# ---------------------------------------------------------------------------- reports
def _report_ctx(db, job_id, blind, run_id=None):
    job = _job(db, job_id)
    run = _run(db, job_id, run_id)
    rows = rows_for_run(db, run, blind)
    return job, run, rows


def _download(data: bytes, name: str, mime: str):
    return Response(content=data, media_type=mime, headers={"Content-Disposition": f'attachment; filename="{name}"'})


BLIND_INTERVIEWS_NOTE = "Interview notes are omitted from blind-screening exports because free text can contain identifying details."


def _interviews_for(db: Session, candidate_ids) -> dict[int, list[dict]]:
    """candidate_id -> interview scorecards (newest first, each with its linked job title) for the exports."""
    from .matching import _interview_out
    ids = set(candidate_ids)
    if not ids:
        return {}
    notes = list(db.scalars(select(M.InterviewNote).where(M.InterviewNote.candidate_id.in_(ids))
                            .order_by(M.InterviewNote.interviewed_on.desc(), M.InterviewNote.id.desc())))
    job_ids = {n.job_id for n in notes if n.job_id is not None}
    titles = {j.id: j.title for j in db.scalars(select(M.Job).where(M.Job.id.in_(job_ids)))} if job_ids else {}
    out: dict[int, list[dict]] = {}
    for n in notes:
        d = _interview_out(n)
        d["job_title"] = titles.get(n.job_id)
        out.setdefault(n.candidate_id, []).append(d)
    return out


@router.get("/reports/matrix/excel", tags=["reports"])   # must be declared before the /reports/{job_id}/... routes
def report_matrix_excel(blind: bool = False, ids: str | None = None, interviews: bool = True, db: Session = Depends(get_db)):
    """Talent matrix workbook: every candidate x every job that has a ranking run.
    `ids` (comma-separated candidate ids) exports only those candidates, in that order (the on-screen filter and sort).
    Interview figures (count and average rating, never text) are included unless `interviews=false` or blind mode."""
    order: list[int] | None = None
    if ids:
        parts = [p.strip() for p in ids.split(",") if p.strip()]
        if not parts or len(parts) > 1000 or not all(p.isdigit() for p in parts):
            raise AppError("ids must be a comma-separated list of candidate ids (at most 1000).", 422, "validation_error")
        order = [int(p) for p in parts]
    jobs = []
    for j in db.scalars(select(M.Job).order_by(M.Job.id)):
        run = pipeline.latest_run(db, j.id)
        if run:
            jobs.append({"id": j.id, "title": j.title, "run": run_info(run), "rows": rows_for_run(db, run, blind)})
    if not jobs:
        raise AppError("No job has a ranking run yet. Run matching first.", 404, "no_run")
    iv = _interviews_for(db, {r["candidate_id"] for j in jobs for r in j["rows"]}) if (interviews and not blind) else None
    pipeline.audit(db, "report.exported", "matrix", None, {"format": "xlsx", "blind": blind, "filtered": order is not None, "jobs": len(jobs),
                                                            "interviews": sum(len(v) for v in iv.values()) if iv is not None else 0})
    db.commit()
    return _download(exports.matrix_excel(jobs, order, blind, iv), "talentiq_talent_matrix.xlsx",
                     "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@router.get("/reports/{job_id}/csv", tags=["reports"])
def report_csv(job_id: int, blind: bool = False, interviews: bool = True, db: Session = Depends(get_db)):
    """Ranking CSV. Two summary columns (interview count and average rating; numbers only, never text) are added unless
    `interviews=false`; they are always left out in blind mode."""
    job, run, rows = _report_ctx(db, job_id, blind)
    iv = _interviews_for(db, [r["candidate_id"] for r in rows]) if (interviews and not blind) else None
    pipeline.audit(db, "report.exported", "job", job_id, {"format": "csv", "blind": blind, "interviews": sum(len(v) for v in iv.values()) if iv is not None else 0}); db.commit()
    return _download(exports.to_csv(rows, iv), f"talentiq_job{job_id}_ranking.csv", "text/csv; charset=utf-8")


@router.get("/reports/{job_id}/excel", tags=["reports"])
def report_excel(job_id: int, blind: bool = False, interviews: bool = True, db: Session = Depends(get_db)):
    """Ranking workbook. Interview notes add an 'Interviews' sheet and two summary columns; they are left out with
    `interviews=false` and always in blind mode (free text can contain identifying details)."""
    job, run, rows = _report_ctx(db, job_id, blind)
    info = {**run_info(run), "job_title": job.title, "weights": ", ".join(f"{k}={v}" for k, v in run.weights.items()), "formula": describe_formula(run.weights)}
    iv = _interviews_for(db, [r["candidate_id"] for r in rows]) if (interviews and not blind) else None
    omitted = BLIND_INTERVIEWS_NOTE if (interviews and blind) else None
    pipeline.audit(db, "report.exported", "job", job_id, {"format": "xlsx", "blind": blind, "interviews": sum(len(v) for v in iv.values()) if iv is not None else 0}); db.commit()
    return _download(exports.to_excel(rows, info, run.job_snapshot["requirements"], iv, omitted), f"talentiq_job{job_id}_ranking.xlsx",
                     "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@router.get("/reports/{job_id}/pdf", tags=["reports"])
def report_pdf(job_id: int, blind: bool = False, db: Session = Depends(get_db)):
    job, run, rows = _report_ctx(db, job_id, blind)
    pipeline.audit(db, "report.exported", "job", job_id, {"format": "pdf", "blind": blind}); db.commit()
    return _download(exports.job_pdf(job.title, run_info(run), rows), f"talentiq_job{job_id}_report.pdf", "application/pdf")


@router.get("/reports/{job_id}/candidate/{candidate_id}/pdf", tags=["reports"])
def candidate_report(job_id: int, candidate_id: int, blind: bool = False, interviews: bool = True, db: Session = Depends(get_db)):
    """Candidate PDF. Interview notes are included by default (`interviews=false` leaves them out) and are always
    left out of blind-screening reports, because free text can contain identifying details."""
    from .matching import _interview_summary, candidate_detail
    job = _job(db, job_id)
    d = candidate_detail(candidate_id, job_id, None, blind, db)
    if not d["result"]:
        raise AppError("Candidate is not part of the latest run.", 404, "not_found")
    iv, omitted = None, None
    if interviews and blind:
        omitted = "Interview notes are omitted from blind-screening reports because free text can contain identifying details."
    elif interviews:
        items = _interviews_for(db, [candidate_id]).get(candidate_id, [])
        iv = {"items": items, "summary": _interview_summary(items)}
    pipeline.audit(db, "report.exported", "candidate", candidate_id, {"format": "pdf", "blind": blind, "interviews": len(iv["items"]) if iv else 0}); db.commit()
    return _download(exports.candidate_pdf(d["candidate"]["name"], job.title, d, iv, omitted), f"talentiq_candidate{candidate_id}_report.pdf", "application/pdf")


# ---------------------------------------------------------------------------- admin / settings
@router.get("/settings", tags=["admin"])
def get_settings():
    from ..services.semantic_matcher import CALIBRATION
    return {"algorithm_version": ALGORITHM_VERSION, "default_weights": DEFAULT_WEIGHTS, "component_labels": COMPONENT_LABELS, "components": COMPONENTS,
            "max_upload_mb": settings.max_upload_mb, "max_batch_files": settings.max_batch_files, "retention_days": settings.retention_days,
            "store_original_files": settings.store_original_files, "embedding_backend": settings.embedding_backend, "calibration": CALIBRATION,
            "ontology": {"version": pipeline.ontology.version, "skills": len(pipeline.ontology.skills)}, "formula": describe_formula(DEFAULT_WEIGHTS)}


@router.get("/audit", tags=["admin"])
def audit_log(page: int = 1, page_size: int = 50, action: str | None = None, db: Session = Depends(get_db)):
    page_size = max(1, min(page_size, 200))
    q = select(M.AuditLog)
    if action:
        q = q.where(M.AuditLog.action == action)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.scalars(q.order_by(M.AuditLog.id.desc()).offset((max(page, 1) - 1) * page_size).limit(page_size))
    return {"total": total, "items": [{"id": a.id, "ts": a.ts.isoformat(), "actor": a.actor, "action": a.action, "entity_type": a.entity_type,
                                         "entity_id": a.entity_id, "details": a.details} for a in rows]}


@router.post("/admin/retention/run", tags=["admin"])
def retention(days: int | None = None, db: Session = Depends(get_db)):
    return {"deleted": pipeline.purge_expired(db, days), "days": settings.retention_days if days is None else days}


@router.get("/ontology", tags=["admin"])
def get_ontology(category: str | None = None):
    o = pipeline.ontology
    sk = [s for s in o.skills.values() if not category or s["category"] == category]
    return {"version": o.version, "categories": sorted({s["category"] for s in o.skills.values()}), "count": len(sk), "skills": sk}


@router.post("/ontology/reload", tags=["admin"])
def reload_ontology():
    pipeline.reload_ontology()
    return {"reloaded": True, "skills": len(pipeline.ontology.skills), "note": "Re-run matching (and re-upload/retry resumes) to apply ontology changes to existing data."}


@router.get("/searches", tags=["workflow"])
def list_searches(job_id: int | None = None, db: Session = Depends(get_db)):
    q = select(M.SavedSearch).order_by(M.SavedSearch.id.desc())
    if job_id:
        q = q.where((M.SavedSearch.job_id == job_id) | (M.SavedSearch.job_id.is_(None)))
    return [{"id": s.id, "name": s.name, "job_id": s.job_id, "filters": s.filters} for s in db.scalars(q)]


@router.post("/searches", status_code=201, tags=["workflow"])
def save_search(body: SavedSearchIn, db: Session = Depends(get_db)):
    s = M.SavedSearch(**body.model_dump())
    db.add(s)
    db.commit()
    return {"id": s.id, "name": s.name, "job_id": s.job_id, "filters": s.filters}


@router.delete("/searches/{sid}", status_code=204, tags=["workflow"])
def del_search(sid: int, db: Session = Depends(get_db)):
    s = db.get(M.SavedSearch, sid)
    if not s:
        raise AppError("Saved search not found.", 404, "not_found")
    db.delete(s)
    db.commit()


# ---------------------------------------------------------------------------- demo helpers
SAMPLE_DIR = Path(os.environ["SAMPLE_DATA_DIR"]) if os.environ.get("SAMPLE_DATA_DIR") else ROOT_DIR / "sample_data"


@router.post("/demo/seed-jobs", tags=["demo"])
def seed_jobs(db: Session = Depends(get_db)):
    """Loads the bundled synthetic job descriptions as reusable JD templates (idempotent)."""
    from ..schemas.api import JobIn
    from .jobs import _apply
    created = []
    for p in sorted((SAMPLE_DIR / "job_descriptions").glob("*.txt")):
        text = p.read_text(encoding="utf-8")
        title = next((l.split(":", 1)[1].strip() for l in text.splitlines() if l.lower().startswith("job title:")), p.stem)
        if db.scalar(select(M.Job).where(M.Job.title == title, M.Job.is_template.is_(True))):
            continue
        j = M.Job()
        _apply(j, JobIn(title=title, description=text, is_template=True, category="Synthetic sample"))
        db.add(j)
        db.flush()
        created.append(j.id)
    pipeline.audit(db, "demo.seed_jobs", None, None, {"created": len(created)})
    db.commit()
    return {"created": created, "templates": db.scalar(select(func.count(M.Job.id)).where(M.Job.is_template.is_(True)))}


@router.post("/demo/upload-samples", tags=["demo"])
def upload_samples(db: Session = Depends(get_db)):
    """Runs the bundled SYNTHETIC resumes through the real upload pipeline (demo only)."""
    import uuid
    d = SAMPLE_DIR / "resumes"
    files = sorted(p for p in d.iterdir() if p.is_file() and p.suffix.lower() in (".pdf", ".docx"))
    if not files:
        raise AppError("No sample resumes found. Run scripts/generate_sample_data.py first.", 404, "no_samples")
    batch = uuid.uuid4().hex[:12]
    results = [pipeline.ingest_resume(db, p.name, p.read_bytes(), batch) for p in files]
    summary = {s: sum(1 for r in results if r["status"] == s) for s in ("parsed", "failed", "duplicate", "rejected")}
    return {"batch_id": batch, "total": len(results), "summary": summary, "results": results}
