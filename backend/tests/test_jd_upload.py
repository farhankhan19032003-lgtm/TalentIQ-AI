"""Module 1: a job description can be pasted or uploaded as .txt, .docx or .pdf and yields the same extracted requirements."""
import io

import pytest
from docx import Document
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from tests.conftest import SAMPLES

JD = """Job Title: Senior Java Backend Developer
Company: Example Corp (fictional)

Responsibilities:
- Design and build scalable microservices using Java and Spring Boot
- Develop REST APIs and integrate with SQL databases

Requirements:
- 5+ years of professional experience in Java development
- Strong knowledge of Spring Boot and REST APIs
- Solid SQL skills (PostgreSQL or MySQL)
- Experience with Docker and Git
- Bachelor's degree in Computer Science or equivalent

Good to have:
- Kubernetes and AWS
"""
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def make_docx(text=JD) -> bytes:
    d = Document()
    for line in text.splitlines():
        d.add_paragraph(line)
    b = io.BytesIO()
    d.save(b)
    return b.getvalue()


def make_pdf(text=JD) -> bytes:
    b = io.BytesIO()
    c = canvas.Canvas(b, pagesize=A4)
    y = 800
    for line in text.splitlines():
        if y < 40:                                   # new page instead of drawing below the sheet
            c.showPage()
            y = 800
        c.drawString(40, y, line)
        y -= 15
    c.save()
    return b.getvalue()


def upload(client, name, data, mime="application/octet-stream"):
    return client.post("/api/jobs/extract-text", files={"file": (name, data, mime)})


def summary(analysis):
    must = sorted(r["name"] for r in analysis["requirements"] if r["importance"] == "must")
    pref = sorted(r["name"] for r in analysis["requirements"] if r["importance"] == "preferred")
    return must, pref, analysis["experience"]["min_years"], analysis["education"]["required_label"]


def test_pasted_jd_is_analysed(client):
    a = client.post("/api/jobs/analyze", json={"title": "", "description": JD}).json()
    must, pref, years, edu = summary(a)
    assert {"Java", "Spring Boot", "REST APIs", "SQL", "Docker", "Git"} <= set(must)
    assert {"Kubernetes", "AWS"} <= set(pref) and "Kubernetes" not in must
    assert years == 5.0 and edu == "Bachelor's"
    assert a["title"] == "Senior Java Backend Developer"


@pytest.mark.parametrize("name,data,mime", [("jd.txt", JD.encode(), "text/plain"), ("jd.docx", make_docx(), DOCX_MIME), ("jd.pdf", make_pdf(), "application/pdf")])
def test_uploaded_jd_in_every_format_gives_the_same_analysis(client, name, data, mime):
    r = upload(client, name, data, mime)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "Spring Boot" in body["text"] and body["filename"] == name
    pasted = summary(client.post("/api/jobs/analyze", json={"title": "", "description": JD}).json())
    assert summary(body["analysis"]) == pasted, f"{name} must yield the same requirements as pasting the text"


def test_multi_page_pdf_jd_is_read_completely_and_in_order(client):
    long_jd = "\n".join(f"- Responsibility number {i} for the backend team" for i in range(80)) + "\n" + JD
    data = make_pdf(long_jd)
    import pymupdf
    assert len(pymupdf.open(stream=data, filetype="pdf")) >= 2, "the test PDF really has several pages"
    r = upload(client, "long.pdf", data, "application/pdf")
    assert r.status_code == 200
    text = r.json()["text"]
    assert "Responsibility number 0 " in text and "Responsibility number 79" in text and "Spring Boot" in text
    assert text.index("Responsibility number 0 ") < text.index("Responsibility number 79") < text.index("Spring Boot"), "page order is kept"
    must = summary(r.json()["analysis"])[0]
    assert "Spring Boot" in must and "Java" in must


def test_unsupported_and_mislabelled_files_are_refused_with_a_clear_message(client):
    r = upload(client, "jd.exe", b"MZ" + b"0" * 100)
    assert r.status_code == 400 and r.json()["error"]["code"] == "unsupported_type" and ".pdf" in r.json()["error"]["message"]
    fake = upload(client, "jd.pdf", b"this is plain text pretending to be a PDF")
    assert fake.status_code == 400 and fake.json()["error"]["code"] == "invalid_document"
    fake_docx = upload(client, "jd.docx", b"%PDF-1.4 not a docx")
    assert fake_docx.status_code == 400


def test_corrupt_encrypted_and_scanned_pdfs_are_rejected_not_crashed(client):
    for name in ("corrupted_resume.pdf", "password_protected_resume.pdf"):
        r = upload(client, name, (SAMPLES / "resumes" / name).read_bytes(), "application/pdf")
        assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_document", name
        assert r.json()["error"]["message"], "a human-readable reason is returned"


def test_oversized_jd_file_is_refused(client):
    r = upload(client, "big.pdf", b"%PDF-" + b"0" * (2 * 1024 * 1024 + 10), "application/pdf")
    assert r.status_code == 413 and r.json()["error"]["code"] == "file_too_large"


def test_a_saved_job_from_an_uploaded_pdf_ranks_candidates(client, loaded):
    """End to end: upload the PDF JD, save it as a job, run matching: every candidate gets a 0-100 score and skill lists."""
    ex = upload(client, "jd.pdf", make_pdf(), "application/pdf").json()
    job = client.post("/api/jobs", json={"title": ex["analysis"]["title"], "description": ex["text"]})
    assert job.status_code == 201, job.text
    jid = job.json()["id"]
    try:
        assert client.post(f"/api/matching/run/{jid}", json={}).status_code == 201
        items = client.get(f"/api/matching/results/{jid}?page_size=100").json()["items"]
        assert len(items) >= 30
        assert all(0 <= i["overall"] <= 100 and isinstance(i["matched_skills"], list) and isinstance(i["missing_skills"], list) for i in items)
        assert [i["rank"] for i in items] == list(range(1, len(items) + 1))
    finally:
        client.delete(f"/api/jobs/{jid}")
