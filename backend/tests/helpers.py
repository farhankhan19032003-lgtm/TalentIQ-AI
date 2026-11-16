import io
from pathlib import Path

SAMPLES = Path(__file__).resolve().parents[2] / "sample_data"
RES = SAMPLES / "resumes"


def make_pdf(lines: list[str]) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate
    buf = io.BytesIO()
    st = getSampleStyleSheet()["Normal"]
    SimpleDocTemplate(buf, pagesize=A4).build([Paragraph(l.replace("&", "&amp;"), st) for l in lines])
    return buf.getvalue()


def make_docx(lines: list[str]) -> bytes:
    from docx import Document
    d = Document()
    for l in lines:
        d.add_paragraph(l)
    b = io.BytesIO()
    d.save(b)
    return b.getvalue()


def simple_resume(name="Test Person", email=None, skills="Python, SQL, Docker", extra=None):
    email = email or f"{name.lower().replace(' ', '.')}@example.com"
    return [name, f"{email} | +91 90000 99999 | Pune, India", "Summary", "Backend developer with experience building services.",
            "Experience", "Python Developer | Acme Labs | Jan 2020 – Dec 2022", "• Built REST APIs using Python and Docker",
            "Education", "B.Tech in Computer Science | Sunrise Institute of Technology | 2016 – 2020", "Skills", skills] + (extra or [])
