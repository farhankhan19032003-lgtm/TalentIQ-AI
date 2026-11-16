from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.config import COMPONENTS, DEFAULT_WEIGHTS
from ..core.database import get_db
from ..core.errors import AppError
from ..models import db as M
from ..schemas.api import RATING_CRITERIA, BulkStatusIn, InterviewIn, InterviewPatch, NoteIn, OverrideIn, RunIn, StatusIn, WhatIfIn
from ..services import pipeline
from .deps import require_access
from .views import HIGH_SCORE, mask_fields, result_row, rows_for_run, run_info

router = APIRouter(tags=["matching"], dependencies=[Depends(require_access)])


def _job(db, job_id):
    j = db.get(M.Job, job_id)
    if not j:
        raise AppError("Job not found.", 404, "not_found")
    return j


def _run(db, job_id, run_id=None):
    run = db.get(M.MatchRun, run_id) if run_id else pipeline.latest_run(db, job_id)
    if not run or run.job_id != job_id:
        raise AppError("No matching run exists for this job. Run matching first.", 404, "no_run")
    return run


@router.post("/matching/run/{job_id}", status_code=201)
def run(job_id: int, body: RunIn | None = None, db: Session = Depends(get_db)):
    body = body or RunIn()
    r = pipeline.run_matching(db, _job(db, job_id), body.weights, body.resume_ids)
    return {**run_info(r), "default_weights": DEFAULT_WEIGHTS}


@router.get("/matching/runs/{job_id}")
def runs(job_id: int, db: Session = Depends(get_db)):
    _job(db, job_id)
    rs = db.scalars(select(M.MatchRun).where(M.MatchRun.job_id == job_id).order_by(M.MatchRun.id.desc()))
    return [run_info(r) for r in rs]


SORTS = {"rank": lambda r: r["rank"], "name": lambda r: r["name"].lower(), "overall": lambda r: r["overall"], "experience": lambda r: r["relevant_years"],
         "coverage": lambda r: r["skill_coverage"] or 0, "confidence": lambda r: r["confidence"], "completeness": lambda r: r["completeness"],
         "role": lambda r: (r["latest_role"] or "").lower(), "status": lambda r: r["review_status"]}


@router.get("/matching/results/{job_id}")
def results(job_id: int, run_id: int | None = None, q: str | None = None, min_score: float | None = None, max_score: float | None = None,
            min_exp: float | None = None, max_exp: float | None = None, skills: str | None = None, review_status: str | None = None,
            min_confidence: float | None = None, needs_review: bool | None = None, sort: str = "rank", order: str = "asc",
            page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), blind: bool = False, db: Session = Depends(get_db)):
    job = _job(db, job_id)
    run = _run(db, job_id, run_id)
    rows = rows_for_run(db, run, blind)
    allrows = rows
    if q:
        ql = q.lower()
        rows = [r for r in rows if ql in r["name"].lower() or ql in (r["latest_role"] or "").lower() or any(ql in s.lower() for s in r["candidate_skills"])]
    if min_score is not None:
        rows = [r for r in rows if r["overall"] >= min_score]
    if max_score is not None:
        rows = [r for r in rows if r["overall"] <= max_score]
    if min_exp is not None:
        rows = [r for r in rows if r["total_years"] >= min_exp]
    if max_exp is not None:
        rows = [r for r in rows if r["total_years"] <= max_exp]
    if skills:
        want = [s.strip().lower() for s in skills.split(",") if s.strip()]
        rows = [r for r in rows if all(any(w == s.lower() for s in r["candidate_skills"]) for w in want)]
    if review_status:
        rows = [r for r in rows if r["review_status"] == review_status]
    if min_confidence is not None:
        rows = [r for r in rows if r["confidence"] >= min_confidence]
    if needs_review is not None:
        rows = [r for r in rows if r["needs_review"] == needs_review]
    if sort not in SORTS:
        raise AppError(f"sort must be one of {', '.join(SORTS)}", 422, "invalid_sort")
    rows = sorted(rows, key=SORTS[sort], reverse=(order == "desc"))
    total = len(rows)
    items = rows[(page - 1) * page_size: page * page_size]
    summary = {"total_ranked": len(allrows), "average_score": round(sum(r["overall"] for r in allrows) / len(allrows), 2) if allrows else None,
               "high_matching": sum(r["overall"] >= HIGH_SCORE for r in allrows), "needs_review": sum(r["needs_review"] for r in allrows),
               "high_threshold": HIGH_SCORE}
    return {"job": {"id": job.id, "title": job.title}, "run": run_info(run), "summary": summary, "total": total, "page": page,
            "page_size": page_size, "items": items}


def _candidate_view(db, c: M.Candidate, blind: bool):
    p = c.parsed
    return {"id": c.id, "name": pipeline.display_name(c, blind), "fields": mask_fields(p.get("fields", {}), blind), "review_status": c.review_status,
            "employment": p.get("employment", []), "education": p.get("education", []), "projects": p.get("projects", []),
            "certifications": p.get("certifications", []), "achievements": p.get("achievements", []), "publications": p.get("publications", []),
            "skills": sorted(p.get("skills", {}).values(), key=lambda s: (s["category"], s["name"])), "parse_confidence": c.parse_confidence,
            "protected_lines_removed": p.get("protected_lines_removed", 0), "injection_flags": p.get("injection_flags", []),
            "diagnostics": c.resume.diagnostics if c.resume else {}, "file": {"filename": (f"resume_{c.resume.id}.{c.resume.file_type}" if blind else c.resume.original_filename) if c.resume else None,
                                                                              "pages": c.resume.page_count if c.resume else None},
            "notes": [{"id": n.id, "text": n.text, "author": n.author, "at": n.created_at.isoformat()} for n in sorted(c.notes, key=lambda n: -n.id)]}


@router.get("/matching/candidate/{candidate_id}")
def candidate_detail(candidate_id: int, job_id: int | None = None, run_id: int | None = None, blind: bool = False, db: Session = Depends(get_db)):
    c = db.get(M.Candidate, candidate_id)
    if not c:
        raise AppError("Candidate not found.", 404, "not_found")
    out = {"candidate": _candidate_view(db, c, blind), "result": None}
    if job_id:
        run = _run(db, job_id, run_id)
        res = db.scalar(select(M.MatchResult).where(M.MatchResult.run_id == run.id, M.MatchResult.candidate_id == candidate_id))
        if res:
            row = result_row(res, c, blind)
            d = res.detail
            out["result"] = {**row, "run": run_info(run), "requirements": d["requirements"], "experience": d["experience"], "education": d["education"],
                             "projects": d["projects"], "semantic": d["semantic"], "components": d["components"], "explanation": res.explanation,
                             "evidence": [{"requirement_id": e.requirement_id, "requirement": e.requirement, "category": e.category, "match_type": e.match_type,
                                           "text": e.evidence_text, "page": e.page, "similarity": e.similarity, "verification": e.verification} for e in res.evidence],
                             "overrides": [{"id": o.id, "original_score": o.original_score, "new_score": o.new_score, "reason": o.reason, "reviewer": o.reviewer,
                                            "at": o.created_at.isoformat()} for o in sorted(res.overrides, key=lambda o: -o.id)]}
    return out


@router.get("/matching/compare")
def compare(job_id: int, ids: str, blind: bool = False, db: Session = Depends(get_db)):
    idl = [int(x) for x in ids.split(",") if x.strip().isdigit()]
    if not (2 <= len(idl) <= 5):
        raise AppError("Select between 2 and 5 candidates to compare.", 422, "invalid_selection")
    run = _run(db, job_id)
    rows = [r for r in rows_for_run(db, run, blind) if r["candidate_id"] in idl]
    if len(rows) != len(set(idl)):
        raise AppError("One or more candidates are not part of the latest run.", 404, "not_found")
    names = [r["name"] for r in run.job_snapshot["requirements"] if r["importance"] in ("must", "preferred")]
    return {"run": run_info(run), "requirements": [r for r in run.job_snapshot["requirements"] if r["importance"] in ("must", "preferred")], "candidates": rows}


@router.post("/matching/whatif/{job_id}")
def whatif(job_id: int, body: WhatIfIn, blind: bool = False, db: Session = Depends(get_db)):
    return pipeline.simulate(db, _job(db, job_id), body.model_dump(), blind)


# ---- recruiter workflow --------------------------------------------------------------
@router.patch("/candidates/{candidate_id}/status")
def set_status(candidate_id: int, body: StatusIn, db: Session = Depends(get_db)):
    c = db.get(M.Candidate, candidate_id)
    if not c:
        raise AppError("Candidate not found.", 404, "not_found")
    old = c.review_status
    c.review_status = body.review_status
    pipeline.audit(db, "candidate.status_changed", "candidate", c.id, {"from": old, "to": body.review_status, "human_decision": True, "has_reason": bool(body.reason)})
    db.commit()
    return {"candidate_id": c.id, "review_status": c.review_status}


@router.post("/candidates/status/bulk")
def set_status_bulk(body: BulkStatusIn, db: Session = Depends(get_db)):
    """Recruiter-initiated bulk stage change. All-or-nothing: an unknown id changes nothing.
    Returns each change with its previous status so the UI can offer Undo."""
    ids = list(dict.fromkeys(body.candidate_ids))                      # de-duplicate, keep order
    found = {c.id: c for c in db.scalars(select(M.Candidate).where(M.Candidate.id.in_(ids)))}
    missing = [i for i in ids if i not in found]
    if missing:
        raise AppError(f"Candidate(s) not found: {', '.join(map(str, missing[:10]))}. Nothing was changed.", 404, "not_found")
    changes = []
    for i in ids:
        c = found[i]
        if c.review_status == body.review_status:
            continue
        changes.append({"candidate_id": c.id, "from": c.review_status, "to": body.review_status})
        pipeline.audit(db, "candidate.status_changed", "candidate", c.id,
                       {"from": c.review_status, "to": body.review_status, "human_decision": True, "bulk": True, "has_reason": bool(body.reason)})
        c.review_status = body.review_status
    db.commit()
    return {"review_status": body.review_status, "requested": len(ids), "updated": len(changes), "unchanged": len(ids) - len(changes), "changes": changes}


# ---- interview notes (structured scorecards written by humans; never feed the match score) -----------
def _interview_out(n: M.InterviewNote) -> dict:
    vals = list((n.ratings or {}).values())
    return {"id": n.id, "candidate_id": n.candidate_id, "job_id": n.job_id, "round": n.round, "interviewer": n.interviewer,
            "interviewed_on": n.interviewed_on.isoformat() if n.interviewed_on else None, "recommendation": n.recommendation,
            "ratings": n.ratings or {}, "rating_avg": round(sum(vals) / len(vals), 2) if vals else None,
            "strengths": n.strengths, "concerns": n.concerns, "notes": n.notes,
            "created_at": n.created_at.isoformat(), "updated_at": n.updated_at.isoformat()}


def _interview_summary(items: list[dict]) -> dict:
    avgs = [i["rating_avg"] for i in items if i["rating_avg"] is not None]
    by = {}
    for k in RATING_CRITERIA:
        vs = [i["ratings"][k] for i in items if k in i["ratings"]]
        by[k] = round(sum(vs) / len(vs), 2) if vs else None
    # A tally of what interviewers said. Deliberately no combined verdict: people decide.
    rec = {k: sum(1 for i in items if i["recommendation"] == k) for k in ("strong_yes", "yes", "no", "strong_no", "undecided")}
    return {"count": len(items), "avg_rating": round(sum(avgs) / len(avgs), 2) if avgs else None, "avg_by_criterion": by, "recommendations": rec}


def _candidate(db: Session, candidate_id: int) -> M.Candidate:
    c = db.get(M.Candidate, candidate_id)
    if not c:
        raise AppError("Candidate not found.", 404, "not_found")
    return c


def _interview(db: Session, candidate_id: int, interview_id: int) -> M.InterviewNote:
    n = db.get(M.InterviewNote, interview_id)
    if not n or n.candidate_id != candidate_id:
        raise AppError("Interview note not found.", 404, "not_found")
    return n


def _check_job(db: Session, job_id: int | None):
    if job_id is not None and not db.get(M.Job, job_id):
        raise AppError("Job not found.", 404, "not_found")


@router.get("/candidates/interviews/summary")
def interviews_summary(ids: str, db: Session = Depends(get_db)):
    """Interview count, average rating and recommendation tally for many candidates in one request (used by the pipeline board).
    Candidates without interviews are simply absent from the result."""
    parts = [p.strip() for p in ids.split(",") if p.strip()]
    if not parts or len(parts) > 1000 or not all(p.isdigit() for p in parts):
        raise AppError("ids must be a comma-separated list of candidate ids (at most 1000).", 422, "validation_error")
    by: dict[int, list[dict]] = {}
    for n in db.scalars(select(M.InterviewNote).where(M.InterviewNote.candidate_id.in_({int(p) for p in parts}))):
        by.setdefault(n.candidate_id, []).append(_interview_out(n))
    out = {}
    for cid, items in by.items():
        s = _interview_summary(items)
        out[str(cid)] = {"count": s["count"], "avg_rating": s["avg_rating"], "recommendations": s["recommendations"]}
    return {"summaries": out}


@router.get("/candidates/{candidate_id}/interviews")
def list_interviews(candidate_id: int, db: Session = Depends(get_db)):
    _candidate(db, candidate_id)
    rows = db.scalars(select(M.InterviewNote).where(M.InterviewNote.candidate_id == candidate_id)
                      .order_by(M.InterviewNote.interviewed_on.desc(), M.InterviewNote.id.desc()))
    items = [_interview_out(n) for n in rows]
    return {"items": items, "summary": _interview_summary(items)}


@router.post("/candidates/{candidate_id}/interviews", status_code=201)
def add_interview(candidate_id: int, body: InterviewIn, db: Session = Depends(get_db)):
    _candidate(db, candidate_id)
    _check_job(db, body.job_id)
    n = M.InterviewNote(candidate_id=candidate_id, job_id=body.job_id, round=body.round, interviewer=body.interviewer.strip(),
                        interviewed_on=body.interviewed_on or date.today(), recommendation=body.recommendation, ratings=dict(body.ratings),
                        strengths=body.strengths.strip(), concerns=body.concerns.strip(), notes=body.notes.strip())
    db.add(n)
    db.flush()
    pipeline.audit(db, "interview.added", "candidate", candidate_id, {"interview_id": n.id, "round": n.round, "recommendation": n.recommendation, "rated": bool(n.ratings)})
    db.commit()
    return _interview_out(n)


@router.patch("/candidates/{candidate_id}/interviews/{interview_id}")
def update_interview(candidate_id: int, interview_id: int, body: InterviewPatch, db: Session = Depends(get_db)):
    n = _interview(db, candidate_id, interview_id)
    data = body.model_dump(exclude_unset=True)
    if "job_id" in data:
        _check_job(db, data["job_id"])
    for k, v in data.items():
        if v is None and k != "job_id":
            continue                                         # these fields cannot be cleared; ignore explicit nulls
        setattr(n, k, v.strip() if isinstance(v, str) else v)
    if not (n.ratings or n.strengths or n.concerns or n.notes or n.recommendation != "undecided"):
        raise AppError("An interview note cannot be empty. Delete it instead.", 422, "validation_error")
    n.updated_at = M.utcnow()
    pipeline.audit(db, "interview.updated", "candidate", candidate_id, {"interview_id": n.id, "fields": sorted(data)})
    db.commit()
    return _interview_out(n)


@router.delete("/candidates/{candidate_id}/interviews/{interview_id}", status_code=204)
def delete_interview(candidate_id: int, interview_id: int, db: Session = Depends(get_db)):
    n = _interview(db, candidate_id, interview_id)
    db.delete(n)
    pipeline.audit(db, "interview.deleted", "candidate", candidate_id, {"interview_id": interview_id})
    db.commit()


@router.post("/candidates/{candidate_id}/notes", status_code=201)
def add_note(candidate_id: int, body: NoteIn, db: Session = Depends(get_db)):
    c = db.get(M.Candidate, candidate_id)
    if not c:
        raise AppError("Candidate not found.", 404, "not_found")
    n = M.CandidateNote(candidate_id=c.id, text=body.text.strip())
    db.add(n)
    pipeline.audit(db, "candidate.note_added", "candidate", c.id, {})
    db.commit()
    return {"id": n.id, "text": n.text, "author": n.author, "at": n.created_at.isoformat()}


@router.post("/matching/results/{result_id}/override", status_code=201)
def override(result_id: int, body: OverrideIn, db: Session = Depends(get_db)):
    res = db.get(M.MatchResult, result_id)
    if not res:
        raise AppError("Result not found.", 404, "not_found")
    o = M.ManualOverride(result_id=res.id, original_score=res.overall, new_score=body.new_score, reason=body.reason.strip())
    db.add(o)
    pipeline.audit(db, "score.manual_override", "result", res.id, {"original": res.overall, "new": body.new_score})
    db.commit()
    return {"id": o.id, "original_score": o.original_score, "new_score": o.new_score, "reason": o.reason, "note": "Machine score and rank are unchanged; the override is recorded alongside."}


@router.delete("/candidates/{candidate_id}", status_code=204)
def delete_candidate(candidate_id: int, db: Session = Depends(get_db)):
    c = db.get(M.Candidate, candidate_id)
    if not c:
        raise AppError("Candidate not found.", 404, "not_found")
    pipeline.delete_candidate(db, c)
