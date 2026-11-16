import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_twin_resumes_score_identically(client, loaded):
    j = loaded["jobs"]["ai_ml_engineer"]["id"]
    client.post(f"/api/matching/run/{j}", json={})
    items = client.get(f"/api/matching/results/{j}?page_size=100").json()["items"]
    a = next(i for i in items if "Karan" in i["name"])
    b = next(i for i in items if "Kavita" in i["name"])
    assert a["overall"] == b["overall"]


def test_protected_attributes_not_stored(client, loaded):
    from app.core.database import SessionLocal
    from app.models import db as M
    s = SessionLocal()
    for r in s.query(M.Resume).filter(M.Resume.raw_text.isnot(None)).all():
        low = r.raw_text.lower()
        for w in ("date of birth", "marital status", "religion", "nationality"):
            assert w not in low


def test_no_gendered_or_demographic_features_in_explanations(client, loaded):
    j = loaded["jobs"]["ai_ml_engineer"]["id"]
    it = client.get(f"/api/matching/results/{j}?page_size=1").json()["items"][0]
    d = client.get(f"/api/matching/candidate/{it['candidate_id']}?job_id={j}").json()
    blob = json.dumps(d["result"]["explanation"]).lower()
    import re
    for w in ("gender", "age", "religion", "married", "nationality"):
        assert not re.search(rf"\b{w}\b", blob)


def test_evaluation_regression():
    """Re-run the synthetic benchmark; guards against silent accuracy regressions (floors, not claims)."""
    import glob, shutil, subprocess, sys
    latest = ROOT / "backend/eval/results/latest.json"
    backup = latest.read_bytes() if latest.exists() else None
    out = subprocess.run([sys.executable, "eval/run_evaluation.py", "--backend", "tfidf", "--tag", "pytest"],
                         cwd=ROOT / "backend", capture_output=True, text=True, timeout=600)
    for f in glob.glob(str(ROOT / "backend/eval/results/evaluation_*_pytest*")):
        pass                                   # keep until read below
    if backup is not None:
        latest.write_bytes(backup)             # do not clobber the recorded final results
    assert out.returncode == 0, out.stderr[-800:]
    res = json.loads(Path(sorted(glob.glob(str(ROOT / "backend/eval/results/evaluation_*_pytest.json")))[-1]).read_text())
    assert res["skill_extraction"]["micro_f1"] >= 0.95
    assert res["ranking"]["mean_ndcg@5"] > res["ranking"]["baseline_tfidf_mean_ndcg@5"] - 0.02
    assert res["fairness_twin_test"]["max_score_difference_across_6_jds"] == 0
    assert res["score_calculation"]["recomputed_matches_stored"] == res["score_calculation"]["results_checked"]
    for f in glob.glob(str(ROOT / "backend/eval/results/evaluation_*_pytest*")):
        Path(f).unlink()
