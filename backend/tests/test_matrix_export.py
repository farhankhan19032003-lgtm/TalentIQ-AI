"""Talent matrix Excel export: every candidate x every ranked job."""
import io

from openpyxl import load_workbook

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _run_two_jobs(client, loaded):
    ids = [j["id"] for j in list(loaded["jobs"].values())[:2]]
    for i in ids:
        assert client.post(f"/api/matching/run/{i}", json={}).status_code == 201
    return ids


def _wb(resp):
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith(XLSX)
    assert "talentiq_talent_matrix.xlsx" in resp.headers["content-disposition"]
    return load_workbook(io.BytesIO(resp.content))


def test_matrix_route_is_not_shadowed_by_job_id_routes(client, loaded):
    _run_two_jobs(client, loaded)
    assert client.get("/api/reports/matrix/excel").status_code == 200   # not a 422 from /reports/{job_id}/excel


def test_matrix_workbook_structure_and_scores(client, loaded):
    job_ids = _run_two_jobs(client, loaded)
    wb = _wb(client.get("/api/reports/matrix/excel"))
    assert wb.sheetnames == ["Talent matrix", "Ranks", "Top picks", "Info"]
    ws = wb["Talent matrix"]
    head = [c.value for c in ws[1]]
    # default: ... Best fit job | Best score | Jobs scoring 50+ | Interviews | Interview avg rating (1-5)
    assert head[:3] == ["Candidate", "Latest role", "Stage"] and head[-5:] == ["Best fit job", "Best score", "Jobs scoring 50+", "Interviews", "Interview avg rating (1-5)"]
    plain = [c.value for c in _wb(client.get("/api/reports/matrix/excel?interviews=false"))["Talent matrix"][1]]
    assert plain[-3:] == ["Best fit job", "Best score", "Jobs scoring 50+"], "interviews=false restores the original layout"
    ranked_jobs = [h for h in head[3:-5]]
    assert len(ranked_jobs) >= 2
    rows = [[c.value for c in r] for r in ws.iter_rows(min_row=2)]
    assert len(rows) >= 30, "every ranked candidate appears once"
    bests = [r[-4] for r in rows if r[-4] is not None]                 # "Best score" column
    assert bests == sorted(bests, reverse=True), "default order is best score first"
    for r in rows:
        scores = [v for v in r[3:-5] if v is not None]
        if scores:
            assert r[-4] == max(scores) and 0 <= r[-4] <= 100
    assert ws.freeze_panes == "D2" and ws.conditional_formatting, "heatmap colour scale is applied"
    assert [c.value for c in wb["Ranks"][1]][0] == "Candidate"
    top = [[c.value for c in r] for r in wb["Top picks"].iter_rows(min_row=2)]
    assert len(top) == len(ranked_jobs) and all(t[2] is not None for t in top)
    info = {r[0].value: r[1].value for r in wb["Info"].iter_rows()}
    assert "Emails and phone numbers are intentionally not included" in info["Contact details"]
    assert len(rows) == len({c["candidate_id"] for j in job_ids for c in client.get(f"/api/matching/results/{j}?page_size=100").json()["items"]}), \
        "one row per distinct candidate across the ranked jobs"


def test_matrix_export_respects_requested_ids_and_order(client, loaded):
    _run_two_jobs(client, loaded)
    results = client.get(f"/api/matching/results/{list(loaded['jobs'].values())[0]['id']}?page_size=100").json()["items"]
    pick = [results[5], results[1], results[3]]                      # deliberately not in rank order
    ids = ",".join(str(r["candidate_id"]) for r in pick)
    ws = _wb(client.get(f"/api/reports/matrix/excel?ids={ids}"))["Talent matrix"]
    assert [r[0].value for r in ws.iter_rows(min_row=2)] == [r["name"] for r in pick]
    ws2 = _wb(client.get(f"/api/reports/matrix/excel?ids={ids},999999"))["Talent matrix"]
    assert ws2.max_row == 4, "unknown ids are skipped, not an error"


def test_matrix_ids_are_validated(client, loaded):
    _run_two_jobs(client, loaded)
    for bad in ("abc", "1,2,x", "1;2", "-5"):
        assert client.get(f"/api/reports/matrix/excel?ids={bad}").status_code == 422, bad


def test_matrix_blind_mode_hides_names(client, loaded):
    _run_two_jobs(client, loaded)
    normal = _wb(client.get("/api/reports/matrix/excel"))["Talent matrix"]
    blind = _wb(client.get("/api/reports/matrix/excel?blind=true"))["Talent matrix"]
    real_names = {r[0].value for r in normal.iter_rows(min_row=2)}
    blind_names = {r[0].value for r in blind.iter_rows(min_row=2)}
    assert real_names and not (real_names & blind_names), "no real name survives blind mode"
    assert "on" in {r[0].value: r[1].value for r in _wb(client.get("/api/reports/matrix/excel?blind=true"))["Info"].iter_rows()}["Blind screening"]


def test_matrix_header_cells_are_sanitised_against_formula_injection(client, loaded):
    jd = "Job Title: x\nRequirements:\n- Python\n- 2+ years of experience\n"
    j = client.post("/api/jobs", json={"title": "=HYPERLINK(\"http://evil\",\"x\")", "description": jd}).json()
    try:
        assert client.post(f"/api/matching/run/{j['id']}", json={}).status_code == 201
        ws = _wb(client.get("/api/reports/matrix/excel"))["Talent matrix"]
        titles = [c.value for c in ws[1]]
        assert not any(isinstance(t, str) and t.startswith("=") for t in titles)
        assert any(isinstance(t, str) and t.startswith("'=HYPERLINK") for t in titles)
    finally:
        client.delete(f"/api/jobs/{j['id']}")


def test_matrix_export_is_audited_without_pii(client, loaded):
    _run_two_jobs(client, loaded)
    client.get("/api/reports/matrix/excel?blind=true")
    items = client.get("/api/audit?page_size=20").json()
    items = items["items"] if isinstance(items, dict) else items
    exp = [a for a in items if a["action"] == "report.exported" and "matrix" in str(a)]
    assert exp and "@" not in str(exp[0])
