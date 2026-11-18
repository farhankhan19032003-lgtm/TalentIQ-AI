import pytest

from app.services.jd_analyzer import analyze_jd
from app.services.pipeline import ontology, resume_extractor, skill_extractor
from app.services.skill_extractor import Line


def ex(text, section="experience"):
    return skill_extractor.extract([Line(1, section, text)])


def test_exact_alias_and_canonical_normalisation():
    r = ex("Used sklearn and PostgreSQL (postgres), ran k8s on Amazon Web Services; wrote ci/cd pipelines")
    assert {"scikit-learn", "PostgreSQL", "Kubernetes", "AWS", "CI/CD"} <= set(r)
    assert r["scikit-learn"]["mentions"][0]["method"] == "synonym"
    assert r["PostgreSQL"]["mentions"][0]["method"] in ("exact", "synonym")


def test_python_does_not_imply_django_or_vice_versa_evidence():
    r = ex("Developed services in Python")
    assert "Django" not in r and "FastAPI" not in r
    r2 = ex("Built Django apps")
    assert "Django" in r2 and "Python" not in r2          # extraction reports only what is written


def test_word_boundaries():
    assert "Java" not in ex("Strong JavaScript skills")
    assert "Java" in ex("Strong Java skills")
    assert "C" not in ex("C++ developer", "skills") or "C++" in ex("C++ developer", "skills")
    assert "C++" in ex("C++ developer")


@pytest.mark.parametrize("text,absent", [("Go-getter attitude", "Go"), ("Supports R&D teams", "R"), ("Spring 2021 internship", "Spring"),
                                         ("We excel at teamwork", "Excel"), ("A swift response", "Swift")])
def test_ambiguous_tokens_not_false_positives(text, absent):
    assert absent not in ex(text)


def test_ambiguous_skills_found_in_lists():
    r = ex("Languages: Python, R, Go, SQL", "skills")
    assert {"R", "Go", "Python", "SQL"} <= set(r)


def test_listed_only_vs_context():
    r = skill_extractor.extract([Line(1, "skills", "Docker, Python"), Line(1, "experience", "Deployed with Docker")])
    assert r["Docker"]["listed_only"] is False and r["Python"]["listed_only"] is True


def test_proficiency_only_when_explicit():
    r = ex("5 years of Python; scikit-learn (Advanced); used Docker")
    assert r["Python"]["proficiency"]["years"] == 5.0
    assert r["scikit-learn"]["proficiency"]["level"] == "advanced"
    assert r["Docker"]["proficiency"] is None


def test_header_contact_lines_are_not_skill_evidence():
    assert skill_extractor.extract([Line(1, "header", "github.com/jane | jane@example.com")]) == {}


def test_every_mention_has_evidence_snippet_and_page():
    r = ex("Built APIs with FastAPI and Docker")
    for s in r.values():
        for m in s["mentions"]:
            assert m["snippet"] and m["page"] == 1


def test_ontology_related_is_directional_and_valid():
    assert "Kubernetes" in ontology.related("Docker") and "Docker" not in ontology.related("Kubernetes")
    for s in ontology.skills.values():
        for r in s["related"]:
            assert r in ontology.skills


JD = """Job Title: AI/ML Engineer
Responsibilities:
- Deploy models with Docker
Requirements:
- 3+ years of experience in machine learning
- Python or Bash required
- Bachelor's degree in Computer Science
Nice to have:
- Kubernetes
- Master's degree preferred
"""


def test_jd_requirements_importance_and_core():
    a = analyze_jd(JD, skill_extractor, ontology)
    imp = {r["name"]: r for r in a["requirements"]}
    assert imp["Machine Learning"]["importance"] == "must" and imp["Machine Learning"].get("core")
    assert imp["Kubernetes"]["importance"] == "preferred"
    assert imp["Docker"]["importance"] == "preferred"            # only named under Responsibilities
    assert "Python or Bash" in imp and imp["Python or Bash"]["any_of"] == ["Python", "Bash"]
    assert a["experience"]["min_years"] == 3
    assert a["education"]["required_level"] == 3 and a["education"]["preferred_level"] == 4
    assert a["title"] == "AI/ML Engineer"


def test_jd_sample_files(jd_text):
    a = analyze_jd(jd_text["ai_ml_engineer"], skill_extractor, ontology)
    names = {r["name"] for r in a["requirements"]}
    assert {"Machine Learning", "Python", "scikit-learn", "NLP", "SQL"} <= names
    assert a["experience"]["min_years"] == 2 and a["responsibilities"]
    assert "Fintech" in a["domain_knowledge"]


def test_resume_extraction_fields_have_provenance():
    from app.services.document_parser import parse_pdf
    from helpers import RES
    p = resume_extractor.extract(parse_pdf((RES / "anika_menon.pdf").read_bytes()))
    f = p["fields"]["email"]
    assert f["value"].endswith("@example.com") and f["page"] == 1 and f["evidence"] and f["method"] and f["confidence"] > 0.9
    assert p["fields"]["location"]["value"] == "Bengaluru, India"
    assert p["education"][0]["level"] >= 3 and p["education"][0]["page"] == 1


def test_missing_fields_are_null_not_invented():
    from app.services.document_parser import parse_pdf
    from helpers import RES
    p = resume_extractor.extract(parse_pdf((RES / "neha_banerjee.pdf").read_bytes()))
    assert p["fields"]["phone"]["value"] is None and p["fields"]["linkedin"]["value"] is None
    assert p["fields"]["phone"]["status"] == "unknown"
    assert p["employment"] == [] and p["education"] == []


def test_peer_skills_give_related_credit_but_are_not_equivalent():
    """Same-tier alternatives (Flask for Django, MySQL for PostgreSQL) are related evidence (partial credit, never a full match)."""
    assert {"Flask", "Django"} <= set(ontology.related("FastAPI"))
    assert {"Flask", "FastAPI"} <= set(ontology.related("Django"))
    assert "MySQL" in ontology.related("PostgreSQL") and "PostgreSQL" in ontology.related("MySQL")
    r = ex("Built services in Flask on MySQL")
    assert "Django" not in r and "PostgreSQL" not in r      # extraction still reports only what is written
