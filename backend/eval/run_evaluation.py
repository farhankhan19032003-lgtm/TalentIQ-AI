"""Scientific evaluation on the SYNTHETIC benchmark. Every number is computed from an actual run; nothing is hard-coded.
Usage (PowerShell, from backend/):  python eval/run_evaluation.py [--backend tfidf|auto|minilm]"""
import argparse
import csv
import json
import math
import os
import sys
import tempfile
import time
import warnings
from datetime import date, datetime
from pathlib import Path

warnings.filterwarnings("ignore")
ap = argparse.ArgumentParser()
ap.add_argument("--backend", default=os.environ.get("EMBEDDING_BACKEND", "tfidf"))
ap.add_argument("--tag", default="")
args = ap.parse_args()
tmp = tempfile.mkdtemp(prefix="talentiq_eval_")
os.environ.update(DATABASE_URL=f"sqlite:///{tmp}/eval.db", UPLOAD_DIR=f"{tmp}/uploads", EMBEDDING_BACKEND=args.backend)
os.environ.pop("API_KEY", None)
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
ROOT = HERE.parents[1]

import numpy as np  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sklearn.feature_extraction.text import TfidfVectorizer  # noqa: E402

from app.core.config import ALGORITHM_VERSION, COMPONENTS, SCORING  # noqa: E402
from app.main import app  # noqa: E402
from app.services import pipeline  # noqa: E402
from app.services.experience_analyzer import analyze_experience  # noqa: E402

GT = json.loads((ROOT / "sample_data/ground_truth/ground_truth.json").read_text())
AS_OF = date.fromisoformat(GT["as_of"])
SAMPLES = ROOT / "sample_data"


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return p, r, (2 * p * r / (p + r) if p + r else 0.0)


def dcg(grades):
    return sum(g / math.log2(i + 2) for i, g in enumerate(grades))


def ndcg_at(ranked_grades, all_grades, k=5):
    ideal = sorted(all_grades, reverse=True)[:k]
    return dcg(ranked_grades[:k]) / dcg(ideal) if dcg(ideal) > 0 else None


def main():
    out = {"dataset_version": GT["dataset_version"], "algorithm_version": ALGORITHM_VERSION, "ontology_version": pipeline.ontology.version,
           "evaluation_date": datetime.utcnow().isoformat(timespec="seconds") + "Z", "as_of_date": GT["as_of"], "label_provenance": GT["label_provenance"],
           "tag": args.tag}
    with TestClient(app) as c:
        files = sorted((SAMPLES / "resumes").iterdir())
        t0 = time.time()
        up = c.post("/api/resumes/upload", files=[("files", (f.name, f.read_bytes(), "application/octet-stream")) for f in files]).json()
        out["batch_upload_seconds"] = round(time.time() - t0, 2)
        status = {r["filename"]: r for r in up["results"]}
        # ---------------- batch reliability & parsing
        exp_parsed = [r for r in GT["resumes"] if r["expects"] == "parsed"]
        ocr = [r for r in GT["resumes"] if r["expects"] == "ocr_dependent"]
        fail_exp = [r for r in GT["resumes"] if r["expects"] in ("failed", "rejected", "duplicate")]
        ok_parsed = sum(status[r["file"]]["status"] == "parsed" for r in exp_parsed)
        right_fail = sum(status[r["file"]]["status"] == r["expects"] and (r.get("error_code") is None or status[r["file"]]["error_code"] in (r["error_code"], "duplicate_file")) for r in fail_exp)
        out["parsing"] = {"files_in_batch": len(files), "expected_parseable": len(exp_parsed), "parsed_ok": ok_parsed,
                          "parse_success_rate": round(ok_parsed / len(exp_parsed), 4),
                          "failure_cases_expected": len(fail_exp), "failure_cases_classified_correctly": right_fail,
                          "ocr_dependent_files": [{"file": r["file"], "status": status[r["file"]]["status"]} for r in ocr],
                          "batch_completed_without_crash": up["total"] == len(files), "http_summary": up["summary"]}
        # ---------------- skill / field / experience extraction
        by_file = {}
        for f, r in status.items():
            if r.get("candidate_id"):
                by_file[f] = r["candidate_id"]
        from app.core.database import SessionLocal
        from app.models import db as M
        s = SessionLocal()
        tp = fp = fn = 0
        ttp = tfp = tfn = 0
        per = []
        nm_ok = em_ok = n_f = 0
        exp_ok = n_ok = n_e = 0
        errs = []
        for r in GT["resumes"]:
            if r["expects"] not in ("parsed", "ocr_dependent") or r["file"] not in by_file:
                continue
            cand = s.get(M.Candidate, by_file[r["file"]])
            got = set(cand.parsed["skills"])
            exp = set(r["skills"])
            tech = lambda S: {k for k in S if pipeline.ontology.category(k) != "Soft Skills"}
            a, b_, c_ = len(got & exp), len(got - exp), len(exp - got)
            tp, fp, fn = tp + a, fp + b_, fn + c_
            ta, tb, tc = len(tech(got) & tech(exp)), len(tech(got) - tech(exp)), len(tech(exp) - tech(got))
            ttp, tfp, tfn = ttp + ta, tfp + tb, tfn + tc
            p_, r_, f_ = prf(a, b_, c_)
            per.append({"file": r["file"], "tp": a, "fp": b_, "fn": c_, "precision": round(p_, 3), "recall": round(r_, 3), "f1": round(f_, 3),
                        "false_positives": sorted(got - exp), "false_negatives": sorted(exp - got)})
            n_f += 1
            nm_ok += (cand.name == r["name"])
            em_ok += (cand.email == r["email"])
            e = analyze_experience(cand.parsed["employment"], {"experience": {}}, set(), AS_OF, None)
            n_e += 1
            exp_ok += abs(e["total_effective_years"] - r["experience"]["effective_years"]) <= 0.1
            n_ok += len(cand.parsed["employment"]) == r["experience"]["n_employment"]
            if abs(e["total_effective_years"] - r["experience"]["effective_years"]) > 0.1:
                errs.append({"file": r["file"], "expected_years": r["experience"]["effective_years"], "got_years": e["total_effective_years"]})
        P, R, F = prf(tp, fp, fn)
        TP, TR, TF = prf(ttp, tfp, tfn)
        macro_f1 = sum(x["f1"] for x in per) / len(per)
        out["skill_extraction"] = {"resumes_evaluated": len(per), "micro_precision": round(P, 4), "micro_recall": round(R, 4), "micro_f1": round(F, 4),
                                   "macro_f1": round(macro_f1, 4), "technical_only_micro_precision": round(TP, 4), "technical_only_micro_recall": round(TR, 4),
                                   "technical_only_micro_f1": round(TF, 4), "total_tp": tp, "total_fp": fp, "total_fn": fn}
        out["field_extraction"] = {"name_accuracy": round(nm_ok / n_f, 4), "email_accuracy": round(em_ok / n_f, 4), "n": n_f}
        out["experience_extraction"] = {"effective_years_within_0.1y_accuracy": round(exp_ok / n_e, 4), "employment_count_accuracy": round(n_ok / n_e, 4), "n": n_e, "mismatches": errs}
        # ---------------- JD extraction
        jd_res = []
        jobs = {}
        for key, truth in GT["job_descriptions"].items():
            text = (SAMPLES / "job_descriptions" / f"{key}.txt").read_text()
            real_title = next(l.split(":", 1)[1].strip() for l in text.splitlines() if l.lower().startswith("job title:"))
            j = c.post("/api/jobs", json={"title": real_title, "description": text}).json()
            jobs[key] = j
            gm = {r["name"] for r in j["requirements"] if r["importance"] == "must"}
            gp = {r["name"] for r in j["requirements"] if r["importance"] == "preferred"}
            em, ep = set(truth["must"]), set(truth["preferred"])
            allg, alle = gm | gp, em | ep
            p_, r_, f_ = prf(len(allg & alle), len(allg - alle), len(alle - allg))
            jd_res.append({"jd": key, "skill_f1": round(f_, 3), "precision": round(p_, 3), "recall": round(r_, 3),
                           "must_correct": len(gm & em), "must_expected": len(em), "importance_correct": len((gm & em) | (gp & ep)), "importance_total": len(alle),
                           "extra": sorted(allg - alle), "missing": sorted(alle - allg),
                           "min_years_ok": j["min_experience_years"] == truth["min_years"], "education_ok": j["education_level"] == truth["education_level"]})
        out["jd_extraction"] = {"per_jd": jd_res, "mean_skill_f1": round(sum(x["skill_f1"] for x in jd_res) / len(jd_res), 4),
                                "importance_accuracy": round(sum(x["importance_correct"] for x in jd_res) / sum(x["importance_total"] for x in jd_res), 4),
                                "experience_requirement_accuracy": round(sum(x["min_years_ok"] for x in jd_res) / len(jd_res), 4),
                                "education_requirement_accuracy": round(sum(x["education_ok"] for x in jd_res) / len(jd_res), 4)}
        # ---------------- ranking quality, baseline, score correctness
        file_of = {cid: f for f, cid in by_file.items()}
        grade = {r["file"]: r["relevance"] for r in GT["resumes"] if r.get("relevance")}
        rank_rows, corr_ok, corr_n, weight_ok = [], 0, 0, True
        sens_stable = sens_n = 0
        texts = {f: (s.get(M.Candidate, cid).resume.raw_text or "") for f, cid in by_file.items() if f in grade}
        for key, j in jobs.items():
            t0 = time.time()
            run = c.post(f"/api/matching/run/{j['id']}", json={}).json()
            dur = time.time() - t0
            res = c.get(f"/api/matching/results/{j['id']}?page_size=100").json()
            ranked = [file_of[it["candidate_id"]] for it in res["items"]]
            graded = [f for f in ranked if f in grade]
            gl = [grade[f][key] for f in graded]
            n5 = ndcg_at(gl, gl, 5)
            relevant_total = sum(1 for g in gl if g >= 2)
            p5 = sum(1 for g in gl[:5] if g >= 2) / 5
            r5 = (sum(1 for g in gl[:5] if g >= 2) / relevant_total) if relevant_total else None
            r5_max = min(5, relevant_total) / relevant_total if relevant_total else None
            # baseline: TF-IDF cosine over whole resume text vs JD text
            vec = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, stop_words="english").fit([j["description"]] + list(texts.values()))
            sims = (vec.transform([texts[f] for f in graded]) @ vec.transform([j["description"]]).T).toarray().ravel()
            bl = [grade[f][key] for f in [graded[i] for i in np.argsort(-sims, kind="stable")]]
            rng = np.random.default_rng(0)
            rand_ndcg = float(np.mean([ndcg_at(list(rng.permutation(gl)), gl, 5) for _ in range(500)]))
            rank_rows.append({"jd": key, "n_graded": len(gl), "relevant_total": relevant_total, "ndcg@5": round(n5, 4), "precision@5": round(p5, 4),
                              "recall@5": None if r5 is None else round(r5, 4), "max_possible_recall@5": None if r5_max is None else round(r5_max, 4),
                              "baseline_tfidf_ndcg@5": round(ndcg_at(bl, gl, 5), 4), "baseline_tfidf_precision@5": round(sum(1 for g in bl[:5] if g >= 2) / 5, 4),
                              "random_ndcg@5_mean": round(rand_ndcg, 4), "match_seconds": round(dur, 2), "top5": [f for f in graded[:5]],
                              "top5_grades": gl[:5]})
            # score calculation correctness (independent recomputation from stored components)
            for it in res["items"]:
                comps = it["components"]
                skip = set(SCORING["renormalise_unverified"])   # unverified low-stakes components are left out of the point estimate
                active = {k: v for k, v in comps.items() if v["status"] != "not_required" and not (v["status"] == "unverified" and k in skip)}
                tw = sum(run["weights"][k] for k in active)
                manual = sum(run["weights"][k] / tw * (v["score"] or 0) for k, v in active.items())
                corr_n += 1
                corr_ok += abs(manual - it["overall"]) < 0.011 and 0 <= it["overall"] <= 100 and it["score_low"] <= it["overall"] <= it["score_high"] <= 100
                sens_n += 1
                sens_stable += it["sensitivity"]["stable"]
            weight_ok &= abs(sum(run["weights"].values()) - 1) < 1e-6
        mean = lambda k: round(sum(r[k] for r in rank_rows if r[k] is not None) / len([r for r in rank_rows if r[k] is not None]), 4)
        out["ranking"] = {"per_jd": rank_rows, "mean_ndcg@5": mean("ndcg@5"), "mean_precision@5": mean("precision@5"), "mean_recall@5": mean("recall@5"),
                          "mean_max_possible_recall@5": mean("max_possible_recall@5"), "baseline_tfidf_mean_ndcg@5": mean("baseline_tfidf_ndcg@5"),
                          "baseline_tfidf_mean_precision@5": mean("baseline_tfidf_precision@5"), "random_mean_ndcg@5": mean("random_ndcg@5_mean"),
                          "relevant_definition": "relevance grade >= 2 (graded 0-3 by the author)", "gain": "linear (gain = grade)",
                          "similarity_method": run["similarity_method"], "model_name": run["model_name"]}
        out["score_calculation"] = {"results_checked": corr_n, "recomputed_matches_stored": corr_ok, "weights_sum_to_one": bool(weight_ok),
                                    "rank_stable_under_10pp_weight_perturbation_share": round(sens_stable / sens_n, 4)}
        # ---------------- fairness
        fa = next(r for r in GT["resumes"] if r.get("tags") and "fairness_pair" in r["tags"] and r["name"] == "Karan Arora")
        fb = next(r for r in GT["resumes"] if r.get("tags") and "fairness_pair" in r["tags"] and r["name"] == "Kavita Arora")
        diffs = []
        for key, j in jobs.items():
            res = c.get(f"/api/matching/results/{j['id']}?page_size=100").json()
            m = {file_of[it["candidate_id"]]: it for it in res["items"]}
            diffs.append(abs(m[fa["file"]]["overall"] - m[fb["file"]]["overall"]))
        out["fairness_twin_test"] = {"pair": [fa["file"], fb["file"]], "max_score_difference_across_6_jds": max(diffs), "note": "Identical professional content; different name/gender/DOB/marital status/religion lines."}
        out["performance"] = {"mean_parse_ms_per_resume": round(float(np.mean([r["processing_ms"] for r in up["results"] if r.get("processing_ms")])), 1),
                              "max_parse_ms": max(r.get("processing_ms") or 0 for r in up["results"]), "mean_match_seconds_per_jd": mean("match_seconds")}
    out["known_limitations"] = [
        "Benchmark is synthetic and small (35 parseable resumes, 6 job descriptions); results do not predict performance on real resumes.",
        "Skill labels are defined by construction and reviewed by the author, not by independent annotators; ontology aliases were refined after viewing errors on this same set, so skill metrics are optimistic (dev set = test set).",
        "Relevance grades (0-3) are author-assigned; NDCG/precision/recall are only as valid as those grades.",
        "Fallback TF-IDF similarity was used when the MiniLM model could not be downloaded; MiniLM was not evaluated in this run." if out["ranking"]["similarity_method"] == "tfidf" else "MiniLM similarity used.",
    ]
    (HERE / "results").mkdir(exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%d")
    name = f"evaluation_{stamp}{('_' + args.tag) if args.tag else ''}"
    (HERE / "results" / f"{name}.json").write_text(json.dumps(out, indent=1))
    (HERE / "results" / "latest.json").write_text(json.dumps(out, indent=1))
    with open(HERE / "results" / f"{name}_skills_per_resume.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(per[0].keys()))
        w.writeheader()
        for r in per:
            w.writerow({**r, "false_positives": ";".join(r["false_positives"]), "false_negatives": ";".join(r["false_negatives"])})
    with open(HERE / "results" / f"{name}_ranking.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[k for k in rank_rows[0].keys() if k not in ("top5", "top5_grades")])
        w.writeheader()
        for r in rank_rows:
            w.writerow({k: v for k, v in r.items() if k not in ("top5", "top5_grades")})
    print(json.dumps({k: out[k] for k in ("parsing", "skill_extraction", "field_extraction", "experience_extraction", "score_calculation", "fairness_twin_test", "performance")}, indent=1))
    print("JD extraction:", json.dumps({k: v for k, v in out["jd_extraction"].items() if k != "per_jd"}))
    for r in out["jd_extraction"]["per_jd"]:
        print("  ", r["jd"], "extra:", r["extra"], "missing:", r["missing"], "yrs", r["min_years_ok"], "edu", r["education_ok"])
    print("RANKING", json.dumps({k: v for k, v in out["ranking"].items() if k != "per_jd"}))
    for r in rank_rows:
        print("  ", r["jd"], "ndcg", r["ndcg@5"], "p@5", r["precision@5"], "baseline ndcg", r["baseline_tfidf_ndcg@5"], "top5", r["top5"], r["top5_grades"])


main()
