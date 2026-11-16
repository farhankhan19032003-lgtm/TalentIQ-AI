from datetime import date

import pytest

from app.core.config import COMPONENTS, DEFAULT_WEIGHTS
from app.core.errors import AppError
from app.services import ranking_engine as re_
from app.services.experience_analyzer import analyze_experience

AS_OF = date(2026, 11, 1)


def emp(title, start, end, typ="full_time", skills=(), year_only=False):
    mk = lambda ym, e: {"year": ym[0], "month": (6 if e else 7) if year_only else ym[1], "precision": "year" if year_only else "month"} if ym != "present" else {"current": True}
    return {"title": title, "company": "X", "start": mk(start, False), "end": mk(end, True), "type": typ, "skills": list(skills),
            "date_uncertain": year_only, "page": 1, "evidence": "ev", "description": []}


def run(emps, mn=2, pf=None, skills={"Python", "SQL"}):
    return analyze_experience(emps, {"experience": {"min_years": mn, "preferred_years": pf}}, set(skills), AS_OF, "Python Developer")


@pytest.mark.parametrize("jd_title,role_title", [("AI/ML Engineer", "Machine Learning Engineer"), ("Machine Learning Engineer", "ML Engineer"),
                                                 ("AI Engineer", "Artificial Intelligence Engineer")])
def test_title_abbreviations_count_as_the_same_field(jd_title, role_title):
    """A 'Machine Learning Engineer' role is relevant for an 'AI/ML Engineer' job even when only one JD skill appears in it
    (found on the 50-resume pack: three strong candidates were scored 0 relevant years)."""
    e = emp(role_title, (2019, 1), (2023, 12), skills=["Python"])
    r = analyze_experience([e], {"experience": {"min_years": 3}}, {"Python", "SQL", "FastAPI"}, AS_OF, jd_title)
    assert r["relevant_effective_years"] == 5.0
    unrelated = analyze_experience([emp("Sales Manager", (2019, 1), (2023, 12), skills=["Python"])], {"experience": {"min_years": 3}}, {"Python", "SQL"}, AS_OF, jd_title)
    assert unrelated["relevant_effective_years"] == 0.0


def test_simple_duration_inclusive_months():
    r = run([emp("Python Developer", (2020, 1), (2021, 12), skills=["Python", "SQL"])])
    assert r["total_effective_years"] == 2.0 and r["relevant_effective_years"] == 2.0 and r["score"] == 100.0


def test_overlapping_periods_not_double_counted():
    r = run([emp("A", (2018, 1), (2020, 12), skills=["Python", "SQL"]), emp("B", (2019, 1), (2021, 12), skills=["Python", "SQL"])])
    assert r["total_breakdown"]["full_time_years"] == 4.0          # 2018-01..2021-12, not 3 + 3


def test_internship_and_part_time_not_full_time():
    r = run([emp("Intern", (2022, 1), (2022, 12), "internship", ["Python", "SQL"]), emp("Dev", (2023, 1), (2023, 12), "part_time", ["Python", "SQL"])])
    assert r["total_breakdown"]["full_time_years"] == 0
    assert r["total_effective_years"] == pytest.approx(1.0)          # (12*0.5 + 12*0.5)/12
    assert any("Internship" in n for n in r["notes"])


def test_internship_overlapping_fulltime_adds_nothing():
    r = run([emp("Dev", (2020, 1), (2020, 12), skills=["Python", "SQL"]), emp("Intern", (2020, 3), (2020, 8), "internship")])
    assert r["total_effective_years"] == 1.0


def test_present_resolved_to_as_of():
    r = run([emp("Dev", (2025, 11), "present", skills=["Python", "SQL"])])
    assert r["roles"][0]["end"] == "present" and r["total_effective_years"] == pytest.approx(13 / 12, abs=0.01)


def test_year_only_marked_uncertain():
    r = run([emp("Dev", (2019,), (2021,), skills=["Python", "SQL"], year_only=True)])
    assert r["uncertain"] and r["total_effective_years"] == 2.0
    assert any("year-only" in n for n in r["notes"])


def test_gaps_reported_but_not_penalised():
    r = run([emp("A", (2015, 1), (2016, 12), skills=["Python", "SQL"]), emp("B", (2019, 1), (2021, 12), skills=["Python", "SQL"])])
    assert r["gaps_info_only"] and r["gaps_info_only"][0]["months"] >= 24
    assert r["total_effective_years"] == 5.0                         # gap simply isn't counted; no negative adjustment


def test_relevance_requires_skill_overlap():
    r = run([emp("Chef", (2010, 1), (2020, 12), skills=["Cooking"]), emp("Dev", (2021, 1), (2021, 12), skills=["Python", "SQL"])])
    assert r["total_effective_years"] == 12.0 and r["relevant_effective_years"] == 1.0
    assert r["score"] == 50.0


def test_no_employment_is_unverified_not_failure():
    r = run([])
    assert r["status"] == "unverified" and r["score"] == 0.0 and "missing evidence" in " ".join(r["notes"]).lower()


def test_no_requirement_excluded():
    r = run([emp("Dev", (2020, 1), (2021, 12))], mn=None)
    assert r["status"] == "not_required" and r["score"] is None


def test_preferred_years_blend():
    r = run([emp("Dev", (2020, 1), (2022, 12), skills=["Python", "SQL"])], mn=2, pf=6)
    assert r["score"] == pytest.approx(0.7 * 100 + 0.3 * 50, abs=0.01)


def test_methodology_included():
    assert "union" in run([]) ["methodology"].lower() or "overlap" in run([])["methodology"].lower()


# ----------------------------------------------------------------- scoring formula
def comps(t=80, s=60, e=100, ed=100, p=50, **status):
    base = {"technical_skills": t, "semantic_relevance": s, "relevant_experience": e, "education": ed, "project_domain": p}
    return {k: {"score": v, "status": status.get(k, "scored")} for k, v in base.items()}


def test_default_weights_total_100_percent():
    assert sum(DEFAULT_WEIGHTS.values()) == pytest.approx(1.0)
    assert DEFAULT_WEIGHTS == {"technical_skills": 0.40, "semantic_relevance": 0.25, "relevant_experience": 0.20, "education": 0.10, "project_domain": 0.05}


def test_formula_matches_hand_calculation():
    o = re_.compute_overall(comps(), DEFAULT_WEIGHTS)
    assert o["overall"] == pytest.approx(0.4 * 80 + 0.25 * 60 + 0.2 * 100 + 0.1 * 100 + 0.05 * 50)   # 32+15+20+10+2.5 = 79.5
    assert sum(o["contributions"].values()) == pytest.approx(o["overall"], abs=0.01)


@pytest.mark.parametrize("w", [{k: 0.3 for k in COMPONENTS}, {**DEFAULT_WEIGHTS, "technical_skills": -0.1}, {"technical_skills": 1.0}])
def test_invalid_weights_rejected(w):
    with pytest.raises(AppError):
        re_.validate_weights(w)


def test_valid_custom_weights():
    w = {"technical_skills": 0.5, "semantic_relevance": 0.2, "relevant_experience": 0.2, "education": 0.05, "project_domain": 0.05}
    assert re_.validate_weights(w) == w


def test_scores_normalised_0_100_and_clamped():
    assert re_.compute_overall(comps(100, 100, 100, 100, 100), DEFAULT_WEIGHTS)["overall"] == 100.0
    assert re_.compute_overall(comps(0, 0, 0, 0, 0), DEFAULT_WEIGHTS)["overall"] == 0.0
    assert re_.compute_overall(comps(150, 150, 150, 150, 150), DEFAULT_WEIGHTS)["overall"] == 100.0


def test_not_required_component_excluded_and_renormalised():
    o = re_.compute_overall(comps(education=None, **{"education": "not_required"}) if False else {**comps(), "education": {"score": None, "status": "not_required"}}, DEFAULT_WEIGHTS)
    assert "education" not in o["effective_weights"]
    assert sum(o["effective_weights"].values()) == pytest.approx(1.0)
    assert o["overall"] == pytest.approx((0.4 * 80 + 0.25 * 60 + 0.2 * 100 + 0.05 * 50) / 0.9, abs=0.01)


def test_unverified_widens_range_but_not_score():
    c = comps(e=0, relevant_experience="unverified")
    o = re_.compute_overall(c, DEFAULT_WEIGHTS)
    assert o["score_low"] == o["overall"] and o["score_high"] > o["overall"]
    assert o["score_high"] == pytest.approx(o["overall"] + 0.2 * 100, abs=0.01)


def test_ranking_deterministic_with_tiebreaks():
    items = [{"candidate_id": 2, "overall": 70, "components": comps(80)}, {"candidate_id": 1, "overall": 70, "components": comps(80)},
             {"candidate_id": 3, "overall": 90, "components": comps(10)}]
    r = re_.rank(items)
    assert [x["candidate_id"] for x in r] == [3, 1, 2] and [x["rank"] for x in r] == [1, 2, 3]


def test_sensitivity_reports_rank_ranges():
    items = [{"candidate_id": 1, "overall": 0, "components": comps(90, 20)}, {"candidate_id": 2, "overall": 0, "components": comps(60, 95)}]
    s = re_.sensitivity(items, DEFAULT_WEIGHTS)
    assert s[1]["rank_min"] == 1 and s[1]["rank_max"] == 2 and s[1]["scenarios"] == 11


def test_formula_description_mentions_version():
    assert "Technical Skill Match × 0.40" in re_.describe_formula(DEFAULT_WEIGHTS)
