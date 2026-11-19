"""The same sample JD pasted, uploaded as TXT, DOCX and PDF must give the same skills, minimum years and qualification."""
from conftest import SAMPLES

JD_DIR = SAMPLES / "job_descriptions"


def _signature(a: dict) -> dict:
    return {"requirements": sorted((r["name"], r["importance"]) for r in a["requirements"]),
            "experience": a["experience"], "education": a["education"]}


def _uploaded(client, name: str) -> dict:
    f = JD_DIR / name
    r = client.post("/api/jobs/extract-text", files={"file": (name, f.read_bytes(), "application/octet-stream")})
    assert r.status_code == 200, r.text
    return r.json()["analysis"]


def test_paste_txt_docx_pdf_give_identical_extraction(client):
    pasted = client.post("/api/jobs/analyze", json={"description": (JD_DIR / "python_backend_developer.txt").read_text(encoding="utf-8")}).json()
    base = _signature(pasted)
    assert len(base["requirements"]) == 12
    for name in ("python_backend_developer.txt", "python_backend_developer.docx", "python_backend_developer.pdf"):
        assert _signature(_uploaded(client, name)) == base, name


def test_sample_jd_states_years_and_degree(client):
    a = client.post("/api/jobs/analyze", json={"description": (JD_DIR / "python_backend_developer.txt").read_text(encoding="utf-8")}).json()
    assert "3" in str(a["experience"]) and a["education"]
