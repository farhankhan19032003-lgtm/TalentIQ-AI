"""Interview notes inside the Excel exports (job ranking workbook and talent matrix workbook)."""
import datetime
import io

import pytest
from openpyxl import load_workbook


def _wb(resp):
    assert resp.status_code == 200, resp.text
    return load_workbook(io.BytesIO(resp.content))


def _all_text(wb) -> str:
    return "\n".join(str(c.value) for ws in wb for row in ws.iter_rows() for c in row if c.value is not None)


@pytest.fixture()
def subject(client, loaded):
    """(job_id, [top candidate ids], names) of a ranked job; interview notes created by a test are removed afterwards."""
    job_id = next(iter(loaded["jobs"].values()))["id"]
    assert client.post(f"/api/matching/run/{job_id}", json={}).status_code == 201
    items = client.get(f"/api/matching/results/{job_id}?page_size=100").json()["items"]
    ids = [i["candidate_id"] for i in items]
    yield job_id, ids, {i["candidate_id"]: i["name"] for i in items}
    for cid in ids[:4]:
        for n in client.get(f"/api/candidates/{cid}/interviews").json()["items"]:
            client.delete(f"/api/candidates/{cid}/interviews/{n['id']}")


def _seed(client, job_id, ids):
    a = client.post(f"/api/candidates/{ids[0]}/interviews", json={
        "round": "technical", "interviewer": "Asha Verma", "interviewed_on": "2026-11-10", "recommendation": "strong_yes", "job_id": job_id,
        "ratings": {"technical": 5, "communication": 4, "problem_solving": 4, "collaboration": 5},
        "strengths": "=HYPERLINK(\"http://evil\",\"x\")", "concerns": "Little cloud work", "notes": "Line one.\nLine two."}).json()
    b = client.post(f"/api/candidates/{ids[0]}/interviews", json={"round": "hr", "interviewed_on": "2026-11-12", "recommendation": "no", "ratings": {"communication": 2}}).json()
    c = client.post(f"/api/candidates/{ids[1]}/interviews", json={"round": "final", "interviewed_on": "2026-11-11", "notes": "unrated"}).json()
    return a, b, c


def test_job_workbook_gets_interview_columns_and_sheet(client, subject):
    job_id, ids, names = subject
    _seed(client, job_id, ids)
    wb = _wb(client.get(f"/api/reports/{job_id}/excel"))
    assert wb.sheetnames == ["Ranking", "Interviews", "Skill matrix", "Run info"]
    rk = wb["Ranking"]
    head = [c.value for c in rk[1]]
    assert head[-2:] == ["Interviews", "Interview avg rating (1-5)"]
    rows = {r[1].value: [c.value for c in r] for r in rk.iter_rows(min_row=2)}           # keyed by candidate name
    top = rows[names[ids[0]]]
    assert top[-2] == 2 and top[-1] == 3.25, "mean of per-interview averages 4.5 and 2.0 (same figure as the screen)"
    assert rows[names[ids[1]]][-2:] == [1, None], "an unrated interview counts but has no average"
    assert rows[names[ids[2]]][-2:] == [0, None]
    ws = wb["Interviews"]
    h = [c.value for c in ws[1]]
    assert h[:8] == ["Candidate", "Rank", "Stage", "Round", "Date", "Interviewer", "Linked job", "Recommendation"] and h[12] == "Average (1-5)"
    data = [[c.value for c in r] for r in ws.iter_rows(min_row=2)]
    assert len(data) == 3
    assert [d[0] for d in data] == [names[ids[0]], names[ids[0]], names[ids[1]]], "candidates in ranking order"
    assert [d[3] for d in data[:2]] == ["HR", "Technical"], "newest interview first within a candidate"
    tech = data[1]
    assert isinstance(tech[4], datetime.datetime) or isinstance(tech[4], datetime.date)
    assert str(tech[4])[:10] == "2026-11-10" and tech[5] == "Asha Verma" and tech[7] == "Strong yes"
    assert tech[8:12] == [5, 4, 4, 5] and tech[12] == 4.5 and tech[6], "ratings, average and linked job title"
    assert tech[13].startswith("'="), "free text is protected against formula injection"
    assert tech[14] == "Little cloud work" and tech[15] == "Line one.\nLine two."
    assert ws.freeze_panes == "B2" and ws.conditional_formatting


def test_job_workbook_without_any_interviews_still_has_a_clear_sheet(client, subject):
    job_id, _, _ = subject
    ws = _wb(client.get(f"/api/reports/{job_id}/excel"))["Interviews"]
    assert ws["A2"].value == "No interviews recorded for these candidates."


def test_job_workbook_can_leave_interviews_out(client, subject):
    job_id, ids, _ = subject
    _seed(client, job_id, ids)
    wb = _wb(client.get(f"/api/reports/{job_id}/excel?interviews=false"))
    assert "Interviews" not in wb.sheetnames
    assert [c.value for c in wb["Ranking"][1]][-1] != "Interview avg rating (1-5)"
    assert "Asha Verma" not in _all_text(wb)


def test_blind_workbook_has_no_interview_data_at_all(client, subject):
    job_id, ids, names = subject
    _seed(client, job_id, ids)
    wb = _wb(client.get(f"/api/reports/{job_id}/excel?blind=true"))
    assert "Interviews" not in wb.sheetnames
    text = _all_text(wb)
    for secret in ("Asha Verma", "Line one", "Little cloud work", "unrated"):
        assert secret not in text
    assert "omitted from blind-screening exports" in text
    assert names[ids[0]] not in text, "real names stay hidden in blind mode"


def test_matrix_gets_count_and_average_but_never_text(client, subject):
    job_id, ids, names = subject
    _seed(client, job_id, ids)
    wb = _wb(client.get("/api/reports/matrix/excel"))
    ws = wb["Talent matrix"]
    head = [c.value for c in ws[1]]
    assert head[-2:] == ["Interviews", "Interview avg rating (1-5)"] and head[-5:-2] == ["Best fit job", "Best score", "Jobs scoring 50+"]
    rows = {r[0].value: [c.value for c in r] for r in ws.iter_rows(min_row=2)}
    assert rows[names[ids[0]]][-2:] == [2, 3.25] and rows[names[ids[1]]][-2:] == [1, None] and rows[names[ids[2]]][-2:] == [0, None]
    assert ws.auto_filter.ref.endswith(str(ws.max_row)) and ws.auto_filter.ref.startswith("A1:")
    text = _all_text(wb)
    for secret in ("Asha Verma", "Line one", "Little cloud work", "HYPERLINK"):
        assert secret not in text, "the matrix carries numbers only"
    assert "interview text is never part of this export" in text


def test_matrix_interview_columns_can_be_dropped_and_vanish_in_blind_mode(client, subject):
    job_id, ids, _ = subject
    _seed(client, job_id, ids)
    for q in ("?interviews=false", "?blind=true"):
        head = [c.value for c in _wb(client.get(f"/api/reports/matrix/excel{q}"))["Talent matrix"][1]]
        assert head[-1] == "Jobs scoring 50+", q


def _csv(resp):
    import csv
    assert resp.status_code == 200, resp.text
    return list(csv.reader(io.StringIO(resp.content.decode("utf-8-sig"))))


def test_csv_gets_count_and_average_but_never_text(client, subject):
    job_id, ids, names = subject
    _seed(client, job_id, ids)
    rows = _csv(client.get(f"/api/reports/{job_id}/csv"))
    head = rows[0]
    assert head[-3:] == ["No-evidence skills", "Interviews", "Interview avg rating (1-5)"]
    by_name = {r[1]: r for r in rows[1:]}
    assert by_name[names[ids[0]]][-2:] == ["2", "3.25"], "same figures as the Excel export and the screen"
    assert by_name[names[ids[1]]][-2:] == ["1", ""], "an unrated interview counts but has no average"
    assert by_name[names[ids[2]]][-2:] == ["0", ""]
    assert all(len(r) == len(head) for r in rows), "every row has every column"
    raw = "\n".join(",".join(r) for r in rows)
    for secret in ("Asha Verma", "Line one", "Little cloud work", "HYPERLINK"):
        assert secret not in raw, "the CSV carries numbers only"


def test_csv_interview_columns_can_be_dropped_and_vanish_in_blind_mode(client, subject):
    job_id, ids, _ = subject
    _seed(client, job_id, ids)
    original = _csv(client.get(f"/api/reports/{job_id}/csv?interviews=false"))[0]
    assert original[-1] == "No-evidence skills", "interviews=false restores the original columns"
    blind = _csv(client.get(f"/api/reports/{job_id}/csv?blind=true"))
    assert blind[0] == original and all(len(r) == len(original) for r in blind)


def test_exports_are_audited_with_the_interview_count_only(client, subject):
    job_id, ids, _ = subject
    _seed(client, job_id, ids)
    client.get(f"/api/reports/{job_id}/excel")
    audit = client.get("/api/audit?page_size=10").json()
    items = audit["items"] if isinstance(audit, dict) else audit
    exp = [a for a in items if a["action"] == "report.exported" and "xlsx" in str(a)][0]
    assert "3" in str(exp) and "interviews" in str(exp)
    assert "Asha Verma" not in str(exp) and "Line one" not in str(exp)
