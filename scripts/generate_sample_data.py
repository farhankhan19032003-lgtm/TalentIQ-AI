"""Generate the SYNTHETIC benchmark: resumes (PDF/DOCX in several layouts + failure cases), job descriptions
and a ground-truth file. All people/companies/contacts are fictional. Usage (PowerShell): python scripts/generate_sample_data.py"""
import json
import random
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from synthetic.jds import JDS, JD_KEYS  # noqa: E402
from synthetic.profiles import JD_ORDER, PRESENT, PROFILES, SPECIAL  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "sample_data"
AS_OF = date(2026, 11, 1)
DATASET_VERSION = "1.0.0"
MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
LONG = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]


# ------------------------------------------------------------------ content model
def fmt_date(d, style, end=False):
    if d == PRESENT:
        return "Present"
    y, m = d
    return {"mon": f"{MON[m - 1]} {y}", "slash": f"{m:02d}/{y}", "year": f"{y}", "long": f"{LONG[m - 1]} {y}"}[style]


def dates_text(e, style):
    st = "year" if e["ds"] == "year" else style
    return f"{fmt_date(e['start'], st)} – {fmt_date(e['end'], st, True)}"


def split_skill(item):
    if "=" in item:
        disp, canon = item.split("=", 1)
        return disp, canon
    return item, item


def build_content(p):
    idx = int(p["key"][1:])
    style = ["mon", "slash", "mon", "long"][idx % 4]
    two_line = idx % 3 == 0
    contact = []
    if "email" in p["links"]:
        contact.append(p["name"].lower().replace(" ", ".") + "@example.com")
    if "phone" in p["links"]:
        contact.append(f"+91 90000 {10000 + idx * 37:05d}")
    if "loc" in p["links"]:
        contact.append(p["loc"])
    if "linkedin" in p["links"]:
        contact.append("linkedin.com/in/" + p["name"].lower().replace(" ", "-") + "-demo")
    if "github" in p["links"]:
        contact.append("github.com/" + p["name"].lower().replace(" ", "") + "demo")
    secs, truth = [], set()
    if p["summary"]:
        secs.append(("Professional Summary" if idx % 2 else "Summary", [("p", p["summary"][0])]))
        truth |= set(p["summary"][1])
    if p["exp"]:
        blocks = []
        for e in p["exp"]:
            dt = dates_text(e, style)
            ttl = e["title"] + {"part_time": " (Part-time)", "contract": " (Contract)"}.get(e["type"], "")
            if two_line:
                blocks += [("h", f"{ttl}, {e['company']}"), ("p", dt)]
            else:
                blocks += [("h", f"{ttl} | {e['company']} | {dt}")]
            for t, tags in e["bullets"]:
                blocks.append(("b", t))
                truth |= set(tags)
            truth |= set(e["tags"])
        secs.append(("Work Experience" if idx % 2 else "Experience", blocks))
    if p["edu"]:
        secs.append(("Education", [("p", l) for l in p["edu"]]))
    sk = []
    for g, items in p["skills"].items():
        disp = []
        for it in items:
            d, c = split_skill(it)
            disp.append(d)
            truth.add(c)
        sk.append(("p", ", ".join(disp) if g == "Skills" else f"{g}: " + ", ".join(disp)))
    if sk:
        secs.append(("Technical Skills" if idx % 2 else "Skills", sk))
    if p["projects"]:
        blocks = []
        for name, bl in p["projects"]:
            blocks.append(("h", name))
            for t, tags in bl:
                blocks.append(("b", t))
                truth |= set(tags)
        secs.append(("Projects", blocks))
    if p["certs"]:
        secs.append(("Certifications", [("b", c) for c in p["certs"]]))
    # skills mentioned only in job titles
    for e in p["exp"]:
        pass
    return {"name": p["name"], "contact": " | ".join(contact), "email": next((c for c in contact if "@" in c), None), "protected": p["protected"],
            "sections": secs, "truth": sorted(truth)}


# ------------------------------------------------------------------ independent experience ground truth
def month_idx(d, ds, is_end):
    if d == PRESENT:
        return AS_OF.year * 12 + AS_OF.month - 1
    y, m = d
    if ds == "year":
        m = 6 if is_end else 7
    return y * 12 + m - 1


def expected_experience(p):
    full, part, intern = set(), set(), set()
    for e in p["exp"]:
        a, b_ = month_idx(e["start"], e["ds"], False), month_idx(e["end"], e["ds"], True)
        if b_ < a:
            b_ = a + 5
        rng = set(range(a, b_ + 1))
        {"full_time": full, "contract": full, "part_time": part, "internship": intern}[e["type"]].update(rng)
    part -= full
    intern -= full | part
    return {"fulltime_months": len(full), "part_time_months": len(part), "internship_months": len(intern),
            "effective_years": round((len(full) + 0.5 * len(part) + 0.5 * len(intern)) / 12, 2)}


# ------------------------------------------------------------------ renderers
def _styles():
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    base = getSampleStyleSheet()
    return {"name": ParagraphStyle("n", parent=base["Title"], fontSize=20, spaceAfter=4), "contact": ParagraphStyle("c", parent=base["Normal"], fontSize=9, spaceAfter=8),
            "h": ParagraphStyle("hd", parent=base["Heading2"], fontSize=12, spaceBefore=8, spaceAfter=3, textColor="#1e3a8a"),
            "p": ParagraphStyle("p", parent=base["Normal"], fontSize=9.5, leading=12), "ent": ParagraphStyle("e", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=10, spaceBefore=4),
            "b": ParagraphStyle("b", parent=base["Normal"], fontSize=9.5, leading=12, leftIndent=12, bulletIndent=2)}


def _esc(t):
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _flow(blocks, st):
    from reportlab.platypus import Paragraph
    out = []
    for kind, t in blocks:
        if kind == "h":
            out.append(Paragraph(_esc(t), st["ent"]))
        elif kind == "b":
            out.append(Paragraph("•&nbsp;&nbsp;" + _esc(t), st["b"]))
        else:
            out.append(Paragraph(_esc(t), st["p"]))
    return out


def render_pdf_single(c, path):
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import Paragraph, SimpleDocTemplate
    st = _styles()
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=42, rightMargin=42, topMargin=36, bottomMargin=36)
    story = [Paragraph(_esc(c["name"]), st["name"]), Paragraph(_esc(c["contact"]), st["contact"])]
    story += [Paragraph(_esc(l), st["contact"]) for l in c["protected"]]
    for head, blocks in c["sections"]:
        story.append(Paragraph(head.upper() if head == "Education" else head, st["h"]))
        story += _flow(blocks, st)
    doc.build(story)


def render_pdf_two_col(c, path):
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import BaseDocTemplate, Frame, FrameBreak, PageTemplate, Paragraph, NextPageTemplate
    st = _styles()
    W, H = A4
    doc = BaseDocTemplate(str(path), pagesize=A4)
    hdr = Frame(36, H - 130, W - 72, 94, id="h", leftPadding=0, rightPadding=0)
    left = Frame(36, 36, 175, H - 180, id="l", leftPadding=0, rightPadding=8)
    right = Frame(225, 36, W - 261, H - 180, id="r", leftPadding=0, rightPadding=0)
    doc.addPageTemplates([PageTemplate("first", [hdr, left, right]), PageTemplate("later", [Frame(36, 36, 175, H - 72, id="l2"), Frame(225, 36, W - 261, H - 72, id="r2")])])
    story = [Paragraph(_esc(c["name"]), st["name"]), Paragraph(_esc(c["contact"]), st["contact"])]
    story += [Paragraph(_esc(l), st["contact"]) for l in c["protected"]]
    story.append(FrameBreak())
    L = [s for s in c["sections"] if s[0] in ("Skills", "Technical Skills", "Education", "Certifications")]
    R = [s for s in c["sections"] if s not in L]
    for head, blocks in L:
        story.append(Paragraph(head, st["h"]))
        story += _flow(blocks, st)
    story.append(FrameBreak())
    story.append(NextPageTemplate("later"))
    for head, blocks in R:
        story.append(Paragraph(head, st["h"]))
        story += _flow(blocks, st)
    doc.build(story)


def _docx_fill(container, blocks, doc=None):
    from docx.shared import Pt
    for kind, t in blocks:
        if kind == "b":
            para = container.add_paragraph(t, style="List Bullet")
        else:
            para = container.add_paragraph()
            r = para.add_run(t)
            if kind == "h":
                r.bold = True


def render_docx(c, path, table=False):
    from docx import Document
    d = Document()
    d.add_paragraph(c["name"], style="Title")
    d.add_paragraph(c["contact"])
    for l in c["protected"]:
        d.add_paragraph(l)
    if not table:
        for head, blocks in c["sections"]:
            d.add_heading(head, level=1)
            _docx_fill(d, blocks)
    else:
        L = [s for s in c["sections"] if s[0] in ("Skills", "Technical Skills", "Education", "Certifications")]
        R = [s for s in c["sections"] if s not in L]
        t = d.add_table(rows=1, cols=2)
        for cell, secs in zip(t.rows[0].cells, (L, R)):
            first = True
            for head, blocks in secs:
                hp = cell.paragraphs[0] if first and not cell.paragraphs[0].text else cell.add_paragraph()
                first = False
                hp.add_run(head).bold = True
                _docx_fill(cell, blocks)
    d.save(str(path))


def _text_lines(c):
    out = [c["name"], c["contact"]]
    for head, blocks in c["sections"]:
        out.append(head.upper())
        out += [("- " if k == "b" else "") + t for k, t in blocks]
    return out


def render_scanned(c, path):
    from PIL import Image, ImageDraw, ImageFont
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    fp = next((f for f in ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans.ttf"] if Path(f).exists()), None)
    font = ImageFont.truetype(fp, 26) if fp else ImageFont.load_default(size=26)
    img = Image.new("L", (1700, 2200), 255)
    dr = ImageDraw.Draw(img)
    y = 80
    for line in _text_lines(c):
        words, cur = line.split(), ""
        for w in words:
            if dr.textlength(cur + " " + w, font=font) > 1500:
                dr.text((100, y), cur, font=font, fill=0); y += 40; cur = w
            else:
                cur = (cur + " " + w).strip()
        dr.text((100, y), cur, font=font, fill=0); y += 46
    tmp = Path(path).with_suffix(".png")
    img.save(tmp)
    cv = canvas.Canvas(str(path), pagesize=A4)
    cv.drawImage(str(tmp), 0, 0, width=A4[0], height=A4[1])
    cv.save()
    tmp.unlink()


def render_encrypted(c, path):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.pdfencrypt import StandardEncryption
    from reportlab.platypus import Paragraph, SimpleDocTemplate
    st = _styles()
    doc = SimpleDocTemplate(str(path), pagesize=A4, encrypt=StandardEncryption("secret", canPrint=0))
    doc.build([Paragraph(_esc(l), st["p"]) for l in _text_lines(c)])


def main():
    (OUT / "resumes").mkdir(parents=True, exist_ok=True)
    (OUT / "job_descriptions").mkdir(parents=True, exist_ok=True)
    (OUT / "ground_truth").mkdir(parents=True, exist_ok=True)
    for f in (OUT / "resumes").glob("*"):
        f.unlink()
    gt = []
    contents = {}
    for p in PROFILES:
        c = build_content(p)
        contents[p["key"]] = c
        path = OUT / "resumes" / p["file"]
        {"pdf_single": render_pdf_single, "pdf_two_col": render_pdf_two_col, "docx_headings": lambda c_, p_: render_docx(c_, p_, False),
         "docx_table": lambda c_, p_: render_docx(c_, p_, True)}[p["layout"]](c, path)
        exp = expected_experience(p)
        gt.append({"key": p["key"], "file": p["file"], "layout": p["layout"], "expects": "parsed", "name": p["name"], "email": c["email"],
                   "skills": c["truth"], "experience": {**exp, "n_employment": len(p["exp"])},
                   "education_level": None if not p["edu"] else max(l_ for l_, kw in ((5, "Ph"), (4, "M."), (4, "MBA"), (4, "Master"), (3, "B."), (3, "BCA")) if any(kw in e for e in p["edu"])),
                   "relevance": p["grades"], "tags": [k for k in p["extra"]], "protected_lines": len(p["protected"])})
    # special files
    by_key = {p["key"]: p for p in PROFILES}
    for s in SPECIAL:
        path = OUT / "resumes" / s["file"]
        rec = {"key": s["key"], "file": s["file"], "expects": s["expects"], "kind": s["kind"], "error_code": s.get("error_code"), "relevance": None}
        if s["kind"] == "duplicate_of":
            path.write_bytes((OUT / "resumes" / by_key[s["source"]]["file"]).read_bytes())
            rec["duplicate_of"] = by_key[s["source"]]["file"]
        elif s["kind"] == "scanned":
            p = dict(key="p30", name=s["name"], links=("email", "phone", "loc"), loc="Pune, India", protected=[], projects=[], certs=[],
                     summary=("Machine learning engineer with 3 years of experience.", ("Machine Learning",)),
                     skills={"Skills": ["Python", "Machine Learning", "scikit-learn", "SQL", "Docker"]},
                     exp=[dict(title="ML Engineer", company="Cobalt Systems", start=(2022, 1), end=PRESENT, type="full_time", ds="mon", tags=("Machine Learning",),
                               bullets=[("Trained scikit-learn models and shipped them in Docker containers", ("scikit-learn", "Docker"))])],
                     edu=["B.Tech in Computer Science | Sunrise Institute of Technology | 2017 – 2021"], grades=dict(zip(JD_ORDER, s["grades"])), extra={})
            c = build_content(p)
            render_scanned(c, path)
            rec.update(name=s["name"], skills=c["truth"], experience={**expected_experience(p), "n_employment": 1}, relevance=p["grades"], email=c["email"], layout="scanned_image_only")
        elif s["kind"] == "corrupted_pdf":
            path.write_bytes(b"%PDF-1.4\n" + random.Random(42).randbytes(3000))
        elif s["kind"] == "encrypted":
            render_encrypted(contents["p01"], path)
        elif s["kind"] == "corrupted_docx":
            path.write_bytes(b"PK\x03\x04" + random.Random(7).randbytes(2500))
        elif s["kind"] == "fake_pdf":
            path.write_text("This is plain text pretending to be a PDF resume. Skills: Python, SQL. " * 3)
        elif s["kind"] == "txt":
            path.write_text("Resume notes in a text file: Python developer with SQL experience.\n" * 3)
        gt.append(rec)
    for k, text in JDS.items():
        (OUT / "job_descriptions" / f"{k}.txt").write_text(text, encoding="utf-8")
    # one JD as DOCX to exercise DOCX JD upload
    from docx import Document
    d = Document()
    for line in JDS["python_backend_developer"].splitlines():
        d.add_paragraph(line)
    d.save(str(OUT / "job_descriptions" / "python_backend_developer.docx"))
    jd_truth = {
        "ai_ml_engineer": {"must": ["Machine Learning", "Python", "scikit-learn", "NLP", "SQL", "Docker", "Git", "REST APIs"],
                           "preferred": ["PyTorch or Transformers", "AWS", "MLOps", "Kubernetes"], "min_years": 2, "education_level": 3, "preferred_education_level": 4},
        "python_backend_developer": {"must": ["Python", "FastAPI or Django", "REST APIs", "PostgreSQL", "Docker", "Git", "Unit Testing", "pytest"],
                                     "preferred": ["Redis", "Celery", "Kubernetes", "CI/CD", "AWS"], "min_years": 3, "education_level": 3, "preferred_education_level": None},
        "data_analyst": {"must": ["SQL", "Excel", "Tableau or Power BI", "Data Analysis", "Data Visualization", "Statistics"],
                         "preferred": ["Python", "Pandas", "Hypothesis Testing", "Communication"], "min_years": 1, "education_level": 3, "preferred_education_level": None},
        "java_backend_developer": {"must": ["Java", "Spring Boot", "Hibernate", "MySQL", "REST APIs", "Microservices", "Maven", "JUnit"],
                                   "preferred": ["Kafka", "Docker", "AWS"], "min_years": 3, "education_level": 3, "preferred_education_level": None},
        "cloud_devops_engineer": {"must": ["AWS", "Docker", "Kubernetes", "Terraform", "CI/CD", "Jenkins", "Linux", "Python or Bash"],
                                  "preferred": ["Ansible", "Prometheus", "Grafana", "Azure"], "min_years": 3, "education_level": 3, "preferred_education_level": None},
        "full_stack_developer": {"must": ["React", "TypeScript", "Node.js", "PostgreSQL", "REST APIs", "HTML", "CSS", "Git"],
                                 "preferred": ["Docker", "AWS", "Next.js"], "min_years": 2, "education_level": 3, "preferred_education_level": None}}
    doc = {"dataset_version": DATASET_VERSION, "as_of": AS_OF.isoformat(), "synthetic": True,
           "label_provenance": "Skill labels are defined BY CONSTRUCTION (every sentence is tagged with the skills it was written to contain) and were reviewed by the author. "
                               "Relevance grades (0-3) were assigned by the author from each profile's design intent. Not independently annotated.",
           "jd_order": JD_ORDER, "job_descriptions": jd_truth, "resumes": gt}
    (OUT / "ground_truth" / "ground_truth.json").write_text(json.dumps(doc, indent=1), encoding="utf-8")
    n = len(list((OUT / 'resumes').iterdir()))
    print(f"generated {n} resume files, {len(JDS)} job descriptions (+1 DOCX) in {OUT}")


if __name__ == "__main__":
    main()
