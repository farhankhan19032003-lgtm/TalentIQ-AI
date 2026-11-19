"""Score bands: a clearly strong, a medium and a clearly weak (fictional) resume must land in defensible, ordered bands
under every similarity backend that is available. See docs/ALGORITHM.md, section "Calibration"."""
import pytest

from app.core.config import SCORING
from app.services.explanation_engine import fit_label, headline
from app.services.pipeline import ontology, ontology_texts
from app.services.semantic_matcher import SimilarityEngine
from test_matching_engine import AS_OF, DEFAULT_WEIGHTS, job_from, match_candidate, parse_lines

JD_TEXT = """Job Title: Python Backend Developer
Responsibilities:
- Design and build scalable backend services and REST APIs
- Model data in PostgreSQL and optimise queries
- Write unit tests and maintain CI pipelines
- Containerise services and support deployments
Requirements:
- 3+ years of professional experience in backend development
- Strong Python with FastAPI or Django
- Experience designing REST APIs
- Solid PostgreSQL knowledge
- Docker and Git
- Unit Testing with pytest
- Bachelor's degree in Computer Science or related field
Nice to have:
- Redis and Celery
- Kubernetes
- CI/CD experience
- AWS
"""

STRONG = ["Aarav Mehta", "aarav.mehta@example.com | +91 90000 11111 | Pune, India",
          "Summary", "Backend engineer building scalable Python services, REST APIs and PostgreSQL data models.",
          "Experience",
          "Senior Backend Engineer | Nimbus Apps | Jan 2019 – Present",
          "• Designed and built scalable REST APIs with FastAPI and Django for a payments platform",
          "• Modelled data in PostgreSQL and optimised slow queries",
          "• Wrote unit tests with pytest and maintained CI/CD pipelines on GitHub Actions",
          "• Containerised services with Docker and deployed them to AWS and Kubernetes",
          "• Used Git, Redis and Celery for background jobs",
          "Education", "B.Tech in Computer Science | Sunrise Institute of Technology | 2014 – 2018",
          "Skills", "Python, FastAPI, Django, PostgreSQL, Docker, Git, pytest, Redis, Celery, AWS, Kubernetes, CI/CD"]

MEDIUM = ["Diya Nair", "diya.nair@example.com | Chennai, India",
          "Summary", "Developer building web services in Python.",
          "Experience", "Python Developer | Brightwave Labs | Jun 2020 – Present",
          "• Built REST APIs in Flask for an internal tool",
          "• Stored data in MySQL and wrote unit tests",
          "• Used Git for version control",
          "Education", "B.Sc in Computer Science | Meridian College | 2016 – 2020",
          "Skills", "Python, Flask, MySQL, Git, Unit Testing"]

WEAK = ["Rohit Das", "rohit.das@example.com | Delhi, India",
        "Summary", "Marketing coordinator running social media campaigns and events.",
        "Experience", "Marketing Coordinator | Zenith Media | Jan 2018 – Present",
        "• Planned social media campaigns and event logistics",
        "• Prepared monthly reports in Excel and PowerPoint",
        "Education", "BBA | Crestview Business School | 2014 – 2017",
        "Skills", "Excel, PowerPoint, Communication"]


def engines():
    out = [SimilarityEngine("tfidf", ontology_texts())]
    mini = SimilarityEngine("minilm", ontology_texts())
    if mini.method == "minilm":
        out.append(mini)
    return out


@pytest.fixture(scope="module")
def scored():
    job = job_from(JD_TEXT)
    res = {}
    for eng in engines():
        eng.prepare([job["description"]] + [ontology.semantic_query(r["name"]) for r in job["requirements"]])
        res[eng.method] = {}
        for name, lines in (("strong", STRONG), ("medium", MEDIUM), ("weak", WEAK)):
            parsed, text = parse_lines(lines)
            res[eng.method][name] = match_candidate(parsed, text.split("\f"), job, eng, ontology, DEFAULT_WEIGHTS, AS_OF)
    return res


def test_ordering_strong_medium_weak(scored):
    for method, r in scored.items():
        assert r["strong"]["overall"] > r["medium"]["overall"] > r["weak"]["overall"], method


def test_score_bands(scored):
    for method, r in scored.items():
        assert r["strong"]["overall"] >= 80, (method, r["strong"]["overall"])       # most must-haves evidenced -> 80+
        assert 50 <= r["medium"]["overall"] < 80, (method, r["medium"]["overall"])  # partial-to-good fit (4 of 7 must-haves)
        assert r["weak"]["overall"] < 40, (method, r["weak"]["overall"])            # unrelated background


def test_strong_candidate_covers_most_musts_and_weak_none(scored):
    for r in scored.values():
        assert r["strong"]["must_have_coverage"] >= 75
        assert r["weak"]["must_have_coverage"] == 0


def test_unit_testing_and_pytest_are_one_requirement():
    job = job_from(JD_TEXT)
    names = [r["name"] for r in job["requirements"]]
    assert "Unit Testing (pytest)" in names and "pytest" not in names and "Unit Testing" not in names
    parsed, text = parse_lines(MEDIUM)         # has Unit Testing but not pytest
    eng = SimilarityEngine("tfidf", ontology_texts())
    eng.prepare([job["description"]])
    m = match_candidate(parsed, text.split("\f"), job, eng, ontology, DEFAULT_WEIGHTS, AS_OF)
    r = next(x for x in m["requirements"] if x["name"] == "Unit Testing (pytest)")
    assert r["match_type"] == "exact" and r["credit"] > 0 and r["satisfied_by"] == "Unit Testing"


def test_peer_framework_is_related_not_exact(scored):
    r = next(x for x in scored["tfidf"]["medium"]["requirements"] if x["name"] == "FastAPI or Django")
    assert r["match_type"] == "partial" and r["credit"] == SCORING["partial_credit"]       # Flask counts as related only


def test_unverified_project_section_is_left_out_not_zeroed(scored):
    m = scored["tfidf"]["strong"]
    assert m["components"]["project_domain"]["status"] == "unverified"
    assert m["components"]["project_domain"]["weight_effective"] == 0
    assert m["score_low"] <= m["overall"] <= m["score_high"] and m["score_high"] - m["score_low"] == pytest.approx(5.0, abs=0.01)


def test_headline_sentence_is_plain_language(scored):
    m = scored["tfidf"]["strong"]
    m["explanation"] = None
    h = headline(m)
    assert h.startswith(fit_label(m["overall"])) and "must-have" in h and "Relevant experience" in h
    assert fit_label(85) == "Strong match" and fit_label(72) == "Good match" and fit_label(55) == "Partial match" and fit_label(10) == "Poor match"


def test_merged_requirement_survives_saving_through_the_api(client):
    """Regression: the API schema used to drop `any_of`, turning 'Unit Testing (pytest)' into a literal text search that matched nothing."""
    from helpers import make_docx
    analysis = client.post("/api/jobs/analyze", json={"description": JD_TEXT}).json()
    job = client.post("/api/jobs", json={**analysis, "description": JD_TEXT, "title": "Python Backend Developer (calibration test)"}).json()
    req = next(r for r in job["requirements"] if r["name"] == "Unit Testing (pytest)")
    assert req["any_of"] == ["Unit Testing", "pytest"] and not req["custom"]
    up = client.post("/api/resumes/upload", files=[("files", ("diya_calibration.docx", make_docx(MEDIUM), "application/octet-stream"))]).json()
    cid = up["results"][0]["candidate_id"]
    assert cid
    client.post(f"/api/matching/run/{job['id']}")
    detail = client.get(f"/api/matching/candidate/{cid}", params={"job_id": job["id"]}).json()["result"]
    ut = next(r for r in detail["requirements"] if r["name"] == "Unit Testing (pytest)")
    assert ut["match_type"] == "exact" and ut["satisfied_by"] == "Unit Testing"
    assert detail["explanation"]["headline"]


def test_minilm_semantic_scale_does_not_saturate_for_strong_matches():
    """Measured on the synthetic benchmark: strong resumes have document cosines up to ~0.90 and sentence-level cosines up to ~0.46.
    The upper anchors sit above that, so a very strong match still scores below 100 and stays distinguishable from a strong one."""
    eng = SimilarityEngine.__new__(SimilarityEngine)   # to_score only needs the method name
    eng.method = "minilm"
    strong, very_strong = eng.to_score(0.77, "doc"), eng.to_score(0.87, "doc")
    assert strong < very_strong < 100
    assert eng.to_score(0.46, "resp") < eng.to_score(0.50, "resp") < 100
    assert eng.to_score(0.25, "doc") == 0 and eng.to_score(0.15, "resp") == 0
