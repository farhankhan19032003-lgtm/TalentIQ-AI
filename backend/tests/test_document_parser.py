import shutil

import pytest

from app.core.config import settings
from app.services.document_parser import DocumentError, normalize_text, parse_document, parse_pdf, text_quality
from helpers import RES, make_pdf


def test_pdf_single_column():
    d = parse_pdf((RES / "anika_menon.pdf").read_bytes())
    assert d.file_type == "pdf" and d.pages[0].columns == 1
    assert "Anika Menon" in d.text and "Machine Learning" in d.text
    assert d.quality > 0.8


def test_pdf_two_column_reading_order():
    d = parse_pdf((RES / "isha_rao.pdf").read_bytes())
    assert d.pages[0].columns == 2
    t = d.text
    # name first (header), and each column's content stays together instead of interleaving rows
    assert t.index("Isha Rao") < t.index("Education")
    i = t.index("Work Experience")
    assert t.index("Data Scientist, Helio Payments") > i
    assert t.index("Junior Analyst") > t.index("Data Scientist, Helio Payments")
    assert "Languages: Python, SQL" in t


def test_pdf_page_diagnostics():
    d = parse_pdf((RES / "anika_menon.pdf").read_bytes())
    diag = d.pages[0].diag()
    assert set(diag) >= {"page", "chars", "method", "columns", "quality", "scanned", "warnings"}


def test_docx_headings_and_bullets():
    d = parse_document((RES / "rohan_varma.docx").read_bytes(), "docx")
    assert "• Trained TensorFlow and Keras" in d.text
    assert "Machine Learning Engineer" in d.text


def test_docx_layout_table_read_column_wise():
    d = parse_document((RES / "rahul_menon.docx").read_bytes(), "docx")
    t = d.text
    # left cell (Skills/Education) is contiguous, then right cell (Summary/Experience)
    assert t.index("Core: Java") < t.index("Java Developer | Pinecrest Finserv") or t.index("Education") < t.index("Experience")
    assert "Spring Boot" in t and "Hibernate" in t


def test_docx_data_table_rows():
    from docx import Document
    import io
    d = Document()
    d.add_paragraph("Jane Roe")
    t = d.add_table(rows=2, cols=2)
    t.rows[0].cells[0].text, t.rows[0].cells[1].text = "Python", "Advanced"
    t.rows[1].cells[0].text, t.rows[1].cells[1].text = "SQL", "Intermediate"
    d.add_paragraph("Experience across several backend systems and analytics projects in production.")
    b = io.BytesIO(); d.save(b)
    assert "Python | Advanced" in parse_document(b.getvalue(), "docx").text


def test_encrypted_pdf_detected():
    with pytest.raises(DocumentError) as e:
        parse_pdf((RES / "password_protected_resume.pdf").read_bytes())
    assert e.value.code == "password_protected"


def test_corrupted_pdf_reports_corrupt():
    with pytest.raises(DocumentError) as e:
        parse_pdf((RES / "corrupted_resume.pdf").read_bytes())
    assert e.value.code in ("corrupt", "no_text")


def test_truncated_pdf_does_not_crash():
    data = (RES / "anika_menon.pdf").read_bytes()
    try:
        d = parse_pdf(data[: len(data) // 2])
        assert isinstance(d.text, str)
    except DocumentError as e:
        assert e.code in ("corrupt", "no_text")


def test_corrupted_docx():
    with pytest.raises(DocumentError) as e:
        parse_document((RES / "corrupted_resume.docx").read_bytes(), "docx")
    assert e.value.code == "corrupt"


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="Tesseract not installed")
def test_scanned_pdf_uses_ocr():
    d = parse_pdf((RES / "scanned_resume_image_only.pdf").read_bytes())
    assert d.ocr_used and d.pages[0].scanned and d.pages[0].method == "tesseract_ocr"
    assert "Ritu Sharma" in d.text and "ocr_used" in d.warnings
    assert d.quality < 1.0  # OCR text is penalised


def test_scanned_pdf_without_ocr_is_reported_not_silent(monkeypatch):
    monkeypatch.setattr(settings, "ocr_enabled", False)
    with pytest.raises(DocumentError) as e:
        parse_pdf((RES / "scanned_resume_image_only.pdf").read_bytes())
    assert e.value.code == "scanned_no_ocr"


def test_empty_text_pdf_rejected():
    with pytest.raises(DocumentError):
        parse_pdf(make_pdf(["x"]))


def test_normalize_text_unicode_and_bullets():
    out = normalize_text("ﬁnal​ report\n▪ item one\n● item two\n- item three x")
    assert "final report" in out
    assert out.count("• ") == 3
    assert "​" not in out


def test_text_quality_bounds():
    assert text_quality("") == 0.0
    assert 0.0 <= text_quality("��� garbage") < 0.5
    assert text_quality("A normal sentence about software engineering and data.") > 0.8
