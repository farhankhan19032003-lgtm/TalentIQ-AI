"""Parsing accuracy across 14 different resume layouts (fictional people only).

Each case is rendered as a real DOCX or PDF, parsed with the production parser/extractor, and checked for the fields the
ranking depends on: name, role, dated employment, experience years and education level."""
from datetime import date

import pytest

from app.services.document_parser import parse_document
from app.services.experience_analyzer import analyze_experience
from app.services.pipeline import REVIEW_REASONS, build_review, resume_extractor
from helpers import make_docx, make_pdf

AS_OF = date(2025, 1, 1)
EDU = "B.Tech in Computer Science | Sunrise Institute of Technology | 2016 – 2020"


def parse(lines, kind="docx", blob=None):
    data = blob or (make_docx(lines) if kind == "docx" else make_pdf(lines))
    doc = parse_document(data, kind)
    return resume_extractor.extract(doc), doc


def years(parsed) -> float:
    return analyze_experience(parsed["employment"], {"experience": {"min_years": 1}}, set(), AS_OF, None)["total_effective_years"]


# (id, lines, kind, expected name, expected role contains, expected total years (+-0.2), expected education level)
CASES = [
    ("month_range_present", ["Aarav Mehta", "aarav.mehta@example.com | +91 90000 11111", "Experience",
                             "Backend Engineer | Nimbus Apps | Jan 2021 – Present", "• Built APIs", "Education", EDU],
     "docx", "Aarav Mehta", "Backend Engineer", 4.0, 3),
    ("year_range_in_parentheses", ["Diya Nair", "diya.nair@example.com", "Work Experience",
                                   "Data Analyst, Brightwave Labs (2019 – 2023)", "• Built dashboards", "Education",
                                   "BSc Statistics, Meridian College, 2018"], "docx", "Diya Nair", "Data Analyst", 4.0, 3),
    ("date_on_next_line", ["Kabir Rao", "kabir.rao@example.com", "Professional Experience", "Senior Developer", "Orion Systems",
                           "Mar 2018 – Feb 2022", "• Led a team", "Education", "Master of Science in Data Science, Lakeview University, 2018"],
     "docx", "Kabir Rao", "Senior Developer", 4.0, 4),
    ("dotted_month_dates", ["Meera Iyer", "meera.iyer@example.com", "Experience", "QA Engineer | Helio Pay | 03.2020 – 05.2021",
                            "• Wrote test plans", "Education", EDU], "docx", "Meera Iyer", "QA Engineer", 1.2, 3),
    ("since_year", ["Neel Joshi", "neel.joshi@example.com", "Experience", "DevOps Engineer | Cloudlane | since Jan 2022",
                    "• Ran Kubernetes clusters", "Education", EDU], "docx", "Neel Joshi", "DevOps Engineer", 3.0, 3),
    ("two_digit_end_year", ["Pooja Sen", "pooja.sen@example.com", "Experience", "Software Engineer, Acme Labs, 2019–23",
                            "• Shipped features", "Education", EDU], "docx", "Pooja Sen", "Software Engineer", 4.0, 3),
    ("career_history_heading", ["Rohit Das", "rohit.das@example.com", "— CAREER HISTORY —", "Product Analyst | Zenith | Jun 2020 – Jun 2022",
                                "• Analysed funnels", "EDUCATION:", "MBA, Crestview Business School, 2020"], "docx", "Rohit Das", "Product Analyst", 2.0, 4),
    ("professional_background_heading", ["Sana Khan", "sana.khan@example.com", "Professional Background",
                                         "Support Engineer | Brightwave Labs | Jul 2019 – Jul 2021", "• Resolved tickets", "Education", EDU],
     "docx", "Sana Khan", "Support Engineer", 2.0, 3),
    ("internship_plus_job", ["Tara Bose", "tara.bose@example.com", "Experience", "Software Engineer | Nimbus Apps | Jan 2023 – Dec 2023",
                             "• Built services", "Internships", "Software Intern | Nimbus Apps | Jun 2022 – Aug 2022", "• Tested APIs",
                             "Education", EDU], "docx", "Tara Bose", "Software Engineer", 1.1, 3),
    ("abbreviated_month_apostrophe_year", ["Vikram Pillai", "vikram.pillai@example.com", "Experience",
                                           "Backend Developer | Orion Systems | Jan '20 – Mar '22", "• Built APIs", "Education", EDU],
     "docx", "Vikram Pillai", "Backend Developer", 2.2, 3),
    ("pdf_standard", ["Isha Verma", "isha.verma@example.com | +91 90000 22222 | Pune, India", "Experience",
                      "Data Scientist | Helio Payments | Jan 2021 – Dec 2023", "• Trained models", "Education", EDU],
     "pdf", "Isha Verma", "Data Scientist", 3.0, 3),
    ("pdf_to_date", ["Yash Trivedi", "yash.trivedi@example.com", "Experience", "Cloud Engineer | Cloudlane | 2022 to date",
                     "• Managed AWS", "Education", EDU], "pdf", "Yash Trivedi", "Cloud Engineer", 2.5, 3),
]


@pytest.mark.parametrize("cid,lines,kind,name,role,yrs,edu", CASES, ids=[c[0] for c in CASES])
def test_layout_fields(cid, lines, kind, name, role, yrs, edu):
    p, _ = parse(lines, kind)
    assert p["fields"]["name"]["value"] == name
    assert p["employment"], "no dated employment extracted"
    titles = " | ".join(e["title"] or "" for e in p["employment"])
    assert role.lower() in titles.lower()
    assert years(p) == pytest.approx(yrs, abs=0.35)
    assert max(e["level"] for e in p["education"]) == edu
    assert p["fields"]["email"]["value"].endswith("@example.com")


def test_experience_written_as_text_only():
    p, _ = parse(["Anil Kumar", "anil.kumar@example.com", "Summary", "Backend developer with 6+ years of experience building Python services.",
                  "Skills", "Python, Docker", "Education", EDU])
    assert p["employment"] == []
    assert p["fields"]["claimed_years"]["value"] == 6.0
    assert p["fields"]["headline"]["value"].lower() == "backend developer"      # shown as the role, flagged as self-described
    e = analyze_experience([], {"experience": {"min_years": 5}}, set(), AS_OF, None, claimed_years=6.0)
    assert e["status"] == "scored" and e["relevant_effective_years"] == pytest.approx(3.6) and "cannot be verified" in " ".join(e["notes"])


def test_fresher_without_experience_section_is_unverified_with_headline_role():
    p, _ = parse(["Farah Siddiqui", "farah.siddiqui@example.com | github.com/farahdemo", "Summary",
                  "Software Engineer with a B.Tech in Computer Science and two ML projects.", "Skills", "Python, SQL, scikit-learn",
                  "Projects", "Resume Ranker – Python | FastAPI", "• Built a ranking API", "Education", EDU])
    assert p["employment"] == [] and p["fields"]["claimed_years"]["value"] is None
    assert p["fields"]["headline"]["value"] == "Software Engineer"
    e = analyze_experience([], {"experience": {"min_years": 2}}, set(), AS_OF, None)
    assert e["status"] == "unverified" and "freshers" in " ".join(e["notes"])


def test_headline_from_title_line_under_name():
    p, _ = parse(["Gita Rao", "Full Stack Developer", "gita.rao@example.com", "Skills", "React, Node.js", "Education", EDU])
    assert p["fields"]["headline"]["value"] == "Full Stack Developer"


def test_docx_two_column_table_layout():
    from docx import Document
    import io
    d = Document()
    d.add_paragraph("Hari Menon")
    d.add_paragraph("hari.menon@example.com")
    t = d.add_table(rows=1, cols=2)
    left, right = t.rows[0].cells
    for line in ["Skills", "Python", "Django", "PostgreSQL", "Docker", "Git"]:
        left.add_paragraph(line)
    for line in ["Experience", "Backend Developer | Orion Systems | Jan 2020 – Dec 2022", "• Built APIs", "• Wrote tests",
                 "Education", EDU]:
        right.add_paragraph(line)
    buf = io.BytesIO()
    d.save(buf)
    p, _ = parse(None, "docx", blob=buf.getvalue())
    assert p["fields"]["name"]["value"] == "Hari Menon"
    assert any("Backend Developer" in (e["title"] or "") for e in p["employment"])
    assert {"Python", "Django", "PostgreSQL"} <= set(p["skills"])


def test_docx_text_box_content_is_extracted():
    """Contact details / sidebars in Word text boxes used to be silently dropped."""
    from docx import Document
    from docx.oxml import parse_xml
    import io
    d = Document()
    d.add_paragraph("Ira Chopra")
    par = d.add_paragraph("")
    ns = ('xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
          'xmlns:v="urn:schemas-microsoft-com:vml"')
    par._p.append(parse_xml(f'<w:r {ns}><w:pict><v:shape><v:textbox><w:txbxContent>'
                            '<w:p><w:r><w:t>ira.chopra@example.com</w:t></w:r></w:p>'
                            '<w:p><w:r><w:t>Skills: Python, Docker, Kubernetes, AWS</w:t></w:r></w:p>'
                            '</w:txbxContent></v:textbox></v:shape></w:pict></w:r>'))
    for line in ["Experience", "DevOps Engineer | Cloudlane | Jan 2021 – Dec 2023", "• Ran clusters", "Education", EDU]:
        d.add_paragraph(line)
    buf = io.BytesIO()
    d.save(buf)
    p, doc = parse(None, "docx", blob=buf.getvalue())
    assert p["fields"]["email"]["value"] == "ira.chopra@example.com"
    assert "text_boxes_not_extracted" not in doc.warnings


def test_scanned_pdf_is_flagged_for_review_when_ocr_was_used():
    """A resume read through OCR must never look like a normal parse."""
    class Doc:  # minimal stand-in for ParsedDocument
        ocr_used, quality, warnings = True, 0.8, ["ocr_used"]
        pages = [type("P", (), {"text": "x" * 500})()]
    parsed = {"fields": {"name": {"value": "Jane Roe"}}}
    r = build_review(Doc, parsed)
    assert r["needs_review"] and r["codes"] == ["scanned_ocr"] and r["reasons"] == [REVIEW_REASONS["scanned_ocr"]]


def test_clean_text_pdf_is_not_flagged():
    p, doc = parse(["Aarav Mehta", "aarav.mehta@example.com", "Experience", "Backend Engineer | Nimbus Apps | Jan 2021 – Present",
                    "• Built APIs and services in Python for payment workflows and reporting dashboards", "Skills", "Python, Docker, SQL",
                    "Education", EDU], "pdf")
    assert not build_review(doc, p)["needs_review"]
