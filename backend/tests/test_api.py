import io
import json
from pathlib import Path

import openpyxl
import pytest

from app.core.config import settings
from helpers import make_pdf, simple_resume

GT = json.loads((Path(__file__).resolve().parents[2] / "sample_data/ground_truth/ground_truth.json").read_text())


def jid(loaded, key="ai_ml_engineer"):
    return loaded["jobs"][key]["id"]


@pytest.fixture(scope="module")
def ran(client, loaded):
    ids = {}
    for k, j in loaded["jobs"].items():
        r = client.post(f"/api/matching/run/{j['id']}", json={})
        assert r.status_code == 201, r.text
        ids[k] = r.json()
    return ids


# ---------------------------------------------------------------- upload
def test_health_and_docs(client):
    h = client.get("/api/health").json()
    assert h["status"] == "ok" and h["database"] == "ok" and h["algorithm_version"]
    assert client.get("/api/openapi.json").status_code == 200 and client.get("/api/docs").status_code == 200


def test_batch_of_10plus_resumes_pdf_and_docx(loaded):
    s = loaded["upload"]["summary"]
    res = loaded["upload"]["results"]
    assert loaded["upload"]["total"] == 41 and s["parsed"] >= 10
    exts = {r["filename"].rsplit(".", 1)[-1] for r in res if r["status"] == "parsed"}
    assert {"pdf", "docx"} <= exts


def test_one_bad_file_never_fails_batch(loaded):
    by = {r["filename"]: r for r in loaded["upload"]["results"]}
    assert by["corrupted_resume.pdf"]["status"] == "failed" and by["corrupted_resume.pdf"]["error_code"] == "corrupt"
    assert by["password_protected_resume.pdf"]["error_code"] == "password_protected"
    assert by["corrupted_resume.docx"]["status"] == "rejected"
    assert by["fake_extension_resume.pdf"]["error_code"] == "signature_mismatch"
    assert by["resume_notes.txt"]["error_code"] == "unsupported_type"
    assert by["anika_menon.pdf"]["status"] == "parsed"
    for r in loaded["upload"]["results"]:
        assert "Traceback" not in json.dumps(r) and "/home/" not in json.dumps(r)   # safe error messages


def test_duplicate_detection(loaded):
    r = next(x for x in loaded["upload"]["results"] if x["filename"] == "anika_menon_resume_copy.pdf")
    assert r["status"] == "duplicate" and r["resume_id"]


def test_duplicate_person_flagged_by_email(client):
    a = make_pdf(simple_resume("Dup Person", "dup.person@example.com"))
    b = make_pdf(simple_resume("Dup Person", "dup.person@example.com", skills="Python, SQL, Docker, Git"))
    client.post("/api/resumes/upload", files=[("files", ("a.pdf", a, "x"))])
    r = client.post("/api/resumes/upload", files=[("files", ("b.pdf", b, "x"))]).json()["results"][0]
    assert r["status"] == "parsed" and r["possible_duplicate_of"]


def test_resume_listing_stats_and_batch(client, loaded):
    st = client.get("/api/resumes/stats").json()
    assert st["failed"] >= 2 and st["success_rate"] and "corrupt" in st["failures_by_reason"]
    lst = client.get("/api/resumes?page=1&page_size=5").json()
    assert len(lst["items"]) == 5 and lst["total"] >= 35
    assert client.get("/api/resumes?status=failed").json()["total"] >= 2
    b = client.get(f"/api/resumes/batches/{loaded['upload']['batch_id']}").json()
    # the image-only scanned PDF only parses when Tesseract OCR is available
    from app.services.document_parser import _ocr_available
    assert b["total"] >= 37 and b["parsed"] >= (35 if _ocr_available() else 34)
    assert client.get("/api/resumes/999999").status_code == 404


def test_retry_failed_resume(client, loaded):
    fid = next(r["resume_id"] for r in loaded["upload"]["results"] if r["filename"] == "corrupted_resume.pdf")
    r = client.post(f"/api/resumes/{fid}/retry")
    assert r.status_code == 200 and r.json()["status"] == "failed"          # still corrupt, but retried safely
    ok = next(r["resume_id"] for r in loaded["upload"]["results"] if r["filename"] == "anika_menon.pdf")
    assert client.post(f"/api/resumes/{ok}/retry").status_code == 409


def test_oversized_and_traversal_filename_handled(client, monkeypatch):
    monkeypatch.setattr(settings, "max_upload_mb", 0.01)
    r = client.post("/api/resumes/upload", files=[("files", ("../../evil.pdf", b"%PDF-" + b"0" * 50000, "x"))]).json()["results"][0]
    assert r["status"] == "rejected" and r["error_code"] == "file_too_large" and ".." not in r["filename"]


def test_batch_limit(client, monkeypatch):
    monkeypatch.setattr(settings, "max_batch_files", 2)
    r = client.post("/api/resumes/upload", files=[("files", (f"{i}.pdf", b"x", "x")) for i in range(3)])
    assert r.status_code == 413 and r.json()["error"]["code"] == "batch_too_large"


# ---------------------------------------------------------------- jobs
def test_job_crud_and_editable_requirements(client):
    desc = "Job Title: Test Dev\nRequirements:\n- Python and Docker\n- 2+ years of experience\nNice to have:\n- Redis\n"
    r = client.post("/api/jobs", json={"title": "Test Dev", "description": desc, "required_skills": ["PostgreSQL"], "optional_skills": ["Terraform"]})
    assert r.status_code == 201
    j = r.json()
    names = {x["name"]: x["importance"] for x in j["requirements"]}
    assert names["Python"] == "must" and names["PostgreSQL"] == "must" and names["Terraform"] == "preferred" and names["Redis"] == "preferred"
    assert j["min_experience_years"] == 2
    edited = [dict(x) for x in j["requirements"]]
    for x in edited:
        if x["name"] == "Redis":
            x["importance"] = "must"
        if x["name"] == "Docker":
            x["importance"] = "ignored"
    u = client.put(f"/api/jobs/{j['id']}", json={"title": "Test Dev II", "description": desc, "requirements": edited})
    assert u.status_code == 200 and u.json()["title"] == "Test Dev II"
    got = {x["name"]: x["importance"] for x in client.get(f"/api/jobs/{j['id']}").json()["requirements"]}
    assert got["Redis"] == "must" and got["Docker"] == "ignored"
    assert client.get("/api/jobs").json()["total"] >= 1
    assert client.delete(f"/api/jobs/{j['id']}").status_code == 204
    assert client.get(f"/api/jobs/{j['id']}").status_code == 404


def test_job_validation_errors(client):
    r = client.post("/api/jobs", json={"title": "x", "description": "short"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"
    r = client.post("/api/jobs", json={"title": "Valid Title", "description": "d" * 30, "min_experience_years": -3})
    assert r.status_code == 422


def test_job_analyze_preview_and_text_upload(client, jd_text):
    a = client.post("/api/jobs/analyze", json={"description": jd_text["data_analyst"]}).json()
    assert "Excel" in a["must_have"] and a["experience"]["min_years"] == 1
    d = client.post("/api/jobs/extract-text", files={"file": ("jd.docx", (Path(__file__).resolve().parents[2] / "sample_data/job_descriptions/python_backend_developer.docx").read_bytes(), "x")}).json()
    assert "Python" in d["text"] and any(r["name"] == "PostgreSQL" for r in d["analysis"]["requirements"])
    t = client.post("/api/jobs/extract-text", files={"file": ("jd.txt", b"Job Title: X\nRequirements:\n- Python\n", "x")}).json()
    assert t["analysis"]["must_have"] == ["Python"]
    assert client.post("/api/jobs/extract-text", files={"file": ("jd.pdf", b"%PDF-", "x")}).status_code == 400


def test_templates_seed(client):
    client.post("/api/demo/seed-jobs")
    assert len(client.get("/api/jobs?templates=true").json()["items"]) >= 6
    assert client.post("/api/demo/seed-jobs").json()["created"] == []         # idempotent


# ---------------------------------------------------------------- matching & ranking
def test_ranking_sorted_descending_and_ranks_consistent(client, loaded, ran):
    res = client.get(f"/api/matching/results/{jid(loaded)}?page_size=100").json()
    scores = [i["overall"] for i in res["items"]]
    assert scores == sorted(scores, reverse=True) and [i["rank"] for i in res["items"]] == list(range(1, len(scores) + 1))
    assert res["total"] >= 35 and all(0 <= s <= 100 for s in scores)
    assert res["run"]["algorithm_version"] and res["run"]["similarity_method"] in ("tfidf", "minilm")


def test_domain_expert_ranks_first(client, loaded, ran):
    top = lambda key: client.get(f"/api/matching/results/{jid(loaded, key)}?page_size=3").json()["items"][0]["name"]
    assert top("java_backend_developer") in ("Rahul Menon", "Farah Ali")
    assert top("cloud_devops_engineer") == "Sameer Gupta"
    assert top("data_analyst") == "Dev Malhotra"


def test_unrelated_candidates_rank_low(client, loaded, ran):
    items = client.get(f"/api/matching/results/{jid(loaded)}?page_size=100").json()["items"]
    pos = {i["name"]: i["rank"] for i in items}
    for n in ("Meenal Shah", "Rajesh Pawar", "Yash Trivedi"):
        assert pos[n] > len(items) - 8


def test_pagination_filters_sort_search(client, loaded, ran):
    base = f"/api/matching/results/{jid(loaded)}"
    p1 = client.get(base + "?page=1&page_size=10").json()
    p2 = client.get(base + "?page=2&page_size=10").json()
    assert len(p1["items"]) == 10 and p1["items"][0]["rank"] == 1 and p2["items"][0]["rank"] == 11
    hi = client.get(base + "?min_score=60&page_size=100").json()
    assert hi["total"] >= 1 and all(i["overall"] >= 60 for i in hi["items"])
    assert all("Python" in i["candidate_skills"] for i in client.get(base + "?skills=Python&page_size=100").json()["items"])
    assert all(i["total_years"] >= 8 for i in client.get(base + "?min_exp=8&page_size=100").json()["items"])
    q = client.get(base + "?q=anika").json()
    assert q["total"] == 1 and q["items"][0]["name"] == "Anika Menon"
    asc = client.get(base + "?sort=overall&order=asc&page_size=100").json()["items"]
    assert asc[0]["overall"] <= asc[-1]["overall"]
    assert client.get(base + "?sort=bogus").status_code == 422
    assert client.get(base + "?page_size=1000").status_code == 422


def test_matched_and_missing_skills_consistent(client, loaded, ran):
    it = client.get(f"/api/matching/results/{jid(loaded)}?q=anika").json()["items"][0]
    assert {"Python", "Machine Learning", "NLP", "scikit-learn"} <= set(it["matched_skills"])
    assert not set(it["matched_skills"]) & set(it["missing_skills"])
    kab = client.get(f"/api/matching/results/{jid(loaded)}?q=kabir").json()["items"][0]
    assert "NLP" in kab["missing_skills"]


def test_candidate_detail_has_breakdown_explanation_evidence(client, loaded, ran):
    cid = client.get(f"/api/matching/results/{jid(loaded)}?q=anika").json()["items"][0]["candidate_id"]
    d = client.get(f"/api/matching/candidate/{cid}?job_id={jid(loaded)}").json()
    r = d["result"]
    assert set(r["components"]) == {"technical_skills", "semantic_relevance", "relevant_experience", "education", "project_domain"}
    assert r["explanation"]["why_matched"] and r["explanation"]["disclaimer"] and r["explanation"]["component_effects"]
    assert r["experience"]["methodology"] and r["experience"]["roles"] and "similarity_method" in r["run"]
    assert d["candidate"]["fields"]["email"]["page"] == 1 and d["candidate"]["fields"]["email"]["evidence"]
    ev = [e for e in r["evidence"] if e["text"]]
    assert ev and all(e["verification"] in ("verified", "inferred") for e in ev)


def test_all_evidence_is_verbatim_resume_text(client, loaded, ran):
    """Never generate fictional resume quotations: every stored evidence snippet must exist in the resume text."""
    from app.core.database import SessionLocal
    from app.models import db as M
    s = SessionLocal()
    n = 0
    norm = lambda t: " ".join(t.replace("• ", "").split())
    for e in s.query(M.EvidenceItem).filter(M.EvidenceItem.evidence_text.isnot(None)).limit(3000):
        res = s.get(M.MatchResult, e.result_id)
        text = norm(s.get(M.Candidate, res.candidate_id).resume.raw_text)
        assert norm(e.evidence_text) in text, (e.requirement, e.evidence_text)
        n += 1
    assert n > 200


def test_database_persistence(client, loaded, ran):
    from app.core.database import SessionLocal
    from app.models import db as M
    s = SessionLocal()
    run = s.query(M.MatchRun).filter_by(job_id=jid(loaded)).order_by(M.MatchRun.id.desc()).first()
    results = s.query(M.MatchResult).filter_by(run_id=run.id).all()
    assert len(results) == run.n_candidates >= 35
    assert len({r.rank for r in results}) == len(results)
    for r in results[:5]:
        assert {c.name for c in r.components} == {"technical_skills", "semantic_relevance", "relevant_experience", "education", "project_domain"}
        assert r.evidence and r.explanation["summary"]
    assert s.query(M.Candidate).count() >= 35 and s.query(M.ExtractedSkill).count() > 200 and s.query(M.Employment).count() > 40
    assert s.query(M.Education).count() > 20 and s.query(M.Project).count() >= 5
    assert run.weights and run.algorithm_version and run.job_snapshot["requirements"]


def test_custom_weights_change_scores_and_are_validated(client, loaded):
    j = jid(loaded)
    base = client.post(f"/api/matching/run/{j}", json={}).json()
    w = {"technical_skills": 0.7, "semantic_relevance": 0.1, "relevant_experience": 0.1, "education": 0.05, "project_domain": 0.05}
    r = client.post(f"/api/matching/run/{j}", json={"weights": w})
    assert r.status_code == 201 and r.json()["weights"] == w
    bad = client.post(f"/api/matching/run/{j}", json={"weights": {**w, "technical_skills": 0.9}})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "invalid_weights"
    client.post(f"/api/matching/run/{j}", json={})                          # restore latest run to defaults
    assert base["weights"]["technical_skills"] == 0.4


def test_two_runs_are_reproducible(client, loaded):
    j = jid(loaded, "full_stack_developer")
    client.post(f"/api/matching/run/{j}", json={})
    a = [(i["candidate_id"], i["overall"]) for i in client.get(f"/api/matching/results/{j}?page_size=100").json()["items"]]
    client.post(f"/api/matching/run/{j}", json={})
    b = [(i["candidate_id"], i["overall"]) for i in client.get(f"/api/matching/results/{j}?page_size=100").json()["items"]]
    assert a == b


def test_compare_candidates(client, loaded, ran):
    items = client.get(f"/api/matching/results/{jid(loaded)}?page_size=5").json()["items"]
    ids = ",".join(str(i["candidate_id"]) for i in items[:3])
    c = client.get(f"/api/matching/compare?job_id={jid(loaded)}&ids={ids}").json()
    assert len(c["candidates"]) == 3 and c["requirements"]
    assert client.get(f"/api/matching/compare?job_id={jid(loaded)}&ids=1").status_code == 422
    assert client.get(f"/api/matching/compare?job_id={jid(loaded)}&ids=1,2,3,4,5,6").status_code == 422


def test_whatif_does_not_modify_original(client, loaded, ran):
    j = jid(loaded)
    before = client.get(f"/api/matching/results/{j}?page_size=100").json()["items"]
    w = {"technical_skills": 0.1, "semantic_relevance": 0.6, "relevant_experience": 0.1, "education": 0.1, "project_domain": 0.1}
    sim = client.post(f"/api/matching/whatif/{j}", json={"weights": w, "add_requirements": [{"name": "Kubernetes", "importance": "must"}], "min_years": 5}).json()
    assert sim["persisted"] is False and len(sim["rows"]) == len(before)
    assert any(r["rank_change"] != 0 for r in sim["rows"]) and any(r["score_change"] != 0 for r in sim["rows"])
    after = client.get(f"/api/matching/results/{j}?page_size=100").json()["items"]
    assert [(i["candidate_id"], i["overall"], i["rank"]) for i in before] == [(i["candidate_id"], i["overall"], i["rank"]) for i in after]
    assert client.post(f"/api/matching/whatif/{j}", json={"weights": {"technical_skills": 1}}).status_code == 422


def test_whatif_requirement_importance_change(client, loaded, ran):
    j = jid(loaded)
    job = client.get(f"/api/jobs/{j}").json()
    nlp = next(r for r in job["requirements"] if r["name"] == "NLP")
    sim = client.post(f"/api/matching/whatif/{j}", json={"requirement_changes": [{"id": nlp["id"], "importance": "ignored"}]}).json()
    assert any(r["score_change"] != 0 for r in sim["rows"])


def test_notes_status_override_are_recorded_and_machine_score_unchanged(client, loaded, ran):
    j = jid(loaded)
    it = client.get(f"/api/matching/results/{j}?q=rohan").json()["items"][0]
    cid, rid, score = it["candidate_id"], it["result_id"], it["overall"]
    assert client.post(f"/api/candidates/{cid}/notes", json={"text": "Strong ML portfolio, schedule screen"}).status_code == 201
    assert client.patch(f"/api/candidates/{cid}/status", json={"review_status": "shortlisted"}).json()["review_status"] == "shortlisted"
    assert client.patch(f"/api/candidates/{cid}/status", json={"review_status": "hired"}).status_code == 422
    o = client.post(f"/api/matching/results/{rid}/override", json={"new_score": 90, "reason": "Verified portfolio during call"})
    assert o.status_code == 201
    assert client.post(f"/api/matching/results/{rid}/override", json={"new_score": 90, "reason": "x"}).status_code == 422   # reason required
    d = client.get(f"/api/matching/candidate/{cid}?job_id={j}").json()
    assert d["candidate"]["notes"][0]["text"].startswith("Strong ML") and d["candidate"]["review_status"] == "shortlisted"
    assert d["result"]["overrides"][0]["new_score"] == 90 and d["result"]["overall"] == score
    assert client.get(f"/api/matching/results/{j}?review_status=shortlisted").json()["total"] >= 1
    acts = {a["action"] for a in client.get("/api/audit?page_size=200").json()["items"]}
    assert {"candidate.status_changed", "score.manual_override", "candidate.note_added"} <= acts


def test_system_never_auto_rejects(client, loaded, ran):
    statuses = {i["review_status"] for i in client.get(f"/api/matching/results/{jid(loaded)}?page_size=100").json()["items"]}
    assert "not_progressing" not in statuses and "rejected" not in statuses


# ---------------------------------------------------------------- analytics & reports
def test_analytics(client, loaded, ran):
    a = client.get(f"/api/analytics/{jid(loaded)}").json()
    assert a["has_run"] and a["parsing"]["failed"] >= 2 and 0 < a["parsing"]["success_rate"] < 100
    assert sum(b["count"] for b in a["score_distribution"]) == a["summary"]["total_candidates"]
    assert a["skill_frequency"] and a["most_missing_skills"] and a["requirement_coverage"] and a["experience_distribution"]
    assert sum(b["count"] for b in a["experience_distribution"]) == a["summary"]["total_candidates"]


def test_talent_pool(client, loaded, ran):
    t = client.get(f"/api/analytics/talent-pool/overview?job_id={jid(loaded)}").json()
    assert t["total_candidates"] >= 35 and t["common_skills"] and t["skill_matrix"]["rows"] and t["job_coverage"]
    assert t["availability"]["available"] is False


def test_csv_export(client, loaded, ran):
    r = client.get(f"/api/reports/{jid(loaded)}/csv")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv") and "attachment" in r.headers["content-disposition"]
    rows = list(__import__("csv").reader(io.StringIO(r.content.decode("utf-8-sig"))))
    assert rows[0][:5] == ["Rank", "Candidate", "Email", "Latest role", "Match score"] and len(rows) - 1 >= 35
    assert [int(x[0]) for x in rows[1:]] == list(range(1, len(rows)))
    blind = client.get(f"/api/reports/{jid(loaded)}/csv?blind=true").content.decode("utf-8-sig")
    assert "Anika" not in blind and "@example.com" not in blind and "Candidate C-" in blind


def test_csv_formula_injection_neutralised():
    from app.services.exports import safe_cell
    assert safe_cell("=HYPERLINK('http://evil')") == "'=HYPERLINK('http://evil')" and safe_cell("+1+1").startswith("'") and safe_cell("normal") == "normal"


def test_excel_export(client, loaded, ran):
    r = client.get(f"/api/reports/{jid(loaded)}/excel")
    assert r.status_code == 200 and "spreadsheetml" in r.headers["content-type"]
    wb = openpyxl.load_workbook(io.BytesIO(r.content))
    assert wb.sheetnames == ["Ranking", "Interviews", "Skill matrix", "Run info"]          # interview notes are included by default
    ws = wb["Ranking"]
    assert ws.max_row - 1 >= 35 and ws["A1"].value == "Rank" and ws["A2"].value == 1
    assert any("disclaimer" == c.value for c in wb["Run info"]["A"])
    # `interviews=false` gives the original three-sheet layout without the two interview columns
    plain = openpyxl.load_workbook(io.BytesIO(client.get(f"/api/reports/{jid(loaded)}/excel?interviews=false").content))
    assert plain.sheetnames == ["Ranking", "Skill matrix", "Run info"]
    assert [c.value for c in plain["Ranking"][1]][-1] == "No-evidence skills"


def test_pdf_exports(client, loaded, ran):
    j = jid(loaded)
    r = client.get(f"/api/reports/{j}/pdf")
    assert r.status_code == 200 and r.content.startswith(b"%PDF") and r.headers["content-type"] == "application/pdf"
    cid = client.get(f"/api/matching/results/{j}?page_size=1").json()["items"][0]["candidate_id"]
    c = client.get(f"/api/reports/{j}/candidate/{cid}/pdf")
    assert c.status_code == 200 and c.content.startswith(b"%PDF") and len(c.content) > 2000
    import pymupdf
    txt = " ".join(pg.get_text() for pg in pymupdf.open(stream=c.content, filetype="pdf"))
    assert "Score breakdown" in txt and "Evidence snippets" in txt and "not" in txt.lower() and "probab" in txt.lower()


def test_report_without_run_is_404(client):
    j = client.post("/api/jobs", json={"title": "No Run Job", "description": "Requirements:\n- Python\n- 1+ years of experience\n"}).json()
    assert client.get(f"/api/reports/{j['id']}/csv").status_code == 404
    assert client.get(f"/api/matching/results/{j['id']}").status_code == 404


# ---------------------------------------------------------------- security / privacy / errors
def test_audit_log_has_no_personal_data(client, loaded, ran):
    log = json.dumps(client.get("/api/audit?page_size=200").json())
    for needle in ("@example.com", "Anika", "Menon", "Karan", "linkedin", "+91"):
        assert needle not in log


def test_blind_mode_masks_identity_everywhere(client, loaded, ran):
    j = jid(loaded)
    rows = client.get(f"/api/matching/results/{j}?blind=true&page_size=100").json()["items"]
    blob = json.dumps(rows)
    assert all(r["name"].startswith("Candidate C-") and r["email"] is None for r in rows) and "@example.com" not in blob and "Anika" not in blob
    d = client.get(f"/api/matching/candidate/{rows[0]['candidate_id']}?job_id={j}&blind=true").json()
    f = d["candidate"]["fields"]
    assert f["name"]["value"].startswith("[hidden") and f["email"]["value"].startswith("[hidden") and "resume_" in d["candidate"]["file"]["filename"]
    assert "@example.com" not in json.dumps(d["candidate"]["fields"])


def test_blind_mode_does_not_change_ranking(client, loaded, ran):
    j = jid(loaded)
    a = [i["candidate_id"] for i in client.get(f"/api/matching/results/{j}?page_size=100").json()["items"]]
    b = [i["candidate_id"] for i in client.get(f"/api/matching/results/{j}?page_size=100&blind=true").json()["items"]]
    assert a == b


def test_unknown_routes_and_methods_safe(client):
    assert client.get("/api/nope").status_code == 404 and client.get("/api/nope").json()["error"]["code"] == "http_error"
    assert client.delete("/api/jobs/abc").status_code == 422


def test_internal_errors_do_not_leak_details(loaded, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.services import pipeline
    monkeypatch.setattr(pipeline, "run_matching", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("secret internal path /srv/db")))
    with TestClient(app, raise_server_exceptions=False) as c:
        r = c.post(f"/api/matching/run/{jid(loaded)}", json={})
    assert r.status_code == 500 and "secret" not in r.text and r.json()["error"]["code"] == "internal_error"


def test_api_key_access_control(client, monkeypatch):
    monkeypatch.setattr(settings, "api_key", "s3cret")
    assert client.get("/api/jobs").status_code == 401
    assert client.get("/api/jobs", headers={"X-API-Key": "wrong"}).status_code == 401
    assert client.get("/api/jobs", headers={"X-API-Key": "s3cret"}).status_code == 200
    assert client.get("/api/health").status_code == 200
    assert client.post("/api/auth/login", json={"api_key": "bad"}).status_code == 401
    assert client.post("/api/auth/login", json={"api_key": "s3cret"}).status_code == 200


def test_candidate_deletion_removes_data_and_file(client):
    from app.core.database import SessionLocal
    from app.models import db as M
    from app.services.security import read_stored
    r = client.post("/api/resumes/upload", files=[("files", ("del.pdf", make_pdf(simple_resume("Delete Me", skills="Python, Docker, SQL, Git")), "x"))]).json()["results"][0]
    s = SessionLocal()
    stored = s.get(M.Resume, r["resume_id"]).stored_filename
    assert read_stored(stored)
    assert client.delete(f"/api/candidates/{r['candidate_id']}").status_code == 204
    s2 = SessionLocal()
    assert s2.get(M.Candidate, r["candidate_id"]) is None and s2.get(M.Resume, r["resume_id"]) is None
    assert s2.query(M.ExtractedSkill).filter_by(candidate_id=r["candidate_id"]).count() == 0
    assert read_stored(stored) is None
    assert client.delete(f"/api/candidates/{r['candidate_id']}").status_code == 404


def test_retention_purge(client):
    from datetime import datetime, timedelta
    from app.core.database import SessionLocal
    from app.models import db as M
    r = client.post("/api/resumes/upload", files=[("files", ("old.pdf", make_pdf(simple_resume("Old Person", skills="Python, Docker, SQL, Git")), "x"))]).json()["results"][0]
    s = SessionLocal()
    s.get(M.Resume, r["resume_id"]).created_at = datetime.utcnow() - timedelta(days=400)
    s.commit()
    out = client.post("/api/admin/retention/run?days=365").json()
    assert out["deleted"] >= 1 and SessionLocal().get(M.Resume, r["resume_id"]) is None
    assert client.post("/api/admin/retention/run?days=0").json()["deleted"] == 0


def test_ontology_and_settings_endpoints(client):
    o = client.get("/api/ontology?category=Databases").json()
    assert o["count"] >= 8 and all(s["category"] == "Databases" for s in o["skills"])
    assert client.post("/api/ontology/reload").json()["reloaded"]
    s = client.get("/api/settings").json()
    assert s["default_weights"]["technical_skills"] == 0.4 and "Technical Skill Match" in s["formula"]


def test_saved_searches(client, loaded):
    r = client.post("/api/searches", json={"name": "ML seniors", "job_id": jid(loaded), "filters": {"min_exp": 5, "skills": "Python"}})
    assert r.status_code == 201
    assert any(x["name"] == "ML seniors" for x in client.get(f"/api/searches?job_id={jid(loaded)}").json())
    assert client.delete(f"/api/searches/{r.json()['id']}").status_code == 204
