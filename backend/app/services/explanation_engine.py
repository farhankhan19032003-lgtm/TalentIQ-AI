"""Builds readable explanations strictly from computed match data. No generative text, no invented quotes."""
from __future__ import annotations

from ..core.config import COMPONENT_LABELS, COMPONENTS, SCORING

DISCLAIMER = ("The match score is a decision-support signal (0-100) comparing resume evidence with job requirements. "
              "It is not a probability of being hired or of job performance. A recruiter makes every decision.")


def fit_label(score: float) -> str:
    """Plain-language band for an overall score (display only; never used to reject anyone)."""
    return ("Strong match" if score >= SCORING["high_match"] + 10 else "Good match" if score >= SCORING["high_match"]
            else "Partial match" if score >= 50 else "Weak match" if score >= 30 else "Poor match")


def headline(m: dict) -> str:
    """One readable sentence for the top of the candidate page, built only from computed numbers."""
    reqs = m["requirements"]
    must = [r for r in reqs if r["importance"] == "must"]
    direct = [r for r in must if r["match_type"] in ("exact", "synonym")]
    part = [r for r in must if r["match_type"] == "partial"]
    e = m["experience"]
    bits = [f"{fit_label(m['overall'])} ({m['overall']:.0f}/100)."]
    if must:
        bits.append(f"Direct evidence for {len(direct)} of {len(must)} must-have skills" + (f" and related evidence for {len(part)} more" if part else "") + ".")
    if e["status"] == "scored" and e.get("required_min_years"):
        verdict = "meets" if e["relevant_effective_years"] >= e["required_min_years"] else "is below"
        bits.append(f"Relevant experience {e['relevant_effective_years']:.1f} y ({e['total_effective_years']:.1f} y total) {verdict} the {e['required_min_years']:g}+ y required.")
    elif e["status"] == "unverified":
        bits.append("No dated work experience was found, so experience could not be verified.")
    miss = [r["name"] for r in must if r["match_type"] == "none"]
    if miss:
        bits.append("Missing must-haves: " + ", ".join(miss[:4]) + (" and more." if len(miss) > 4 else "."))
    return " ".join(bits)


def explain(m: dict) -> dict:
    """Turn one candidate's match result into readable text: headline, why matched / why not, missing information and per-component points."""
    reqs = m["requirements"]
    matched = [r for r in reqs if r["match_type"] in ("exact", "synonym")]
    partial = [r for r in reqs if r["match_type"] == "partial"]
    semantic = [r for r in reqs if r["match_type"] == "semantic"]
    missing = [r for r in reqs if r["match_type"] == "none"]
    comps = m["components"]

    why = []
    if matched:
        must_m = [r["name"] for r in matched if r["importance"] == "must"]
        why.append(f"{len(matched)} of {len(reqs)} requested skills have direct resume evidence"
                   + (f" (must-have: {', '.join(must_m)})" if must_m else "") + ".")
    ctx = [r["name"] for r in matched if "supporting context" in r["note"]]
    if ctx:
        why.append(f"Supporting context (used in work or projects, not just listed) was found for: {', '.join(ctx[:8])}.")
    rel_years = m["experience"]["relevant_effective_years"]
    if m["experience"]["status"] == "scored" and rel_years > 0:
        rel_roles = [r["title"] for r in m["experience"]["roles"] if r["relevant"]]
        why.append(f"{rel_years:.1f} effective year(s) of job-relevant experience from: {', '.join(x for x in rel_roles if x) or 'listed roles'}.")
    sem = m["semantic"]
    if sem.get("doc_similarity") is not None:
        level = "high" if comps["semantic_relevance"]["score"] >= 66 else "moderate" if comps["semantic_relevance"]["score"] >= 33 else "low"
        why.append(f"Semantic similarity between the job narrative and the candidate's summary/experience is {level} "
                   f"(raw cosine {sem['doc_similarity']:.2f}, method: {m['similarity_method']}).")
    if m["projects"].get("top_projects"):
        tp = m["projects"]["top_projects"][0]
        why.append(f"Most job-relevant project: '{tp['name']}' (cosine {tp['similarity']:.2f}).")

    why_not = []
    if missing:
        mm = [r["name"] for r in missing if r["importance"] == "must"]
        if mm:
            why_not.append(f"No evidence was found in the resume for must-have skills: {', '.join(mm)}. "
                           "This means the resume text does not show them; it does not prove the candidate lacks them.")
        pm = [r["name"] for r in missing if r["importance"] == "preferred"]
        if pm:
            why_not.append(f"No evidence found for preferred skills: {', '.join(pm)}.")
    for r in partial:
        why_not.append(f"{r['name']}: only related evidence ({', '.join(r['related_found'])}); related skills are not treated as equivalent.")
    for r in semantic:
        why_not.append(f"{r['name']}: skill not named; only weak semantic similarity to resume text (cosine {r['similarity']:.2f}).")
    lo = [r["name"] for r in matched if "only in a skills list" in r["note"]]
    if lo:
        why_not.append(f"{', '.join(lo[:8])}: appear only in a skills list without supporting context (reduced credit).")
    e = m["experience"]
    if e["status"] == "scored" and e["required_min_years"] and e["relevant_effective_years"] < e["required_min_years"]:
        why_not.append(f"Relevant experience ({e['relevant_effective_years']:.1f} y) is below the required minimum ({e['required_min_years']:g} y).")
    if m["education"].get("candidate_level") is not None and m["education"].get("required_level") and m["education"]["candidate_level"] < m["education"]["required_level"]:
        why_not.append("Highest extracted education level is below the stated requirement.")

    missing_info = []
    for k in COMPONENTS:
        if comps[k]["status"] == "unverified":
            missing_info.append(f"{COMPONENT_LABELS[k]}: required evidence could not be extracted from the resume (treated as unverified, not as a mismatch).")
    if e["uncertain"]:
        missing_info.append("Some employment dates are year-only or unparsable; experience durations are approximate.")
    for note in e["notes"]:
        if "does not state" not in note and note not in missing_info:
            missing_info.append(note)
    chk = [k.replace("_", " ") for k, v in m["completeness_checks"].items() if not v]
    if chk:
        missing_info.append(f"Fields not found in the resume: {', '.join(chk)}.")

    effects = []
    for k in COMPONENTS:
        c = comps[k]
        if c["status"] == "not_required":
            effects.append({"component": k, "label": COMPONENT_LABELS[k], "text": f"{COMPONENT_LABELS[k]}: not required by this job - excluded; remaining weights renormalised."})
        elif c["status"] == "unverified" and not c["weight_effective"]:
            effects.append({"component": k, "label": COMPONENT_LABELS[k], "score": None, "weight": 0.0, "contribution": 0.0, "status": "unverified",
                            "text": f"{COMPONENT_LABELS[k]}: no evidence in the resume - left out of the score (not counted as a mismatch); the score range shows the effect."})
        else:
            effects.append({"component": k, "label": COMPONENT_LABELS[k], "score": c["score"], "weight": round(c["weight_effective"] * 100, 1),
                            "contribution": round(c["contribution"], 2), "status": c["status"],
                            "text": f"{COMPONENT_LABELS[k]}: {c['score']:.1f}/100 × effective weight {c['weight_effective'] * 100:.1f}% = {c['contribution']:.2f} points"
                                    + (" (unverified)" if c["status"] == "unverified" else "")})

    ev = [{"requirement": x["requirement"], "match_type": x["match_type"], "page": x["page"], "text": x["evidence_text"], "verification": x["verification"]}
          for x in m["evidence"] if x["evidence_text"]]
    summary = (f"Overall match {m['overall']:.1f}/100 (range {m['score_low']:.1f}-{m['score_high']:.1f} if missing evidence were found); "
               f"confidence {m['confidence']:.0f}/100, data completeness {m['completeness']:.0f}/100. "
               f"{len(matched)} direct, {len(partial)} related, {len(semantic)} semantic, {len(missing)} without evidence out of {len(reqs)} skill requirements.")
    return {"headline": headline(m), "summary": summary, "why_matched": why, "why_not_matched": why_not, "missing_information": missing_info,
            "component_effects": effects, "evidence_supporting_score": ev, "disclaimer": DISCLAIMER}
