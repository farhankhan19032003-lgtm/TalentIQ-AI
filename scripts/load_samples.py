"""Load the fictional sample data (sample_data/) into a RUNNING TalentIQ instance through its public API.

    python scripts/load_samples.py                        # http://localhost:8080 (Docker) , all 6 JDs + all resumes
    python scripts/load_samples.py --base http://localhost:8000 --jd python_backend_developer --no-bad-files
    python scripts/load_samples.py --run                  # also run matching for every job it created
    python scripts/load_samples.py --demo --run           # the curated 3-minute demo: 1 JD, 15 resumes, 3 edge cases

Standard library only. All people in sample_data/ are fictional; the folder also contains deliberately bad files
(corrupt, password-protected, fake extension) to show the error handling - skip them with --no-bad-files.
"""
import argparse, json, mimetypes, sys, urllib.request, uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "sample_data"
BAD = ("corrupted", "password_protected", "fake_extension", "resume_notes")


def call(base, path, data=None, headers=None, method=None):
    req = urllib.request.Request(base + path, data=data, headers=headers or {}, method=method)
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.load(r)


def post_json(base, path, obj):
    return call(base, path, json.dumps(obj).encode(), {"content-type": "application/json"}, "POST")


def upload(base, files):
    b = uuid.uuid4().hex
    body = b""
    for f in files:
        ct = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
        body += (f'--{b}\r\nContent-Disposition: form-data; name="files"; filename="{f.name}"\r\nContent-Type: {ct}\r\n\r\n').encode() + f.read_bytes() + b"\r\n"
    body += f"--{b}--\r\n".encode()
    return call(base, "/api/resumes/upload", body, {"content-type": f"multipart/form-data; boundary={b}"}, "POST")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default="http://localhost:8080", help="server root (frontend/nginx in Docker, or the backend on :8000)")
    ap.add_argument("--jd", action="append", help="JD file stem to load (repeatable); default: all .txt JDs")
    ap.add_argument("--no-bad-files", action="store_true", help="skip the corrupt / password-protected / fake-extension files")
    ap.add_argument("--run", action="store_true", help="run matching for each created job")
    ap.add_argument("--demo", action="store_true", help="load only the curated demo set listed in sample_data/demo_set.json")
    a = ap.parse_args()

    jds = sorted((ROOT / "job_descriptions").glob("*.txt"))
    if a.jd:
        jds = [p for p in jds if p.stem in a.jd]
    resumes = sorted(p for p in (ROOT / "resumes").iterdir() if p.suffix in (".pdf", ".docx"))
    if a.demo:
        demo = json.loads((ROOT / "demo_set.json").read_text(encoding="utf-8"))
        jds = [ROOT / demo["job_description"]]
        resumes = [ROOT / "resumes" / n for n in demo["resumes"] + demo["edge_cases"]]
    elif a.no_bad_files:
        resumes = [p for p in resumes if not p.stem.startswith(BAD)]

    job_ids = []
    for p in jds:
        text = p.read_text(encoding="utf-8")
        analysis = post_json(a.base, "/api/jobs/analyze", {"description": text})
        job = post_json(a.base, "/api/jobs", {**analysis, "description": text})
        job_ids.append(job["id"])
        print(f"job {job['id']}: {job['title']}")
    res = upload(a.base, resumes)
    print("upload:", res["summary"], f"({res['total']} files)")
    for r in res["results"]:
        if r["status"] != "parsed":
            print(f"  {r['status']:9} {r['filename']}")
    if a.run:
        for j in job_ids:
            run = post_json(a.base, f"/api/matching/run/{j}", {})
            print(f"matched job {j}: {run['n_candidates']} candidates, {run['similarity_method']}, {run['duration_ms']} ms")
    print(f"open {a.base}  (no data is loaded unless you run this script; the UI itself ships empty)")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.URLError as e:
        sys.exit(f"cannot reach the server: {e}")
