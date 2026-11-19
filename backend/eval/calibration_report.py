"""Score distribution by relevance grade on the SYNTHETIC benchmark (6 JDs x 35 resumes), plus semantic saturation.
Every number is computed from an actual run. Usage (from backend/):  python eval/calibration_report.py [--backend tfidf|minilm]"""
import argparse
import json
import os
import statistics as st
import sys
import tempfile
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
import logging  # noqa: E402

logging.disable(logging.INFO)
ap = argparse.ArgumentParser()
ap.add_argument("--backend", default="minilm")
args = ap.parse_args()
tmp = tempfile.mkdtemp(prefix="talentiq_cal_")
os.environ.update(DATABASE_URL=f"sqlite:///{tmp}/cal.db", UPLOAD_DIR=f"{tmp}/uploads", EMBEDDING_BACKEND=args.backend)
os.environ.pop("API_KEY", None)
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
SAMPLES = HERE.parents[1] / "sample_data"
GT = json.loads((SAMPLES / "ground_truth" / "ground_truth.json").read_text())

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


def pct(v: list[float], p: float) -> float:
    """p-th percentile (nearest rank)."""
    v = sorted(v)
    return v[min(len(v) - 1, int(p / 100 * len(v)))]


with TestClient(app) as c:
    files = sorted((SAMPLES / "resumes").iterdir())
    up = c.post("/api/resumes/upload", files=[("files", (f.name, f.read_bytes(), "application/octet-stream")) for f in files]).json()
    file_of = {r["candidate_id"]: r["filename"] for r in up["results"] if r.get("candidate_id")}
    grade = {r["file"]: r["relevance"] for r in GT["resumes"] if r.get("relevance")}
    by_grade: dict[int, list[float]] = {}
    sem_all: list[float] = []
    doc_cos: list[tuple[int, float]] = []
    musts: list[tuple[float, float]] = []          # (must-have coverage %, overall)
    ordered = total_pairs = 0
    for key in GT["job_descriptions"]:
        text = (SAMPLES / "job_descriptions" / f"{key}.txt").read_text()
        title = next(ln.split(":", 1)[1].strip() for ln in text.splitlines() if ln.lower().startswith("job title:"))
        job = c.post("/api/jobs", json={"title": title, "description": text}).json()
        c.post(f"/api/matching/run/{job['id']}", json={})
        res = c.get(f"/api/matching/results/{job['id']}", params={"page_size": 100}).json()["items"]
        graded = []
        for r in res:
            g = grade.get(file_of.get(r["candidate_id"]), {}).get(key)
            if g is None:
                continue
            by_grade.setdefault(g, []).append(r["overall"])
            graded.append((g, r["overall"]))
            s = r["components"]["semantic_relevance"]["score"]
            if s is not None:
                sem_all.append(s)
            det = c.get(f"/api/matching/candidate/{r['candidate_id']}", params={"job_id": job["id"]}).json()["result"]["semantic"]
            doc_cos.append((g, det["doc_similarity"]))
            musts.append((c.get(f"/api/matching/candidate/{r['candidate_id']}", params={"job_id": job["id"]}).json()["result"]["must_have_coverage"], r["overall"]))
        for i, (g1, s1) in enumerate(graded):
            for g2, s2 in graded[i + 1:]:
                if g1 != g2:
                    total_pairs += 1
                    ordered += (s1 > s2) == (g1 > g2) and s1 != s2
    print(f"backend={args.backend}  pairs={sum(len(v) for v in by_grade.values())}")
    print("grade |  n | median | p10 | p90 |  min |  max   (overall score)")
    for g in sorted(by_grade, reverse=True):
        v = by_grade[g]
        print(f"  {g}   | {len(v):2d} | {st.median(v):6.1f} | {pct(v, 10):3.0f} | {pct(v, 90):3.0f} | {min(v):4.0f} | {max(v):5.0f}")
    print(f"semantic component: saturated at 100 for {sum(x >= 99.5 for x in sem_all)} of {len(sem_all)} pairs; "
          f"distinct values above 90: {len({round(x, 1) for x in sem_all if x > 90})}")
    d_sat = sum(1 for _, x in doc_cos if x >= 0.75)
    print(f"raw doc cosine >= 0.75 (the OLD upper anchor): {d_sat} of {len(doc_cos)} pairs; max {max(x for _, x in doc_cos):.3f}")
    hi = [s for m, s in musts if m >= 75]
    lo = [s for m, s in musts if m <= 25]
    print(f"pairs with >=75% must-haves directly evidenced: {len(hi)}; scoring >= 80: {sum(s >= 80 for s in hi)}; median {st.median(hi):.1f}")
    print(f"pairs with <=25% must-haves directly evidenced: {len(lo)}; scoring < 40: {sum(s < 40 for s in lo)}")
    print(f"pairs ordered correctly against the author grades (within each JD, different grades): {ordered} of {total_pairs} = {100 * ordered / total_pairs:.1f} %")
