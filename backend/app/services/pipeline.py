"""Orchestration: ingestion of resumes, job analysis, matching runs, what-if simulation, retention."""
from __future__ import annotations

import re
import time
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.config import ALGORITHM_VERSION, settings
from ..core.errors import AppError
from ..models import db as M
from . import ranking_engine
from .document_parser import DocumentError, parse_document
from .explanation_engine import explain
from .jd_analyzer import analyze_jd, slug
from .matching_pipeline import jd_narrative, match_candidate
from .resume_extractor import ResumeExtractor
from .security import UploadRejected, delete_stored, sanitize_filename, sha256, store_file, validate_upload
from .semantic_matcher import SimilarityEngine
from .skill_extractor import Ontology, SkillExtractor

ontology = Ontology()
skill_extractor = SkillExtractor(ontology)
resume_extractor = ResumeExtractor(skill_extractor)
_onto_texts: list[str] | None = None


def audit(db: Session, action: str, entity_type: str | None = None, entity_id: int | None = None, details: dict | None = None, actor="recruiter") -> None:
    db.add(M.AuditLog(action=action, entity_type=entity_type, entity_id=entity_id, details=details or {}, actor=actor))


def reload_ontology() -> None:
    global _onto_texts
    ontology.reload()
    _onto_texts = None


def ontology_texts() -> list[str]:
    """Text of every ontology skill, used to fit the TF-IDF fallback."""
    global _onto_texts
    if _onto_texts is None:
        _onto_texts = [ontology.semantic_query(n) for n in ontology.skills]
    return _onto_texts


def display_name(c: M.Candidate, blind: bool) -> str:
    """Candidate name, or an anonymous 'Candidate #id' label in blind-screening mode."""
    if blind:
        return f"Candidate C-{c.id:04d}"
    return c.name or f"Unknown (candidate #{c.id})"


# ---------------------------------------------------------------------------- jobs
def build_job_analysis(description: str, title: str | None) -> dict:
    """Run the JD analyzer and shape its output for storage on a Job row."""
    return analyze_jd(description, skill_extractor, ontology, title)


def merge_user_skills(requirements: list[dict], required: list[str], optional: list[str]) -> list[dict]:
    """Add recruiter-supplied skills to the extracted requirement list."""
    by_name = {r["name"].lower(): r for r in requirements}
    for names, imp in ((optional, "preferred"), (required, "must")):
        for n in names or []:
            n = n.strip()
            if not n:
                continue
            canon = ontology.canonical(n) or n
            ex = by_name.get(canon.lower())
            if ex:
                if imp == "must":
                    ex["importance"] = "must"
            else:
                r = {"id": "req_" + slug(canon), "name": canon, "category": ontology.category(canon) if canon in ontology.skills else "Custom",
                     "importance": imp, "weight": 1.0, "custom": canon not in ontology.skills}
                requirements.append(r)
                by_name[canon.lower()] = r
    return requirements


def normalize_requirements(reqs: list[dict]) -> list[dict]:
    """Validate and normalise a requirement list coming from the API (importance, weight, alternatives)."""
    out, seen = [], set()
    for r in reqs:
        name = (r.get("name") or "").strip()
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        canon = ontology.canonical(name) or name
        anyof = r.get("any_of") or None
        if anyof is None and " or " in name.lower():
            parts = [ontology.canonical(x) or x.strip() for x in re.split(r"\s+or\s+", name, flags=re.I) if x.strip()]
            anyof = parts if len(parts) > 1 else None
        if anyof:
            canon = " or ".join(anyof)
        out.append({"id": r.get("id") or "req_" + slug(canon), "name": canon, "any_of": anyof,
                    "category": r.get("category") or (ontology.category(anyof[0] if anyof else canon) if (anyof or canon) in ontology.skills or anyof else "Custom"),
                    "importance": r.get("importance", "must") if r.get("importance") in ("must", "preferred", "ignored") else "must",
                    "weight": float(r.get("weight", 1.0)), "custom": (canon not in ontology.skills) and not anyof})
    return out


def job_to_dict(job: M.Job) -> dict:
    """Plain-dict view of a Job for the matching engine."""
    return {"id": job.id, "title": job.title, "description": job.description, "analysis": job.analysis or {}, "requirements": job.requirements or [],
            "min_years": job.min_experience_years, "preferred_years": job.preferred_experience_years,
            "education_level": job.education_level, "preferred_education_level": job.preferred_education_level}


# ---------------------------------------------------------------------------- ingestion
REVIEW_REASONS = {
    "scanned_ocr": "Scanned/image-only file read with OCR: the text may contain errors, check it against the original.",
    "low_text_quality": "The extracted text is of low quality (garbled or very short), so parsed fields may be wrong.",
    "recovered_with_fallback": "The PDF was malformed and was recovered with a fallback reader; check the parsed fields.",
    "name_not_found": "No candidate name could be extracted.",
}


def build_review(doc, parsed: dict) -> dict:
    """Parse-quality flags. A flagged resume is still scored, but is shown as 'needs review' with the reasons, never as a normal one."""
    codes = []
    if doc.ocr_used:
        codes.append("scanned_ocr")
    if doc.quality < 0.5 or sum(len(p.text) for p in doc.pages) < 200:
        codes.append("low_text_quality")
    if "recovered_with_fallback" in doc.warnings:
        codes.append("recovered_with_fallback")
    if not parsed["fields"]["name"]["value"]:
        codes.append("name_not_found")
    return {"needs_review": bool(codes), "codes": codes, "reasons": [REVIEW_REASONS[c] for c in codes]}


def _persist_candidate(db: Session, resume: M.Resume, parsed: dict) -> M.Candidate:
    f = parsed["fields"]
    c = M.Candidate(name=f["name"]["value"], email=f["email"]["value"], phone=f["phone"]["value"], location=f["location"]["value"],
                    linkedin=f["linkedin"]["value"], github=f["github"]["value"], portfolio=f["portfolio"]["value"],
                    summary=f["summary"]["value"], parsed=parsed, parse_confidence=parsed["parse_confidence"])
    db.add(c)
    db.flush()
    for s in parsed["skills"].values():
        c.skills.append(M.ExtractedSkill(name=s["name"], category=s["category"], method=s["method"], listed_only=s["listed_only"],
                                         mentions=s["mentions"], proficiency=s["proficiency"]))
    for e in parsed["employment"]:
        st, en = e["start"], e["end"]
        c.employment.append(M.Employment(title=e["title"], company=e["company"], start=f"{st['year']}-{st['month']:02d}",
                                         end=None if en.get("current") else f"{en['year']}-{en['month']:02d}", is_current=e["is_current"],
                                         type=e["type"], date_uncertain=e["date_uncertain"], description=e["description"], page=e["page"]))
    for e in parsed["education"]:
        c.education.append(M.Education(degree=e["degree"], level=e["level"], institution=e["institution"], year=e["year"], field=e["field"], page=e["page"]))
    for p in parsed["projects"]:
        c.projects.append(M.Project(name=p["name"], description=p["description"], skills=p.get("skills", []), page=p["page"]))
    resume.candidate_id = c.id
    return c


def process_resume_record(db: Session, resume: M.Resume, data: bytes) -> None:
    """Parse + extract + persist for an existing Resume row. Never raises: failures are recorded on the row."""
    t0 = time.time()
    try:
        doc = parse_document(data, resume.file_type)
        parsed = resume_extractor.extract(doc)
        parsed["review"] = build_review(doc, parsed)
        diag = {"pages": [p.diag() for p in doc.pages], "document_quality": doc.quality, "ocr_used": doc.ocr_used, "warnings": doc.warnings,
                "protected_lines_removed": parsed["protected_lines_removed"], "injection_flags": parsed["injection_flags"],
                "parse_confidence": parsed["parse_confidence"], "sections_found": parsed["section_names_found"]}
        with db.begin_nested():
            resume.raw_text = "\f".join("\n".join(l for l in p.text.split("\n")) for p in doc.pages)
            # remove protected-attribute lines from stored text as well
            resume.raw_text = _scrub(resume.raw_text)
            resume.page_count = len(doc.pages)
            resume.diagnostics = diag
            resume.status, resume.error_code, resume.error_message = "parsed", None, None
            if resume.candidate_id:
                old = db.get(M.Candidate, resume.candidate_id)
                resume.candidate_id = None
                if old:
                    db.delete(old)
                db.flush()
            _persist_candidate(db, resume, parsed)
    except DocumentError as e:
        resume.status, resume.error_code, resume.error_message = "failed", e.code, e.message
    except Exception as e:  # last-resort safety net: never crash the batch
        resume.status, resume.error_code, resume.error_message = "failed", "processing_error", f"Unexpected processing error ({type(e).__name__})."
    resume.processing_ms = int((time.time() - t0) * 1000)


def _scrub(text: str) -> str:
    from .resume_extractor import PROTECTED
    return "\n".join(l for l in text.split("\n") if not PROTECTED.match(l.strip()))


def ingest_resume(db: Session, filename: str, data: bytes, batch_id: str) -> dict:
    """Validate, store, hash and parse one uploaded file; returns a per-file result (parsed / failed / rejected / duplicate)."""
    safe = sanitize_filename(filename)
    try:
        kind = validate_upload(filename, data)
    except UploadRejected as e:
        audit(db, "resume.rejected", "resume", None, {"reason": e.code, "size": len(data)})
        return {"filename": safe, "status": "rejected", "error_code": e.code, "error_message": e.message, "resume_id": None}
    h = sha256(data)
    existing = db.scalar(select(M.Resume).where(M.Resume.file_hash == h))
    if existing:
        return {"filename": safe, "status": "duplicate", "resume_id": existing.id, "candidate_id": existing.candidate_id,
                "error_code": "duplicate_file", "error_message": f"Identical file already uploaded as '{existing.original_filename}'."}
    stored = store_file(data, kind) if settings.store_original_files else None
    r = M.Resume(batch_id=batch_id, original_filename=safe, stored_filename=stored, file_hash=h, file_size=len(data), file_type=kind, status="pending")
    db.add(r)
    db.flush()
    process_resume_record(db, r, data)
    audit(db, "resume.uploaded", "resume", r.id, {"status": r.status, "error": r.error_code, "type": kind, "size": len(data)})
    db.commit()
    out = {"filename": safe, "resume_id": r.id, "candidate_id": r.candidate_id, "status": r.status, "error_code": r.error_code,
           "error_message": r.error_message, "processing_ms": r.processing_ms, "warnings": [], "possible_duplicate_of": None}
    if r.candidate_id:
        c = db.get(M.Candidate, r.candidate_id)
        out["parse_confidence"] = c.parse_confidence
        review = (c.parsed or {}).get("review") or {}
        out["needs_review"], out["review_reasons"] = bool(review.get("needs_review")), review.get("reasons", [])
        if review.get("needs_review"):
            out["warnings"].extend(review["reasons"])
        flags = (r.diagnostics or {}).get("injection_flags")
        if flags:
            out["warnings"].append("Resume contains instruction-like text, which is ignored (treated as data only).")
        if c.email:
            dup = db.scalar(select(M.Candidate).where(M.Candidate.email == c.email, M.Candidate.id != c.id))
            if dup:
                out["possible_duplicate_of"] = dup.id
                out["warnings"].append(f"Same email as candidate #{dup.id}; possible duplicate person.")
    return out


# ---------------------------------------------------------------------------- matching
def make_engine(job: dict) -> SimilarityEngine:
    """Build the similarity engine requested by settings (MiniLM when available, else TF-IDF) fitted on the job text."""
    eng = SimilarityEngine(ontology_texts=ontology_texts())
    eng.prepare([jd_narrative(job), job.get("description", "")] + [ontology.semantic_query(r["name"]) for r in job["requirements"]]
                + job["analysis"].get("responsibilities", []))
    return eng


def _score_all(db: Session, job: dict, weights: dict, candidates: list[M.Candidate], as_of: date, engine: SimilarityEngine) -> list[dict]:
    items = []
    for c in candidates:
        pages = (c.resume.raw_text or "").split("\f") if c.resume else []
        m = match_candidate(c.parsed, pages, job, engine, ontology, weights, as_of)
        m["candidate_id"] = c.id
        items.append(m)
    ranked = ranking_engine.rank(items)
    sens = ranking_engine.sensitivity(ranked, weights)
    for m in ranked:
        m["sensitivity"] = sens[m["candidate_id"]]
        m["explanation"] = explain(m)
    return ranked


def run_matching(db: Session, job: M.Job, weights: dict | None, resume_ids: list[int] | None = None, as_of: date | None = None) -> M.MatchRun:
    """Score every parsed candidate against a job, rank them and persist the run."""
    w = ranking_engine.validate_weights(weights)
    as_of = as_of or date.today()
    q = select(M.Candidate).join(M.Resume, M.Resume.candidate_id == M.Candidate.id).where(M.Resume.status == "parsed")
    if resume_ids:
        q = q.where(M.Resume.id.in_(resume_ids))
    candidates = list(db.scalars(q.order_by(M.Candidate.id)))
    if not candidates:
        raise AppError("No parsed resumes available. Upload resumes first.", 409, "no_candidates")
    jd = job_to_dict(job)
    if not [r for r in jd["requirements"] if r["importance"] in ("must", "preferred")]:
        raise AppError("The job has no skill requirements. Add or edit requirements first.", 409, "no_requirements")
    t0 = time.time()
    engine = make_engine(jd)
    ranked = _score_all(db, jd, w, candidates, as_of, engine)
    run = M.MatchRun(job_id=job.id, algorithm_version=ALGORITHM_VERSION, similarity_method=engine.method, model_name=engine.model_name,
                     fallback_reason=(engine.fallback_reason or None) and engine.fallback_reason[:300], weights=w, as_of=as_of.isoformat(),
                     n_candidates=len(ranked), job_snapshot={"requirements": jd["requirements"], "min_years": jd["min_years"],
                                                          "preferred_years": jd["preferred_years"], "education_level": jd["education_level"]})
    db.add(run)
    db.flush()
    for m in ranked:
        res = M.MatchResult(run_id=run.id, candidate_id=m["candidate_id"], rank=m["rank"], overall=m["overall"], score_low=m["score_low"],
                            score_high=m["score_high"], skill_coverage=m["skill_coverage"], confidence=m["confidence"], completeness=m["completeness"],
                            relevant_years=m["experience"]["relevant_effective_years"], total_years=m["experience"]["total_effective_years"],
                            detail={k: m[k] for k in ("requirements", "experience", "education", "projects", "semantic", "must_have_coverage",
                                                      "completeness_checks", "components")},
                            explanation=m["explanation"], sensitivity=m["sensitivity"])
        db.add(res)
        db.flush()
        for k, c in m["components"].items():
            res.components.append(M.ScoreComponent(name=k, score=c["score"], status=c["status"], weight_configured=c["weight_configured"],
                                                   weight_effective=c["weight_effective"], contribution=c["contribution"]))
        for e in m["evidence"]:
            res.evidence.append(M.EvidenceItem(candidate_id=m["candidate_id"], requirement_id=e["requirement_id"], requirement=e["requirement"][:200],
                                               category=e["category"], match_type=e["match_type"], evidence_text=e["evidence_text"], page=e["page"],
                                               similarity=e["similarity"], verification=e["verification"]))
    run.duration_ms = int((time.time() - t0) * 1000)
    audit(db, "matching.run", "job", job.id, {"run_id": run.id, "candidates": len(ranked), "method": engine.method, "ms": run.duration_ms})
    db.commit()
    return run


def latest_run(db: Session, job_id: int) -> M.MatchRun | None:
    """Most recent matching run for a job, or None."""
    return db.scalar(select(M.MatchRun).where(M.MatchRun.job_id == job_id).order_by(M.MatchRun.id.desc()))


def simulate(db: Session, job: M.Job, mods: dict, blind: bool = False) -> dict:
    """What-if: re-score in memory with modified weights / requirements. Persists nothing."""
    run = latest_run(db, job.id)
    if not run:
        raise AppError("Run matching first before simulating.", 409, "no_run")
    jd = job_to_dict(job)
    reqs = [dict(r) for r in jd["requirements"]]
    for ch in mods.get("requirement_changes", []):
        for r in reqs:
            if r["id"] == ch["id"]:
                if ch.get("importance"):
                    r["importance"] = ch["importance"]
                if ch.get("weight") is not None:
                    r["weight"] = float(ch["weight"])
    for a in mods.get("add_requirements", []):
        n = ontology.canonical(a["name"]) or a["name"].strip()
        reqs.append({"id": "req_" + slug(n), "name": n, "category": ontology.category(n) if n in ontology.skills else "Custom",
                     "importance": a.get("importance", "must"), "weight": float(a.get("weight", 1.0)), "custom": n not in ontology.skills})
    for rid in mods.get("remove_requirement_ids", []):
        reqs = [r for r in reqs if r["id"] != rid]
    jd["requirements"] = reqs
    if mods.get("min_years") is not None:
        jd["min_years"] = float(mods["min_years"])
    if mods.get("preferred_years") is not None:
        jd["preferred_years"] = float(mods["preferred_years"])
    if mods.get("education_level") is not None:
        jd["education_level"] = int(mods["education_level"]) or None
    w = ranking_engine.validate_weights(mods.get("weights") or run.weights)
    cands = list(db.scalars(select(M.Candidate).where(M.Candidate.id.in_([r.candidate_id for r in run.results])).order_by(M.Candidate.id)))
    if not [r for r in reqs if r["importance"] in ("must", "preferred")]:
        raise AppError("Simulation has no skill requirements.", 409, "no_requirements")
    engine = make_engine(jd)
    ranked = _score_all(db, jd, w, cands, date.fromisoformat(run.as_of), engine)
    orig = {r.candidate_id: r for r in run.results}
    byid = {c.id: c for c in cands}
    rows = []
    for m in ranked:
        o = orig[m["candidate_id"]]
        rows.append({"candidate_id": m["candidate_id"], "name": display_name(byid[m["candidate_id"]], blind), "original_rank": o.rank,
                     "simulated_rank": m["rank"], "rank_change": o.rank - m["rank"], "original_score": o.overall, "simulated_score": m["overall"],
                     "score_change": round(m["overall"] - o.overall, 2)})
    return {"original_run_id": run.id, "weights": w, "rows": rows, "persisted": False,
            "note": "Simulation only. Original screening results were not modified."}


# ---------------------------------------------------------------------------- deletion / retention
def delete_candidate(db: Session, c: M.Candidate) -> bool:
    """Erase a candidate, their resume file and all derived data."""
    removed_file = False
    if c.resume:
        removed_file = delete_stored(c.resume.stored_filename)
    cid = c.id
    db.delete(c)
    audit(db, "candidate.deleted", "candidate", cid, {"original_file_deleted": removed_file})
    db.commit()
    return removed_file


def delete_resume(db: Session, r: M.Resume) -> None:
    if r.candidate_id:
        c = db.get(M.Candidate, r.candidate_id)
        if c:
            return delete_candidate(db, c)
    removed = delete_stored(r.stored_filename)
    rid = r.id
    db.delete(r)
    audit(db, "resume.deleted", "resume", rid, {"original_file_deleted": removed})
    db.commit()
    return removed


def purge_expired(db: Session, days: int | None = None) -> int:
    """Delete resumes older than the retention period (no-op when retention is 0)."""
    days = settings.retention_days if days is None else days
    if days <= 0:
        return 0
    cutoff = datetime.utcnow() - timedelta(days=days)
    old = list(db.scalars(select(M.Resume).where(M.Resume.created_at < cutoff)))
    for r in old:
        delete_resume(db, r)
    audit(db, "retention.purge", None, None, {"deleted": len(old), "days": days})
    db.commit()
    return len(old)
