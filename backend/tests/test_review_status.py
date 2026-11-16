"""Recruiter pipeline stages: every stage the UI offers must be accepted by the API."""

STAGES = ["new", "reviewed", "shortlisted", "interview", "on_hold", "not_progressing", "in_review"]


def _candidate_id(loaded):
    return next(r["candidate_id"] for r in loaded["upload"]["results"] if r.get("candidate_id"))


def test_all_pipeline_stages_are_accepted(client, loaded):
    cid = _candidate_id(loaded)
    for stage in STAGES:
        r = client.patch(f"/api/candidates/{cid}/status", json={"review_status": stage})
        assert r.status_code == 200, (stage, r.text)
        assert r.json() == {"candidate_id": cid, "review_status": stage}
    client.patch(f"/api/candidates/{cid}/status", json={"review_status": "new"})


def test_unknown_stage_is_rejected(client, loaded):
    cid = _candidate_id(loaded)
    r = client.patch(f"/api/candidates/{cid}/status", json={"review_status": "hired_automatically"})
    assert r.status_code in (400, 422)
    assert client.patch("/api/candidates/999999/status", json={"review_status": "new"}).status_code == 404


def _ids(loaded, n):
    """First n *distinct* candidate ids (a duplicate resume can map to an existing candidate)."""
    return list(dict.fromkeys(r["candidate_id"] for r in loaded["upload"]["results"] if r.get("candidate_id")))[:n]


def _status(client, cid):
    return client.get(f"/api/matching/candidate/{cid}").json()["candidate"]["review_status"]


def test_bulk_shortlist_changes_all_and_reports_previous_status(client, loaded):
    ids = _ids(loaded, 4)
    client.patch(f"/api/candidates/{ids[0]}/status", json={"review_status": "interview"})
    r = client.post("/api/candidates/status/bulk", json={"candidate_ids": ids, "review_status": "shortlisted"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["updated"] == 4 and body["unchanged"] == 0 and body["requested"] == 4
    assert {c["candidate_id"]: c["from"] for c in body["changes"]}[ids[0]] == "interview"   # enables Undo
    assert all(_status(client, i) == "shortlisted" for i in ids)
    # idempotent: nothing left to change
    again = client.post("/api/candidates/status/bulk", json={"candidate_ids": ids, "review_status": "shortlisted"}).json()
    assert again["updated"] == 0 and again["unchanged"] == 4 and again["changes"] == []
    for i in ids:
        client.patch(f"/api/candidates/{i}/status", json={"review_status": "new"})


def test_bulk_is_all_or_nothing_and_validated(client, loaded):
    ids = _ids(loaded, 2)
    r = client.post("/api/candidates/status/bulk", json={"candidate_ids": ids + [999999], "review_status": "shortlisted"})
    assert r.status_code == 404 and "999999" in r.text
    assert all(_status(client, i) == "new" for i in ids), "an unknown id must not change anyone"
    assert client.post("/api/candidates/status/bulk", json={"candidate_ids": [], "review_status": "new"}).status_code == 422
    assert client.post("/api/candidates/status/bulk", json={"candidate_ids": ids, "review_status": "hired"}).status_code == 422
    assert client.post("/api/candidates/status/bulk", json={"candidate_ids": list(range(1, 202)), "review_status": "new"}).status_code == 422


def test_bulk_deduplicates_and_audits_each_change_without_pii(client, loaded):
    ids = _ids(loaded, 2)
    body = client.post("/api/candidates/status/bulk", json={"candidate_ids": ids + ids, "review_status": "reviewed"}).json()
    assert body["requested"] == 2 and body["updated"] == 2
    items = client.get("/api/audit?page_size=50").json()
    items = items["items"] if isinstance(items, dict) else items
    bulk = [a for a in items if a["action"] == "candidate.status_changed" and "bulk" in str(a)]
    assert len(bulk) >= 2 and "@" not in str(bulk[:2])
    for i in ids:
        client.patch(f"/api/candidates/{i}/status", json={"review_status": "new"})


def test_status_change_is_audited_without_pii(client, loaded):
    cid = _candidate_id(loaded)
    client.patch(f"/api/candidates/{cid}/status", json={"review_status": "interview"})
    client.patch(f"/api/candidates/{cid}/status", json={"review_status": "new"})
    audit = client.get("/api/audit?page_size=50").json()
    items = audit["items"] if isinstance(audit, dict) else audit
    changes = [a for a in items if a["action"] == "candidate.status_changed"]
    assert changes, "status changes must be audit-logged"
    assert "@" not in str(changes[0])
