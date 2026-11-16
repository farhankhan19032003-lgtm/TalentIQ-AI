"""Browser end-to-end check (manual tool, not part of pytest).
Prereqs: pip install playwright ; backend on :8000 with an EMPTY database ; `npm run dev` on :5173.
Set CHROME to a Chrome/Chromium executable path (default: /usr/bin/google-chrome; on Windows e.g.
C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe). It loads the synthetic TEST data, drives the whole UI
and prints PASS/FAIL per step plus browser console errors and failed HTTP calls. Screenshots go to ./e2e_out/.
"""
import os
os.makedirs("e2e_out", exist_ok=True)
import json, sys
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5173"
errors, failed = [], []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME", "/usr/bin/google-chrome"), args=["--no-sandbox"])
    pg = b.new_page(viewport={"width": 1400, "height": 900})
    pg.on("console", lambda m: errors.append(f"{m.type}: {m.text}") if m.type in ("error", "warning") else None)
    pg.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
    pg.on("response", lambda r: failed.append(f"{r.status} {r.url}") if r.status >= 400 else None)
    log = []
    def step(name, fn):
        try: fn(); log.append((name, "PASS", ""))
        except Exception as e: log.append((name, "FAIL", str(e)[:200]))

    step("dashboard loads", lambda: (pg.goto(BASE), pg.wait_for_selector("text=Dashboard")))
    step("empty state offers synthetic test data", lambda: pg.wait_for_selector("text=Load synthetic test data"))
    def load():
        pg.click("text=Load synthetic test data"); pg.wait_for_selector("text=Loaded synthetic TEST resumes", timeout=90000)
    step("load synthetic test data", load)
    pg.screenshot(path="e2e_out/s1_dashboard.png")
    def select_job():
        pg.goto(BASE + "/jobs"); pg.wait_for_selector("text=AI/ML Engineer", timeout=15000) if pg.locator("text=AI/ML Engineer").count() or True else None
    step("jobs page lists templates", lambda: (pg.goto(BASE + "/jobs"), pg.wait_for_selector("table")))
    def rank():
        pg.goto(BASE + "/jobs"); pg.wait_for_selector("table")
        row = pg.locator("tr", has_text="AI").first
        row.get_by_role("button", name="Rank").click()
        pg.wait_for_selector("text=Candidate ranking"); pg.click("text=Run matching"); pg.wait_for_selector("text=Candidates ranked", timeout=60000)
    step("select job, run matching, ranking table", rank)
    pg.screenshot(path="e2e_out/s2_ranking.png")
    step("table has rows", lambda: (_ for _ in ()).throw(Exception("no rows")) if pg.locator("tbody tr").count() < 5 else None)
    def filt():
        pg.fill("#ms", "50"); pg.wait_for_timeout(800)
        n = pg.locator("tbody tr").count(); assert n >= 1
    step("min-score filter", filt)
    def cmp():
        pg.fill("#ms", ""); pg.wait_for_timeout(600)
        boxes = pg.locator("tbody input[type=checkbox]"); boxes.nth(0).check(); boxes.nth(1).check()
        pg.click("text=/Compare \\(2\\/5\\)/"); pg.wait_for_selector("text=Compare candidates"); pg.wait_for_selector("text=Requirements")
    step("compare 2 candidates", cmp)
    pg.screenshot(path="e2e_out/s3_compare.png")
    def cand():
        pg.go_back(); pg.wait_for_selector("tbody tr")
        pg.locator("tbody tr a").first.click(); pg.wait_for_selector("text=Why this score"); pg.wait_for_selector("text=Requirement evidence")
    step("candidate profile", cand)
    def ev():
        pg.locator("tr.cursor-pointer").first.click(); pg.wait_for_selector("blockquote"); assert "verbatim" in pg.locator("blockquote").first.inner_text()
    step("evidence viewer shows verbatim snippet", ev)
    pg.screenshot(path="e2e_out/s4_candidate.png", full_page=True)
    def note():
        pg.fill("textarea[aria-label='Add note']", "Strong profile"); pg.click("text=Add note"); pg.wait_for_selector("text=Strong profile")
    step("add note persists", note)
    def status():
        pg.select_option("#rs", "shortlisted"); pg.wait_for_timeout(800); assert pg.locator("#rs").input_value() == "shortlisted"
    step("change status", status)
    def override():
        pg.fill("input[aria-label='New score']", "90"); pg.fill("textarea[aria-label='Override reason']", "Verified portfolio on call")
        pg.click("text=Record override"); pg.wait_for_selector("text=Override to")
    step("manual override with reason", override)
    def blind():
        pg.click("text=/Blind screening/"); pg.wait_for_selector("text=/Candidate C-/", timeout=10000)
        assert "@example.com" not in pg.content()
    step("blind mode hides identity", blind)
    pg.click("text=/Blind screening/")
    def exports():
        pg.goto(BASE + "/ranking"); pg.wait_for_selector("text=Candidates ranked")
        for lbl in ("CSV", "Excel", "PDF"):
            with pg.expect_download(timeout=30000) as d: pg.get_by_role("button", name=lbl, exact=True).click()
            assert d.value.suggested_filename
    step("CSV/Excel/PDF downloads", exports)
    def whatif():
        pg.goto(BASE + "/whatif"); pg.fill("#wy", "6"); pg.click("text=Run simulation"); pg.wait_for_selector("text=Persisted: no", timeout=30000)
    step("what-if simulation", whatif)
    def analytics():
        pg.goto(BASE + "/analytics"); pg.wait_for_selector("text=Score distribution", timeout=20000); pg.wait_for_selector("text=Talent pool")
    step("analytics + talent pool", analytics)
    pg.screenshot(path="e2e_out/s5_analytics.png", full_page=True)
    def upload():
        pg.goto(BASE + "/upload"); open("e2e_out/bad.pdf", "wb").write(b"%PDF-1.4 garbage")
        pg.set_input_files("input[type=file]", ["e2e_out/bad.pdf"]); pg.click("text=Upload & parse"); pg.wait_for_selector("text=Batch result", timeout=30000)
        assert "corrupt" in pg.content().lower() or "failed" in pg.content().lower()
    step("upload corrupted file handled", upload)
    def resumes():
        pg.goto(BASE + "/resumes"); pg.wait_for_selector("text=Parse success"); pg.wait_for_selector("tbody tr")
    step("resume batches page", resumes)
    def settings():
        pg.goto(BASE + "/settings"); pg.wait_for_selector("text=Audit log"); pg.wait_for_selector("text=score.manual_override")
    step("settings & audit log shows override", settings)
    def jobedit():
        pg.goto(BASE + "/jobs/new"); pg.fill("#t", "Browser Test Dev")
        pg.fill("#d", "Job Title: Browser Test Dev\nRequirements:\n- Python and Docker\n- 2+ years of experience\nNice to have:\n- Redis\n")
        pg.click("text=Analyse requirements"); pg.wait_for_selector("text=Extracted requirements")
        pg.select_option("select[aria-label='Importance of Redis']", "must"); pg.click("text=Save job"); pg.wait_for_url("**/jobs")
        pg.wait_for_selector("text=Browser Test Dev")
    step("create job with requirement editor", jobedit)
    b.close()
for n, s, d in log: print(f"{s:5} {n} {d}")
print("CONSOLE:", json.dumps(errors, indent=1)[:2500])
print("HTTP>=400:", json.dumps(failed)[:1500])
