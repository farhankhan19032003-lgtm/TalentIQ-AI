"""Interview notes: structured scorecards written by humans."""
import pytest


@pytest.fixture()
def cand(client, loaded):
    """A throwaway candidate so these tests never disturb the shared sample data."""
    from app.core.database import SessionLocal
    from app.models import db as M
    s = SessionLocal()
    c = M.Candidate(name="Interview Test Person", email="interview.test@example.com", parsed={})
    s.add(c)
    s.commit()
    cid = c.id
    s.close()
    yield cid
    client.delete(f"/api/candidates/{cid}")


GOOD = {"round": "technical", "interviewer": "A. Interviewer", "interviewed_on": "2026-11-10", "recommendation": "yes",
        "ratings": {"technical": 4, "communication": 5, "problem_solving": 3, "collaboration": 4},
        "strengths": "Clear thinker", "concerns": "Limited cloud exposure", "notes": "Solid system design discussion."}


def test_add_list_and_summary(client, cand):
    r = client.post(f"/api/candidates/{cand}/interviews", json=GOOD)
    assert r.status_code == 201, r.text
    n = r.json()
    assert n["round"] == "technical" and n["recommendation"] == "yes" and n["rating_avg"] == 4.0 and n["interviewed_on"] == "2026-11-10"
    client.post(f"/api/candidates/{cand}/interviews", json={"round": "hr", "interviewed_on": "2026-11-12", "recommendation": "strong_yes", "ratings": {"communication": 5}})
    client.post(f"/api/candidates/{cand}/interviews", json={"round": "final", "interviewed_on": "2026-11-01", "recommendation": "no", "notes": "Not a fit for the team."})
    out = client.get(f"/api/candidates/{cand}/interviews").json()
    assert [i["round"] for i in out["items"]] == ["hr", "technical", "final"], "newest interview first"
    s = out["summary"]
    assert s["count"] == 3 and s["avg_rating"] == 4.5          # mean of the per-interview averages (4.0 and 5.0); unrated one ignored
    assert s["avg_by_criterion"]["communication"] == 5.0 and s["avg_by_criterion"]["collaboration"] == 4.0
    assert s["recommendations"] == {"strong_yes": 1, "yes": 1, "no": 1, "strong_no": 0, "undecided": 0}
    assert "verdict" not in s and "consensus" not in s, "the app tallies opinions; it never decides"


def test_update_and_delete(client, cand):
    n = client.post(f"/api/candidates/{cand}/interviews", json=GOOD).json()
    u = client.patch(f"/api/candidates/{cand}/interviews/{n['id']}", json={"recommendation": "no", "ratings": {"technical": 2}, "notes": "  Changed my mind.  "}).json()
    assert u["recommendation"] == "no" and u["ratings"] == {"technical": 2} and u["notes"] == "Changed my mind." and u["strengths"] == "Clear thinker"
    assert u["updated_at"] >= n["updated_at"]
    assert client.patch(f"/api/candidates/{cand}/interviews/{n['id']}", json={"recommendation": None}).json()["recommendation"] == "no", "explicit null does not clear"
    assert client.delete(f"/api/candidates/{cand}/interviews/{n['id']}").status_code == 204
    assert client.get(f"/api/candidates/{cand}/interviews").json()["items"] == []
    assert client.delete(f"/api/candidates/{cand}/interviews/{n['id']}").status_code == 404


def test_cannot_empty_a_note_by_updating_it(client, cand):
    n = client.post(f"/api/candidates/{cand}/interviews", json={"round": "hr", "notes": "only a note"}).json()
    r = client.patch(f"/api/candidates/{cand}/interviews/{n['id']}", json={"notes": "   "})
    assert r.status_code == 422 and "cannot be empty" in r.text


@pytest.mark.parametrize("payload", [
    {},                                                                    # nothing at all
    {"round": "technical"},                                                # still nothing
    {"ratings": {"technical": 6}},                                         # out of range
    {"ratings": {"technical": 0}},
    {"ratings": {"charisma": 3}},                                          # unknown criterion
    {"round": "coffee_chat", "notes": "x"},                                # unknown round
    {"recommendation": "hire_now", "notes": "x"},                          # unknown recommendation
    {"notes": "x" * 4001},                                                 # too long
    {"notes": "x", "interviewed_on": "not-a-date"},
])
def test_validation(client, cand, payload):
    assert client.post(f"/api/candidates/{cand}/interviews", json=payload).status_code == 422


def test_unknown_candidate_job_and_note(client, cand):
    assert client.post("/api/candidates/999999/interviews", json=GOOD).status_code == 404
    assert client.get("/api/candidates/999999/interviews").status_code == 404
    assert client.post(f"/api/candidates/{cand}/interviews", json={**GOOD, "job_id": 999999}).status_code == 404
    assert client.patch(f"/api/candidates/{cand}/interviews/999999", json={"notes": "x"}).status_code == 404


def test_note_of_another_candidate_cannot_be_touched(client, cand, loaded):
    other = next(r["candidate_id"] for r in loaded["upload"]["results"] if r.get("candidate_id"))
    n = client.post(f"/api/candidates/{cand}/interviews", json=GOOD).json()
    assert client.patch(f"/api/candidates/{other}/interviews/{n['id']}", json={"notes": "hijack"}).status_code == 404
    assert client.delete(f"/api/candidates/{other}/interviews/{n['id']}").status_code == 404


def test_linked_job_is_kept_and_cleared_independently(client, cand, loaded):
    job_id = next(iter(loaded["jobs"].values()))["id"]
    n = client.post(f"/api/candidates/{cand}/interviews", json={**GOOD, "job_id": job_id}).json()
    assert n["job_id"] == job_id
    assert client.patch(f"/api/candidates/{cand}/interviews/{n['id']}", json={"job_id": None}).json()["job_id"] is None


def test_batch_summary_matches_the_per_candidate_summary(client, cand, loaded):
    other = next(r["candidate_id"] for r in loaded["upload"]["results"] if r.get("candidate_id"))
    client.post(f"/api/candidates/{cand}/interviews", json=GOOD)                                                    # avg 4.0, yes
    client.post(f"/api/candidates/{cand}/interviews", json={"round": "hr", "recommendation": "no", "ratings": {"communication": 2}})   # avg 2.0, no
    client.post(f"/api/candidates/{cand}/interviews", json={"round": "final", "notes": "unrated"})                 # no rating
    r = client.get(f"/api/candidates/interviews/summary?ids={cand},{other},999999")
    assert r.status_code == 200, r.text
    s = r.json()["summaries"]
    assert set(s) == {str(cand)}, "candidates without interviews (and unknown ids) are simply absent"
    full = client.get(f"/api/candidates/{cand}/interviews").json()["summary"]
    assert s[str(cand)] == {"count": 3, "avg_rating": full["avg_rating"], "recommendations": full["recommendations"]}
    assert s[str(cand)]["avg_rating"] == 3.0 and s[str(cand)]["recommendations"]["yes"] == 1 and s[str(cand)]["recommendations"]["no"] == 1


def test_batch_summary_validates_ids_and_is_not_shadowed(client, cand):
    assert client.get("/api/candidates/interviews/summary").status_code == 422            # ids is required
    for bad in ("", "abc", "1,x", "1;2", "-3"):
        assert client.get(f"/api/candidates/interviews/summary?ids={bad}").status_code == 422, bad
    assert client.get(f"/api/candidates/interviews/summary?ids={cand}").json() == {"summaries": {}}
    too_many = ",".join(str(i) for i in range(1, 1002))
    assert client.get(f"/api/candidates/interviews/summary?ids={too_many}").status_code == 422


def test_deleting_the_candidate_erases_their_interview_notes(client, cand):
    from app.core.database import SessionLocal
    from app.models import db as M
    client.post(f"/api/candidates/{cand}/interviews", json=GOOD)
    client.post(f"/api/candidates/{cand}/interviews", json={**GOOD, "round": "final"})
    s = SessionLocal()
    assert s.query(M.InterviewNote).filter_by(candidate_id=cand).count() == 2
    s.close()
    assert client.delete(f"/api/candidates/{cand}").status_code == 204
    s = SessionLocal()
    assert s.query(M.InterviewNote).filter_by(candidate_id=cand).count() == 0, "privacy: nothing about a deleted candidate may remain"
    s.close()


def test_interview_actions_are_audited_without_pii_or_note_text(client, cand):
    n = client.post(f"/api/candidates/{cand}/interviews", json={**GOOD, "notes": "SECRET-NOTE-TEXT"}).json()
    client.patch(f"/api/candidates/{cand}/interviews/{n['id']}", json={"recommendation": "no"})
    client.delete(f"/api/candidates/{cand}/interviews/{n['id']}")
    audit = client.get("/api/audit?page_size=30").json()
    items = audit["items"] if isinstance(audit, dict) else audit
    actions = [a for a in items if a["action"].startswith("interview.")]
    assert {"interview.added", "interview.updated", "interview.deleted"} <= {a["action"] for a in actions}
    blob = str(actions)
    assert "SECRET-NOTE-TEXT" not in blob and "interview.test@example.com" not in blob and "Interview Test Person" not in blob
