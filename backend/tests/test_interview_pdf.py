"""Interview notes inside the candidate PDF report."""
import io

import pdfplumber
import pytest


def _text(resp):
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "application/pdf" and resp.content[:5] == b"%PDF-"
    with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
        return "\n".join((p.extract_text() or "") for p in pdf.pages)


@pytest.fixture()
def subject(client, loaded):
    """(job_id, candidate_id, candidate_name) of a ranked candidate; interview notes added by a test are removed afterwards."""
    job_id = next(iter(loaded["jobs"].values()))["id"]
    assert client.post(f"/api/matching/run/{job_id}", json={}).status_code == 201
    top = client.get(f"/api/matching/results/{job_id}?page_size=1").json()["items"][0]
    yield job_id, top["candidate_id"], top["name"]
    for n in client.get(f"/api/candidates/{top['candidate_id']}/interviews").json()["items"]:
        client.delete(f"/api/candidates/{top['candidate_id']}/interviews/{n['id']}")


def _pdf(client, job_id, cid, query=""):
    return client.get(f"/api/reports/{job_id}/candidate/{cid}/pdf{query}")


def test_pdf_lists_interviews_with_ratings_summary_and_escaped_text(client, subject):
    job_id, cid, _ = subject
    client.post(f"/api/candidates/{cid}/interviews", json={
        "round": "technical", "interviewer": "Asha Verma", "interviewed_on": "2026-11-10", "recommendation": "strong_yes", "job_id": job_id,
        "ratings": {"technical": 4, "communication": 5}, "strengths": "Great at <b>REST</b> & caching", "concerns": "Little cloud work",
        "notes": "First line of notes.\nSecond line of notes."})
    client.post(f"/api/candidates/{cid}/interviews", json={"round": "hr", "interviewed_on": "2026-11-12", "recommendation": "no", "ratings": {"communication": 2}})
    text = _text(_pdf(client, job_id, cid))
    assert "Interview notes" in text and "not part of the match score" in text
    assert "Asha Verma" in text and "Technical" in text and "2026-11-10" in text
    assert "Recommendation: Strong yes" in text and "Recommendation: No" in text
    assert "Technical 4/5" in text and "Communication 5/5" in text and "(average 4.5 / 5)" in text
    assert "Great at <b>REST</b> & caching" in text, "markup characters must appear literally, not be interpreted"
    assert "First line of notes." in text and "Second line of notes." in text
    assert "1 strong yes, 1 no" in text
    assert "3.3 / 5" in text, "mean of 4.5 and 2.0 is 3.25: rounded half up like the screen, not to even (3.2)"
    assert text.index("2026-11-12") < text.index("2026-11-10"), "newest interview first"


def test_half_up_rounding_matches_the_screen():
    from app.services.exports import _one_decimal
    assert [_one_decimal(x) for x in (3.25, 3.75, 4.0, 4.45, 2.05, 1.0)] == ["3.3", "3.8", "4.0", "4.5", "2.1", "1.0"]


def test_pdf_without_interviews_says_so(client, subject):
    job_id, cid, _ = subject
    text = _text(_pdf(client, job_id, cid))
    assert "Interview notes" in text and "No interviews recorded." in text


def test_pdf_can_leave_interviews_out(client, subject):
    job_id, cid, _ = subject
    client.post(f"/api/candidates/{cid}/interviews", json={"round": "final", "notes": "SECRET-INTERVIEW-TEXT"})
    text = _text(_pdf(client, job_id, cid, "?interviews=false"))
    assert "SECRET-INTERVIEW-TEXT" not in text and "Interview notes" not in text


def test_blind_pdf_hides_the_candidate_name_and_omits_interview_notes(client, subject):
    job_id, cid, name = subject
    client.post(f"/api/candidates/{cid}/interviews", json={"round": "final", "interviewer": "Asha Verma", "notes": f"SECRET-INTERVIEW-TEXT about {name}"})
    text = _text(_pdf(client, job_id, cid, "?blind=true"))
    assert "SECRET-INTERVIEW-TEXT" not in text and "Asha Verma" not in text
    assert "omitted from blind-screening reports" in text
    assert name not in text, "the real name must not appear in a blind report"


def test_pdf_export_is_audited_with_the_interview_count_only(client, subject):
    job_id, cid, _ = subject
    client.post(f"/api/candidates/{cid}/interviews", json={"round": "final", "notes": "SECRET-INTERVIEW-TEXT"})
    assert _pdf(client, job_id, cid).status_code == 200
    audit = client.get("/api/audit?page_size=10").json()
    items = audit["items"] if isinstance(audit, dict) else audit
    exp = [a for a in items if a["action"] == "report.exported" and "candidate" in str(a)][0]
    assert "'interviews': 1" in str(exp) or '"interviews": 1' in str(exp)
    assert "SECRET-INTERVIEW-TEXT" not in str(exp)


def test_non_latin_notes_never_break_the_pdf(client, subject):
    job_id, cid, _ = subject
    client.post(f"/api/candidates/{cid}/interviews", json={"round": "hr", "interviewer": "आशा", "notes": "बहुत अच्छा इंटरव्यू 👍 — résumé naïve café", "strengths": "日本語 العربية"})
    resp = _pdf(client, job_id, cid)
    text = _text(resp)                                    # must still be a valid PDF with the Latin text intact
    assert "Interview notes" in text and "Recommendation:" in text
    assert "résumé naïve café" in text


def test_long_notes_do_not_break_the_pdf(client, subject):
    job_id, cid, _ = subject
    for i in range(6):
        client.post(f"/api/candidates/{cid}/interviews", json={"round": "other", "notes": ("Long paragraph %d. " % i) * 200})
    text = _text(_pdf(client, job_id, cid))
    assert text.count("Recommendation:") == 6 and "Long paragraph 5." in text
