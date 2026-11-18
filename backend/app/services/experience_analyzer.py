"""Experience intelligence. Month-set arithmetic guarantees overlapping periods are never double counted."""
from __future__ import annotations

import re
from datetime import date

from ..core.config import SCORING
from .resume_extractor import month_index

PART_WEIGHT = 0.5
INTERN_WEIGHT = 0.5
METHODOLOGY = (
    "Each employment period is converted to a set of calendar months (start and end months inclusive). "
    "Full-time/contract months are unioned so overlapping jobs are counted once. Part-time months not already covered "
    f"count at {PART_WEIGHT:.0%}; internship months not already covered count at {INTERN_WEIGHT:.0%} (internships are never "
    "treated as full-time employment). Year-only dates are assumed to start in July and end in June and are flagged uncertain. "
    "'Present' is resolved to the analysis date. Gaps are reported for information only and never penalised."
)


def _bounds(e: dict, as_of: date) -> tuple[int, int] | None:
    s, en = e.get("start"), e.get("end")
    if not s or not en or "year" not in s:
        return None
    si = month_index(s)
    ei = (as_of.year * 12 + as_of.month - 1) if en.get("current") else month_index(en)
    if ei < si:
        if s.get("precision") == "year" or en.get("precision") == "year":
            ei = si + 5
        else:
            return None
    return si, ei


def _months(entries: list[tuple[dict, tuple[int, int]]], types: set[str]) -> set[int]:
    out: set[int] = set()
    for e, (a, b) in entries:
        if e["type"] in types:
            out.update(range(a, b + 1))
    return out


def _effective(entries) -> tuple[float, dict]:
    full = _months(entries, {"full_time", "contract"})
    part = _months(entries, {"part_time"}) - full
    intern = _months(entries, {"internship"}) - full - part
    eff = len(full) + PART_WEIGHT * len(part) + INTERN_WEIGHT * len(intern)
    return eff / 12, {"full_time_years": round(len(full) / 12, 2), "part_time_years": round(len(part) / 12, 2),
                      "internship_years": round(len(intern) / 12, 2)}


def title_tokens_of(title: str | None) -> set[str]:
    """Lower-case word tokens of a job title, with the common long forms folded into their abbreviations so that
    "Machine Learning Engineer" and "AI/ML Engineer" share the token "ml"."""
    t = (title or "").lower()
    t = re.sub(r"machine[\s\-]+learning", "ml", t)
    t = re.sub(r"artificial[\s\-]+intelligence", "ai", t)
    return set(re.findall(r"[a-z]+", t))


def is_relevant(entry: dict, jd_skills: set[str], jd_title_tokens: set[str]) -> tuple[bool, list[str]]:
    """Legacy rule (used when the job's weighted requirements are not supplied): >= 2 shared skills, or 1 plus a title match."""
    overlap = sorted(set(entry.get("skills", [])) & jd_skills)
    title_tokens = title_tokens_of(entry.get("title"))
    title_hit = bool(title_tokens & jd_title_tokens)
    return (len(overlap) >= 2 or (len(overlap) >= 1 and title_hit)), overlap


def role_fit(entry: dict, requirements: list[dict], related: dict[str, list[str]] | None = None) -> tuple[float, list[str]]:
    """Weighted share (0..1) of the job's requirements that one role demonstrates.

    `requirements` = [{"names": [alt, ...], "weight": w}]; a requirement counts fully if any alternative appears in the
    role's skills, and at `SCORING["partial_credit"]` if only a related skill does (same rule as the technical score).
    This stops generic tools (Git, Docker) from making every role 'relevant' to every job."""
    have = set(entry.get("skills", []))
    got, total, hits = 0.0, 0.0, []
    for r in requirements:
        total += r["weight"]
        names = r["names"]
        if have & set(names):
            got += r["weight"]
            hits.extend(sorted(have & set(names)))
        elif related and any(have & set(related.get(n, [])) for n in names):
            got += r["weight"] * SCORING["partial_credit"]
    return (got / total if total else 0.0), sorted(set(hits))


def is_relevant_by_fit(entry: dict, fit: float, jd_title_tokens: set[str]) -> bool:
    """A role counts as relevant when it covers `rel_fit_min` of the weighted requirements (a lower bar if the title matches)."""
    title_hit = bool(title_tokens_of(entry.get("title")) & jd_title_tokens)
    return fit >= (SCORING["rel_fit_min_title"] if title_hit else SCORING["rel_fit_min"])


def analyze_experience(employment: list[dict], jd: dict, jd_skill_set: set[str], as_of: date, jd_title: str | None,
                       requirements: list[dict] | None = None, related: dict[str, list[str]] | None = None,
                       claimed_years: float | None = None) -> dict:
    """Score a candidate's relevant experience against the JD.

    When `requirements` (weighted, with alternatives) is given, a role is relevant by `role_fit`; otherwise the legacy
    shared-skill rule on `jd_skill_set` is used. `claimed_years` ("5+ years of experience" written in the summary) is used only
    when no dated employment exists, and is credited at SCORING["claimed_years_credit"] because it cannot be verified."""
    jd_tokens = title_tokens_of(jd_title) - {
        "senior", "junior", "sr", "jr", "lead", "associate", "i", "ii", "iii", "the", "of", "and", "engineer", "developer",
        "specialist", "staff", "principal", "intern", "manager"}
    dated, undated, roles = [], [], []
    for e in employment:
        b = _bounds(e, as_of)
        if b is None:
            undated.append(e)
            continue
        dated.append((e, b))
    rel_entries = []
    for e, b in dated:
        if requirements:
            fit, overlap = role_fit(e, requirements, related)
            rel = is_relevant_by_fit(e, fit, jd_tokens)
        else:
            fit, (rel, overlap) = None, is_relevant(e, jd_skill_set, jd_tokens)
        months = b[1] - b[0] + 1
        roles.append({"title": e.get("title"), "company": e.get("company"), "type": e["type"], "months": months,
                      "start": f"{e['start']['year']}-{e['start']['month']:02d}",
                      "end": "present" if e["end"].get("current") else f"{e['end']['year']}-{e['end']['month']:02d}",
                      "relevant": rel, "fit": None if fit is None else round(fit, 3), "matching_skills": overlap, "date_uncertain": e.get("date_uncertain", False),
                      "page": e.get("page"), "evidence": e.get("evidence")})
        if rel:
            rel_entries.append((e, b))
    total_eff, tot_break = _effective(dated)
    rel_eff, rel_break = _effective(rel_entries)
    # gaps (informational only)
    allm = sorted(_months(dated, {"full_time", "contract", "part_time", "internship"}))
    gaps = []
    for a, b in zip(allm, allm[1:]):
        if b - a > 6:
            gaps.append({"after": f"{a // 12}-{a % 12 + 1:02d}", "before": f"{b // 12}-{b % 12 + 1:02d}", "months": b - a - 1})
    exp = jd.get("experience", {})
    mn, pf = exp.get("min_years"), exp.get("preferred_years")
    status = "scored"
    notes = []
    if mn is None and pf is None:
        score, status = None, "not_required"
        notes.append("The job description does not state an experience requirement; this component is excluded and the other weights are renormalised.")
    elif not employment and claimed_years:
        credited = claimed_years * SCORING["claimed_years_credit"]
        total_eff, rel_eff, status = claimed_years, credited, "scored"
        base = min(1.0, credited / mn) if mn else 1.0
        score = base
        if pf and mn is not None and pf > mn:
            score = 0.7 * base + 0.3 * min(1.0, credited / pf)
        elif pf and mn is None:
            score = min(1.0, credited / pf)
        score = round(score * 100, 2)
        notes.append(f"No dated roles were found; the resume states about {claimed_years:g} years of experience. A stated figure cannot be verified, "
                     f"so it is credited at {SCORING['claimed_years_credit']:.0%} ({credited:.1f} y).")
    elif not employment:
        score, status = 0.0, "unverified"
        notes.append("No dated work experience was found (no Experience/Internship section with dates). This is missing evidence, not confirmed lack of experience - "
                     "typical for freshers, whose projects and education are scored separately.")
    elif not dated:
        score, status = 0.0, "unverified"
        notes.append("Employment entries were found but none had parsable dates.")
    else:
        base = min(1.0, rel_eff / mn) if mn else 1.0
        score = base
        if pf and mn is not None and pf > mn:
            score = 0.7 * base + 0.3 * min(1.0, rel_eff / pf)
        elif pf and mn is None:
            score = min(1.0, rel_eff / pf)
        score = round(score * 100, 2)
    uncertain = [r for r in roles if r["date_uncertain"]] + [{"title": e.get("title"), "reason": "unparsable dates"} for e in undated]
    if uncertain:
        notes.append(f"{len(uncertain)} role(s) have year-only or unparsable dates; durations are approximate.")
    if any(r["type"] == "internship" for r in roles):
        notes.append(f"Internship time is credited at {INTERN_WEIGHT:.0%}; it is not treated as full-time experience.")
    return {
        "score": score, "status": status, "total_effective_years": round(total_eff, 2), "relevant_effective_years": round(rel_eff, 2),
        "total_breakdown": tot_break, "relevant_breakdown": rel_break, "required_min_years": mn, "preferred_years": pf,
        "roles": roles, "gaps_info_only": gaps, "uncertain": bool(uncertain), "notes": notes, "methodology": METHODOLOGY,
        "undated_entries": len(undated), "claimed_years": claimed_years if (not employment and claimed_years) else None,
    }
