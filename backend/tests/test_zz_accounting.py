"""Every uploaded file must be accountable: stored, parsed, failed, duplicate skipped, ranked or not yet ranked.
Named test_zz_* so it runs after the tests that assume the original synthetic batch."""
from helpers import make_pdf, simple_resume


def _acc(client, job_id):
    return client.get("/api/resumes/accounting", params={"job_id": job_id}).json()


def _upload(client, name, data):
    return client.post("/api/resumes/upload", files=[("files", (name, data, "application/pdf"))]).json()


def test_duplicates_are_counted_and_listed_and_late_uploads_flag_a_stale_run(client, loaded):
    job_id = next(iter(loaded["jobs"].values()))["id"]
    run = client.post(f"/api/matching/run/{job_id}", json={}).json()
    before = _acc(client, job_id)
    assert before["not_in_run"] == 0 and before["run_is_stale"] is False
    assert before["ranked_in_run"] == run["n_candidates"]

    pdf = make_pdf(simple_resume(name="Accounting Example", email="accounting.example@example.com"))
    first = _upload(client, "late_resume.pdf", pdf)
    again = _upload(client, "late_resume_copy.pdf", pdf)
    assert first["summary"]["parsed"] == 1 and again["summary"]["duplicate"] == 1

    after = _acc(client, job_id)
    assert after["files_received"] == before["files_received"] + 2          # nothing disappears silently
    assert after["stored"] == before["stored"] + 1
    assert after["duplicates_skipped"] == before["duplicates_skipped"] + 1
    assert after["duplicates"][0]["identical_to_filename"] == "late_resume.pdf"
    assert after["not_in_run"] == 1 and after["run_is_stale"] is True       # the ranking predates this resume

    ranking = client.get(f"/api/matching/results/{job_id}").json()
    assert ranking["pool"]["run_is_stale"] is True and ranking["pool"]["not_in_run"] == 1

    client.post(f"/api/matching/run/{job_id}", json={})
    healed = _acc(client, job_id)
    assert healed["not_in_run"] == 0 and healed["run_is_stale"] is False
    assert healed["ranked_in_run"] == healed["parsed"]
