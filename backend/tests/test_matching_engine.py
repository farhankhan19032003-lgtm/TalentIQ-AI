from datetime import date

import numpy as np
import pytest

from app.core.config import DEFAULT_WEIGHTS, SCORING
from app.services.document_parser import PageText, ParsedDocument
from app.services.explanation_engine import explain
from app.services.jd_analyzer import analyze_jd
from app.services.matching_pipeline import match_candidate
from app.services.pipeline import ontology, ontology_texts, resume_extractor, skill_extractor
from app.services.semantic_matcher import SimilarityEngine

AS_OF = date(2026, 11, 1)


def parse_lines(lines):
    doc = ParsedDocument("pdf", [PageText(1, "\n".join(lines), "test")], 1.0)
    return resume_extractor.extract(doc), "\n".join(lines)


def job_from(text, title=None):
    a = analyze_jd(text, skill_extractor, ontology, title)
    return {"title": a["title"], "description": text, "analysis": a, "requirements": a["requirements"], "min_years": a["experience"]["min_years"],
            "preferred_years": a["experience"]["preferred_years"], "education_level": a["education"]["required_level"],
            "preferred_education_level": a["education"]["preferred_level"]}


def match(lines, job, engine=None):
    parsed, text = parse_lines(lines)
    eng = engine or SimilarityEngine("tfidf", ontology_texts())
    eng.prepare([job["description"]] + [ontology.semantic_query(r["name"]) for r in job["requirements"]])
    return match_candidate(parsed, text.split("\f"), job, eng, ontology, DEFAULT_WEIGHTS, AS_OF), text


JD = job_from("""Job Title: ML Engineer
Requirements:
- 2+ years of experience
- Machine Learning, Python, Docker
- Bachelor's degree
Nice to have:
- Kubernetes
""")


def req(m, name):
    return next(r for r in m["requirements"] if r["name"] == name)


RES_FULL = ["Jane Roe", "jane.roe@example.com | Pune, India", "Experience", "ML Engineer | Acme | Jan 2021 – Dec 2023",
            "• Trained machine learning models in Python and packaged them with Docker", "Education", "B.Tech in Computer Science | Sunrise Institute | 2017 – 2021",
            "Skills", "Python, Docker, Kubernetes"]


def test_exact_match_with_context_has_full_credit_and_verified_evidence():
    m, text = match(RES_FULL, JD)
    r = req(m, "Python")
    assert r["match_type"] == "exact" and r["credit"] == 1.0 and r["verification"] == "verified"
    assert r["evidence_text"] in text and r["page"] == 1


def test_listed_only_gets_reduced_credit():
    m, _ = match(RES_FULL, JD)
    r = req(m, "Kubernetes")
    assert r["match_type"] == "exact" and r["credit"] == 0.85 and "skills list" in r["note"]


def test_related_skill_is_partial_not_exact():
    lines = ["Jane Roe", "Experience", "Software Engineer | Acme | Jan 2021 – Dec 2023", "• Built XGBoost and scikit-learn classifiers for fraud", "Skills", "Python, Docker"]
    m, _ = match(lines, JD)
    r = req(m, "Machine Learning")
    assert r["match_type"] == "partial" and r["credit"] == 0.35 and set(r["related_found"]) >= {"XGBoost", "scikit-learn"}
    assert "not treated as Machine Learning" in r["note"] and r["verification"] == "inferred"


def test_missing_skill_is_no_evidence_not_claimed():
    lines = ["Jane Roe", "Experience", "Developer | Acme | Jan 2021 – Dec 2023", "• Maintained websites", "Skills", "HTML"]
    m, _ = match(lines, JD)
    r = req(m, "Docker")
    assert r["match_type"] == "none" and r["credit"] == 0 and r["evidence_text"] is None and "No evidence" in r["note"]


def test_synonym_alias_match():
    lines = ["Jane Roe", "Experience", "Eng | Acme | Jan 2021 – Dec 2023", "• Containerisation of services with docker-compose", "Skills", "Python"]
    m, _ = match(lines, JD)
    assert req(m, "Docker")["match_type"] == "synonym"


class StubEngine:
    method = "tfidf"
    calibration = {"doc": (0.02, 0.4), "resp": (0.02, 0.3), "evidence_threshold": 0.28}
    model_name, fallback_reason = "stub", None

    def prepare(self, *_): pass
    def similarity(self, a, b): return np.full((len(a), len(b)), 0.5)
    def to_score(self, c, level="doc"): return 50.0


def test_semantic_only_evidence_is_weak_and_inferred():
    lines = ["Jane Roe", "Experience", "Eng | Acme | Jan 2021 – Dec 2023", "• Shipped packaged workloads to production clusters daily", "Skills", "Python"]
    m, text = match(lines, JD, StubEngine())
    r = req(m, "Docker")
    assert r["match_type"] == "semantic" and 0.10 <= r["credit"] <= 0.25 and r["verification"] == "inferred" and r["similarity"] == 0.5
    assert r["evidence_text"] in text                                    # even semantic evidence is real resume text


def test_unverifiable_evidence_is_discarded_never_fabricated():
    from app.services import matching_pipeline as mp
    parsed, text = parse_lines(RES_FULL)
    parsed["skills"]["Python"]["mentions"][0]["snippet"] = "Led Python migration at Google"      # snippet NOT in the resume
    parsed["skills"]["Python"]["mentions"] = parsed["skills"]["Python"]["mentions"][:1]
    eng = SimilarityEngine("tfidf", ontology_texts()); eng.prepare([JD["description"]])
    m = mp.match_candidate(parsed, [text], JD, eng, ontology, DEFAULT_WEIGHTS, AS_OF)
    r = req(m, "Python")
    assert r["match_type"] == "none" and r["verification"] == "failed_verification" and r["evidence_text"] is None


def test_alternative_requirement_satisfied_by_either():
    job = job_from("Job Title: Dev\nRequirements:\n- Django or Flask experience\n- 1+ years of experience\n")
    assert job["requirements"][0]["any_of"] == ["Django", "Flask"]
    m, _ = match(["Jo Doe", "Experience", "Dev | Acme | Jan 2022 – Dec 2023", "• Built Flask services", "Skills", "Flask"], job)
    r = m["requirements"][0]
    assert r["match_type"] == "exact" and r["satisfied_by"] == "Flask" and r["name"] == "Django or Flask"


def test_missing_sections_are_unverified_not_mismatch():
    m, _ = match(["Jane Roe", "Skills", "Python, Docker, Machine Learning"], JD)
    assert m["components"]["education"]["status"] == "unverified" and m["components"]["relevant_experience"]["status"] == "unverified"
    assert m["score_low"] <= m["overall"] < m["score_high"]
    assert m["completeness"] < 60
    text = " ".join(explain(m)["missing_information"])
    assert "not as a mismatch" in text or "unverified" in text


def test_overall_equals_documented_formula():
    m, _ = match(RES_FULL, JD)
    c = m["components"]
    skip = set(SCORING["renormalise_unverified"])
    active = {k: v for k, v in c.items() if v["status"] != "not_required" and not (v["status"] == "unverified" and k in skip)}
    tw = sum(DEFAULT_WEIGHTS[k] for k in active)
    manual = sum(DEFAULT_WEIGHTS[k] / tw * (v["score"] or 0) for k, v in active.items())
    assert m["overall"] == pytest.approx(manual, abs=0.01)
    assert all(0 <= v["score"] <= 100 for v in active.values() if v["score"] is not None)
    assert sum(v["contribution"] for v in active.values()) == pytest.approx(m["overall"], abs=0.02)


def test_scoring_is_reproducible():
    a, _ = match(RES_FULL, JD)
    b, _ = match(RES_FULL, JD)
    assert a["overall"] == b["overall"] and a["components"] == b["components"]


def test_score_independent_of_resume_formatting():
    variant = [l.replace("Jan 2021 – Dec 2023", "01/2021 - 12/2023").replace("ML Engineer | Acme | ", "ML Engineer, Acme\n") for l in RES_FULL]
    a, _ = match(RES_FULL, JD)
    b, _ = match("\n".join(variant).split("\n"), JD)
    assert a["overall"] == pytest.approx(b["overall"], abs=0.01)


def test_explanation_is_grounded_in_resume_text():
    m, text = match(RES_FULL, JD)
    ex = explain(m)
    for e in ex["evidence_supporting_score"]:
        assert e["text"].replace("• ", "") in text.replace("• ", "")
    assert "not a probability" in ex["disclaimer"].lower()
    assert ex["component_effects"] and ex["why_matched"]
    assert "hire" not in " ".join(ex["why_matched"] + ex["why_not_matched"]).lower()


def test_exp_below_requirement_is_explained():
    m, _ = match(["Jane Roe", "Experience", "ML Engineer | Acme | Jan 2023 – Dec 2023", "• Used Python and machine learning", "Skills", "Python"], JD)
    assert any("below the required minimum" in x for x in explain(m)["why_not_matched"])
