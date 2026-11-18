"""Matching Engine V2 - modular, evidence-grounded, reproducible.

Stages: A requirements -> B document understanding (already parsed) -> C skill normalisation ->
D semantic embeddings -> E experience -> F education -> G projects/domain -> H evidence verification ->
I score calculation -> (J ranking is done across candidates in ranking_engine).
"""
from __future__ import annotations

import re
from datetime import date

from ..core.config import ALGORITHM_VERSION, COMPONENTS, SCORING
from .experience_analyzer import analyze_experience
from .resume_extractor import RANGE_RE
from .ranking_engine import compute_overall
from .semantic_matcher import SimilarityEngine
from .skill_extractor import Ontology

MUST_WEIGHT, PREFERRED_WEIGHT = SCORING["must_weight"], SCORING["preferred_weight"]
CREDIT = {"context": SCORING["credit_context"], "listed_only": SCORING["credit_listed_only"], "partial": SCORING["partial_credit"]}
SEMANTIC_CREDIT_MIN, SEMANTIC_CREDIT_MAX = SCORING["semantic_credit_min"], SCORING["semantic_credit_max"]


def _norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def verify_snippet(snippet: str | None, page: int | None, pages: list[str]) -> bool:
    """Evidence must be a verbatim substring of the (scrubbed) resume text on the cited page."""
    if not snippet:
        return False
    s = _norm_ws(snippet).replace("• ", "")
    texts = pages if page is None or page > len(pages) or page < 1 else [pages[page - 1]]
    return any(s in _norm_ws(t).replace("• ", "") for t in texts)


def clean_for_similarity(t: str) -> str:
    """Remove date ranges and separators so layout/date formatting can never influence similarity."""
    t = RANGE_RE.sub(" ", t)
    t = re.sub(r"[|•]+", " ", t)
    return re.sub(r"\s+", " ", t).strip(" ,-–—")


def build_units(parsed: dict) -> list[dict]:
    """Sentence-like evidence units. `text` is verbatim resume text (used as evidence); `clean` is what similarity sees."""
    units, seen = [], set()
    for sec in ("summary", "experience", "internships", "projects", "skills"):
        for it in parsed.get("sections", {}).get(sec, []):
            t = it["text"].lstrip("• ").strip()
            c = clean_for_similarity(t)
            if (len(c.split()) >= 3 or (sec == "skills" and c)) and t not in seen:
                seen.add(t)
                units.append({"text": t, "clean": c, "page": it["page"], "section": sec})
    return units


def narrative(parsed: dict, sections=("summary", "experience", "internships")) -> str:
    """Resume prose (summary + experience) used for the document-level semantic comparison; skills lists are excluded to avoid double counting."""
    out = []
    for s in sections:
        for it in parsed.get("sections", {}).get(s, []):
            c = clean_for_similarity(it["text"].lstrip("• "))
            if len(c.split()) >= 2:
                out.append(c)
    return "\n".join(out)


def jd_narrative(job: dict) -> str:
    """Job text used for semantic comparison: title, responsibilities and required qualifications."""
    a = job["analysis"]
    parts = [a.get("title") or job.get("title", "")] + a.get("responsibilities", []) + a.get("required_qualifications", [])
    text = "\n".join(p for p in parts if p).strip()
    return text or job.get("description", "")


def match_candidate(parsed: dict, pages: list[str], job: dict, engine: SimilarityEngine, onto: Ontology,
                    weights: dict, as_of: date) -> dict:
    """job = {"title", "description", "analysis": {...}, "requirements": [...], "min_years", "preferred_years", "education_level"...}"""
    reqs = [r for r in job["requirements"] if r.get("importance") in ("must", "preferred")]
    cand_skills = parsed.get("skills", {})
    units = build_units(parsed)
    cal = engine.calibration
    thr = cal["evidence_threshold"]
    evidence: list[dict] = []
    req_results: list[dict] = []

    # --- A/C/D/H: requirement-by-requirement skill evidence ------------------------------------
    unit_texts = [u["clean"] for u in units]
    def eval_one(r: dict, name: str) -> dict:
        w = (MUST_WEIGHT if r["importance"] == "must" else PREFERRED_WEIGHT) * float(r.get("weight", 1.0))
        rec = {"requirement_id": r["id"], "name": name, "category": r.get("category") or onto.category(name),
               "importance": r["importance"], "weight": w, "match_type": "none", "credit": 0.0, "similarity": None,
               "evidence_text": None, "page": None, "section": None, "verification": "unverified",
               "note": "No evidence found in the resume text.", "related_found": None}
        hit = cand_skills.get(name) if name in onto.skills else None
        if name not in onto.skills:  # custom requirement (recruiter-added): literal search in the text
            rx = re.compile(r"(?<![A-Za-z0-9])" + re.escape(name).replace(r"\ ", r"\s+") + r"(?![A-Za-z0-9])", re.I)
            ms = [(u, rx.search(u["text"])) for u in units]
            ms = [(u, m) for u, m in ms if m]
            if ms:
                ctx = [x for x in ms if x[0]["section"] != "skills"]
                u, _ = (ctx or ms)[0]
                hit = {"mentions": [{"page": u["page"], "section": u["section"], "snippet": u["text"], "method": "exact", "context": bool(ctx)}],
                       "listed_only": not ctx}
        if hit:
            ments = hit["mentions"]
            best = next((m for m in ments if m.get("context")), ments[0])
            exact = any(m["method"] == "exact" for m in ments)
            rec.update(match_type="exact" if exact else "synonym", credit=CREDIT["listed_only" if hit["listed_only"] else "context"],
                       evidence_text=best["snippet"], page=best["page"], section=best["section"],
                       note=("Found only in a skills list - mention without supporting context." if hit["listed_only"]
                             else "Found with supporting context in the resume.") + ("" if exact else f" (matched as synonym '{best.get('alias', '')}')"))
            if hit.get("proficiency"):
                rec["proficiency"] = hit["proficiency"]
        else:
            rel = [(x, cand_skills[x]) for x in onto.related(name) if x in cand_skills]
            if rel:
                x, h = rel[0]
                m = next((m for m in h["mentions"] if m.get("context")), h["mentions"][0])
                rec.update(match_type="partial", credit=CREDIT["partial"], evidence_text=m["snippet"], page=m["page"], section=m["section"],
                           related_found=[k for k, _ in rel],
                           note=f"Related skill evidence only ({', '.join(k for k, _ in rel)}). Related skills are not treated as {name}.")
        if rec["match_type"] == "none" and unit_texts:
            sims = engine.similarity([onto.semantic_query(name)], unit_texts)[0]
            i = int(sims.argmax())
            if sims[i] >= thr and units[i]["section"] != "skills":
                frac = min(1.0, (sims[i] - thr) / 0.25)
                u = units[i]
                rec.update(match_type="semantic", similarity=round(float(sims[i]), 4),
                           credit=round(SEMANTIC_CREDIT_MIN + (SEMANTIC_CREDIT_MAX - SEMANTIC_CREDIT_MIN) * frac, 4),
                           evidence_text=u["text"], page=u["page"], section=u["section"],
                           note=f"Semantically similar text (cosine {sims[i]:.2f}) but the skill is not named - treated as weak, inferred evidence.")
        # H: evidence verification
        if rec["evidence_text"]:
            if verify_snippet(rec["evidence_text"], rec["page"], pages):
                rec["verification"] = "verified" if rec["match_type"] in ("exact", "synonym") else "inferred"
            else:
                rec.update(match_type="none", credit=0.0, evidence_text=None, verification="failed_verification",
                           note="Candidate evidence snippet could not be verified against the resume text and was discarded.")
        return rec

    for r in reqs:
        if r.get("any_of"):
            alts = [eval_one(r, n) for n in r["any_of"]]
            rec = dict(max(alts, key=lambda x: (x["credit"], x["match_type"] in ("exact", "synonym"))))
            rec["name"] = r["name"]
            rec["any_of"] = r["any_of"]
            rec["satisfied_by"] = rec.pop("name", None) and next((a["name"] for a in alts if a["credit"] == rec["credit"]), None)
            rec["name"] = r["name"]
            if rec["match_type"] != "none":
                rec["note"] = f"Alternative requirement - satisfied by {rec['satisfied_by']}. " + rec["note"]
            else:
                rec["note"] = "No evidence found for any of the alternatives (" + ", ".join(r["any_of"]) + ")."
        else:
            rec = eval_one(r, r["name"])
        req_results.append(rec)
        evidence.append({"requirement_id": rec["requirement_id"], "requirement": rec["name"], "category": "skill", "match_type": rec["match_type"],
                         "evidence_text": rec["evidence_text"], "page": rec["page"], "similarity": rec["similarity"],
                         "verification": rec["verification"]})

    total_w = sum(r["weight"] for r in req_results)
    tech_score = (sum(r["weight"] * r["credit"] for r in req_results) / total_w * 100) if total_w else None
    exact_n = sum(1 for r in req_results if r["match_type"] in ("exact", "synonym"))
    coverage = round(exact_n / len(req_results) * 100, 1) if req_results else None
    must = [r for r in req_results if r["importance"] == "must"]
    must_cov = round(sum(1 for r in must if r["match_type"] in ("exact", "synonym")) / len(must) * 100, 1) if must else None
    comps: dict[str, dict] = {}
    if tech_score is None:
        comps["technical_skills"] = {"score": None, "status": "not_required"}
    elif not cand_skills:
        comps["technical_skills"] = {"score": 0.0, "status": "unverified"}
    else:
        comps["technical_skills"] = {"score": round(tech_score, 2), "status": "scored"}

    # --- D: semantic relevance (disjoint evidence: summary + experience narrative only) ----------
    cand_text = narrative(parsed)
    jd_text = jd_narrative(job)
    resp = job["analysis"].get("responsibilities", [])
    semantic = {"doc_similarity": None, "responsibility_pairs": [], "method": engine.method}
    if not cand_text.strip():
        comps["semantic_relevance"] = {"score": 0.0, "status": "unverified"}
    else:
        doc_sim = float(engine.similarity([jd_text], [cand_text])[0][0])
        semantic["doc_similarity"] = round(doc_sim, 4)
        s_doc = engine.to_score(doc_sim)
        s_resp = None
        exp_units = [u for u in units if u["section"] in ("summary", "experience", "internships")]
        if resp and exp_units:
            M = engine.similarity(resp, [u["clean"] for u in exp_units])
            best = M.max(axis=1)
            s_resp = engine.to_score(float(best.mean()), "resp")
            for i, rline in enumerate(resp):
                j = int(M[i].argmax())
                semantic["responsibility_pairs"].append({"responsibility": rline, "best_resume_text": exp_units[j]["text"],
                                                         "page": exp_units[j]["page"], "similarity": round(float(M[i][j]), 4)})
            semantic["mean_best_responsibility_similarity"] = round(float(best.mean()), 4)
        score = s_doc if s_resp is None else 0.5 * s_doc + 0.5 * s_resp
        semantic.update(doc_component=round(s_doc, 2), responsibility_component=None if s_resp is None else round(s_resp, 2))
        comps["semantic_relevance"] = {"score": round(score, 2), "status": "scored"}

    # --- E: experience --------------------------------------------------------------------------
    jd_skill_set = {n for r in reqs for n in (r.get("any_of") or [r["name"]])}
    jd_skill_set |= {x for n in list(jd_skill_set) for x in onto.related(n)}
    exp_reqs = [{"names": r.get("any_of") or [r["name"]], "weight": (MUST_WEIGHT if r["importance"] == "must" else PREFERRED_WEIGHT) * float(r.get("weight", 1.0))}
                for r in reqs]
    exp = analyze_experience(parsed.get("employment", []), {"experience": {"min_years": job.get("min_years"), "preferred_years": job.get("preferred_years")}},
                             jd_skill_set, as_of, job["analysis"].get("title") or job.get("title"),
                             requirements=exp_reqs, related={n: onto.related(n) for n in jd_skill_set},
                             claimed_years=(parsed.get("fields", {}).get("claimed_years") or {}).get("value"))
    comps["relevant_experience"] = {"score": exp["score"], "status": exp["status"]}
    for r in exp["roles"]:
        if r["relevant"]:
            evidence.append({"requirement_id": "experience", "requirement": f"Relevant experience: {r['title']}", "category": "experience",
                             "match_type": "exact", "evidence_text": r["evidence"], "page": r["page"], "similarity": None,
                             "verification": "verified" if verify_snippet(r["evidence"], r["page"], pages) else "unverified"})

    # --- F: education ---------------------------------------------------------------------------
    edu_req = job.get("education_level") or None      # 0 / None = no qualification required
    edu_pref = job.get("preferred_education_level")
    edu_list = parsed.get("education", [])
    cand_level = max([e["level"] for e in edu_list], default=None)
    edu = {"required_level": edu_req, "candidate_level": cand_level, "entries": [
        {"degree": e["degree"], "institution": e["institution"], "year": e["year"], "page": e["page"], "evidence": e["evidence"]} for e in edu_list]}
    if edu_req is None:
        comps["education"] = {"score": None, "status": "not_required"}
        edu["note"] = "No education requirement stated in the job description; component excluded."
    elif cand_level is None:
        comps["education"] = {"score": 0.0, "status": "unverified"}
        edu["note"] = "No degree could be extracted. This is missing evidence, not a confirmed mismatch."
    else:
        sc = 100.0 if cand_level >= edu_req else 100.0 * cand_level / edu_req
        if edu_pref and edu_req <= cand_level < edu_pref:
            sc = min(sc, 85.0)
        comps["education"] = {"score": round(sc, 2), "status": "scored"}
        edu["note"] = "Candidate level meets the requirement." if cand_level >= edu_req else "Candidate's highest extracted level is below the stated requirement."
    for e in edu_list[:2]:
        evidence.append({"requirement_id": "education", "requirement": "Education", "category": "education", "match_type": "exact",
                         "evidence_text": e["evidence"], "page": e["page"], "similarity": None,
                         "verification": "verified" if verify_snippet(e["evidence"], e["page"], pages) else "unverified"})

    # --- G: project & domain relevance ------------------------------------------------------------
    projects = parsed.get("projects", [])
    proj_units = [p["name"] + ". " + " ".join(p["description"]) for p in projects]
    proj_text = "\n".join(proj_units)
    domains = job["analysis"].get("domain_knowledge", [])
    proj = {"count": len(projects), "similarity": None, "domain_hits": [], "top_projects": []}
    if not proj_text.strip():
        comps["project_domain"] = {"score": 0.0, "status": "unverified"}
        proj["note"] = "No projects section could be extracted. This is missing evidence, not a confirmed mismatch."
    else:
        sim = float(engine.similarity([jd_text], [proj_text])[0][0])
        proj["similarity"] = round(sim, 4)
        s_doc = engine.to_score(sim)
        s_resp = None
        if resp:
            Mp = engine.similarity(resp, [u for p in projects for u in [p["name"] + ". " + " ".join(p["description"])]] + [d for p in projects for d in p["description"]])
            s_resp = engine.to_score(float(Mp.max(axis=1).mean()), "resp")
        base = s_doc if s_resp is None else 0.5 * s_doc + 0.5 * s_resp
        all_text = "\n".join(it["text"] for sec in ("summary", "experience", "internships", "projects") for it in parsed.get("sections", {}).get(sec, []))
        hits = [d for d in domains if re.search(rf"\b{re.escape(d)}\b", all_text, re.I)]
        proj["domain_hits"] = hits
        bonus = (100 - base) * 0.5 * (len(hits) / len(domains)) if domains else 0.0   # domain exposure can only add, never subtract
        proj.update(doc_component=round(s_doc, 2), responsibility_component=None if s_resp is None else round(s_resp, 2), domain_bonus=round(bonus, 2))
        comps["project_domain"] = {"score": round(min(100.0, base + bonus), 2), "status": "scored"}
        per = engine.similarity([jd_text], proj_units)[0]
        order = sorted(range(len(projects)), key=lambda i: -per[i])[:3]
        proj["top_projects"] = [{"name": projects[i]["name"], "similarity": round(float(per[i]), 4), "page": projects[i]["page"],
                                 "evidence": projects[i]["evidence"]} for i in order]
        for i in order[:2]:
            evidence.append({"requirement_id": "projects", "requirement": f"Project: {projects[i]['name']}", "category": "project",
                             "match_type": "semantic", "evidence_text": projects[i]["evidence"], "page": projects[i]["page"],
                             "similarity": round(float(per[i]), 4),
                             "verification": "inferred" if verify_snippet(projects[i]["evidence"], projects[i]["page"], pages) else "unverified"})

    # --- I: score ----------------------------------------------------------------------------------
    overall = compute_overall(comps, weights)
    for k in COMPONENTS:
        comps[k]["weight_configured"] = weights[k]
        comps[k]["weight_effective"] = overall["effective_weights"].get(k)
        comps[k]["contribution"] = overall["contributions"].get(k)

    # --- confidence & completeness (kept separate from the score) --------------------------------------
    claimed = [e for e in evidence if e["evidence_text"]]
    ver_ratio = (sum(1 for e in claimed if e["verification"] in ("verified", "inferred")) / len(claimed)) if claimed else 0.0
    date_certainty = 1.0 - (sum(1 for r in exp["roles"] if r["date_uncertain"]) + exp["undated_entries"]) / max(1, len(exp["roles"]) + exp["undated_entries"]) if parsed.get("employment") else 1.0
    confidence = round(100 * (parsed.get("parse_confidence", 0) + ver_ratio + date_certainty) / 3, 1)
    f = parsed.get("fields", {})
    checks = {
        "name": bool(f.get("name", {}).get("value")), "contact": bool(f.get("email", {}).get("value") or f.get("phone", {}).get("value")),
        "summary": bool(f.get("summary", {}).get("value")), "employment": bool(parsed.get("employment")),
        "education": bool(edu_list), "skills": len(cand_skills) >= 3, "projects": bool(projects),
        "dated_employment": bool(parsed.get("employment")) and exp["undated_entries"] == 0 and not exp["uncertain"],
    }
    completeness = round(100 * sum(checks.values()) / len(checks), 1)
    return {
        "algorithm_version": ALGORITHM_VERSION, "overall": overall["overall"], "score_low": overall["score_low"], "score_high": overall["score_high"],
        "components": comps, "requirements": req_results, "skill_coverage": coverage, "must_have_coverage": must_cov,
        "experience": exp, "education": edu, "projects": proj, "semantic": semantic, "evidence": evidence,
        "confidence": confidence, "completeness": completeness, "completeness_checks": checks,
        "similarity_method": engine.method,
    }
