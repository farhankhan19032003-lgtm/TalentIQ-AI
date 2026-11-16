"""Shared serialisation helpers (blind-screening aware)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.config import COMPONENTS
from ..models import db as M
from ..services.pipeline import display_name

HIGH_SCORE = 70.0


def latest_title(c: M.Candidate) -> str | None:
    if not c.employment:
        return None
    cur = [e for e in c.employment if e.is_current]
    pick = cur[0] if cur else max(c.employment, key=lambda e: e.start or "")
    return pick.title


def needs_review(row: dict) -> bool:
    return row["confidence"] < 60 or row["completeness"] < 60 or (row["score_high"] - row["score_low"]) > 15


def result_row(res: M.MatchResult, c: M.Candidate, blind: bool) -> dict:
    comps = {x.name: {"score": x.score, "status": x.status, "weight_effective": x.weight_effective, "contribution": x.contribution,
                      "weight_configured": x.weight_configured} for x in res.components}
    reqs = res.detail.get("requirements", [])
    ov = max(res.overrides, key=lambda o: o.id) if res.overrides else None
    row = {
        "candidate_id": c.id, "result_id": res.id, "rank": res.rank, "name": display_name(c, blind), "email": None if blind else c.email,
        "latest_role": latest_title(c), "overall": res.overall, "score_low": res.score_low, "score_high": res.score_high,
        "skill_coverage": res.skill_coverage, "must_have_coverage": res.detail.get("must_have_coverage"), "components": comps,
        "relevant_years": res.relevant_years, "total_years": res.total_years, "confidence": res.confidence, "completeness": res.completeness,
        "review_status": c.review_status, "parse_status": "parsed",
        "requirements": [{"name": r["name"], "importance": r["importance"], "match_type": r["match_type"], "credit": r["credit"]} for r in reqs],
        "matched_skills": [r["name"] for r in reqs if r["match_type"] in ("exact", "synonym")],
        "related_skills": [r["name"] for r in reqs if r["match_type"] == "partial"],
        "semantic_skills": [r["name"] for r in reqs if r["match_type"] == "semantic"],
        "missing_skills": [r["name"] for r in reqs if r["match_type"] == "none"],
        "candidate_skills": [s.name for s in c.skills], "sensitivity": res.sensitivity,
        "override": None if not ov else {"new_score": ov.new_score, "original_score": ov.original_score, "reason": ov.reason, "reviewer": ov.reviewer,
                                         "at": ov.created_at.isoformat()},
    }
    row["needs_review"] = needs_review(row)
    return row


def rows_for_run(db: Session, run: M.MatchRun, blind: bool) -> list[dict]:
    results = list(db.scalars(select(M.MatchResult).where(M.MatchResult.run_id == run.id).order_by(M.MatchResult.rank)))
    cands = {c.id: c for c in db.scalars(select(M.Candidate).where(M.Candidate.id.in_([r.candidate_id for r in results])))}
    return [result_row(r, cands[r.candidate_id], blind) for r in results if r.candidate_id in cands]


def run_info(run: M.MatchRun) -> dict:
    return {"run_id": run.id, "job_id": run.job_id, "created_at": run.created_at.isoformat(), "algorithm_version": run.algorithm_version,
            "similarity_method": run.similarity_method, "model_name": run.model_name, "fallback_reason": run.fallback_reason,
            "weights": run.weights, "as_of": run.as_of, "n_candidates": run.n_candidates, "duration_ms": run.duration_ms}


def mask_fields(fields: dict, blind: bool) -> dict:
    if not blind:
        return fields
    out = {}
    for k, v in fields.items():
        out[k] = {**v, "value": "[hidden - blind screening]", "evidence": None} if k in ("name", "email", "phone", "linkedin", "github", "portfolio", "location") and v.get("value") else v
    return out


def job_out(j: M.Job) -> dict:
    return {"id": j.id, "title": j.title, "role": j.role, "category": j.category, "description": j.description,
            "min_experience_years": j.min_experience_years, "preferred_experience_years": j.preferred_experience_years,
            "education_level": j.education_level, "preferred_education_level": j.preferred_education_level,
            "requirements": j.requirements, "analysis": j.analysis, "is_template": j.is_template,
            "created_at": j.created_at.isoformat(), "updated_at": j.updated_at.isoformat()}
