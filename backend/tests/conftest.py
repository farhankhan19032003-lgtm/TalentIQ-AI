import os
import sys
import tempfile
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
_TMP = tempfile.mkdtemp(prefix="talentiq_test_")
# SQLite by default. To run the same suite on PostgreSQL set TEST_DATABASE_URL to an EMPTY database
# (e.g. postgresql+psycopg://user:pw@127.0.0.1:5433/talentiq_test); the suite creates tables and fills it with synthetic data.
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{_TMP}/test.db"
os.environ["UPLOAD_DIR"] = f"{_TMP}/uploads"
os.environ["EMBEDDING_BACKEND"] = "tfidf"       # deterministic & offline for tests (MiniLM is exercised separately if installed)
os.environ.pop("API_KEY", None)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / "sample_data"


@pytest.fixture(scope="session")
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def jd_text():
    return {p.stem: p.read_text(encoding="utf-8") for p in (SAMPLES / "job_descriptions").glob("*.txt")}


@pytest.fixture(scope="session")
def loaded(client, jd_text):
    """Uploads the full synthetic batch once and creates all six jobs."""
    files = sorted((SAMPLES / "resumes").iterdir())
    payload = [("files", (f.name, f.read_bytes(), "application/octet-stream")) for f in files]
    r = client.post("/api/resumes/upload", files=payload)
    assert r.status_code == 200, r.text
    jobs = {}
    for k, t in jd_text.items():
        j = client.post("/api/jobs", json={"title": k.replace("_", " ").title(), "description": t})
        assert j.status_code == 201, j.text
        jobs[k] = j.json()
    return {"upload": r.json(), "jobs": jobs}
