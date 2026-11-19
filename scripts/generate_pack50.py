"""Generate the SYNTHETIC 50-resume demo pack: sample_data/pack50/resume_XX_firstname_lastname.(pdf|docx) plus edge cases.
Everyone, every company and every e-mail (name@example.com) is fictional. Deterministic (seeded), so re-running gives identical files.
Usage: python scripts/generate_pack50.py"""
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import generate_sample_data as g  # noqa: E402  (reuses the renderers and the content builder of the main synthetic set)
from synthetic.profiles import BTECH, PRESENT, E, P, b  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "sample_data" / "pack50"
FIRST = ["Aarav", "Vivaan", "Aditya", "Arjun", "Reyansh", "Ishaan", "Kabir", "Rohan", "Kunal", "Dev", "Ananya", "Diya", "Kavya", "Priya", "Nisha",
         "Meera", "Tara", "Zoya", "Isha", "Sana", "Anika", "Riya", "Pooja", "Neha", "Divya", "Manav", "Yash", "Varun", "Sahil", "Harsh",
         "Omkar", "Pranav", "Rahul", "Sameer", "Gaurav", "Chirag", "Lakshmi", "Farah", "Simran", "Tanya", "Aman", "Naveen", "Ritu", "Mohan",
         "Leela", "Bhavna", "Imran", "Jatin", "Kiran", "Mira"]
LAST = ["Sharma", "Rao", "Menon", "Iyer", "Nair", "Kulkarni", "Patil", "Desai", "Joshi", "Verma", "Gupta", "Singh", "Reddy", "Das", "Bose",
        "Malhotra", "Kapoor", "Chopra", "Bhatt", "Mehta", "Pillai", "Sethi", "Hasan", "Ali", "Khan", "Shah", "Yadav", "Pawar", "Trivedi", "Sen"]
COMPANIES = ["Brightwave Labs", "Cobalt Systems", "Lumen Retail Tech", "Helio Payments", "Quanta Logistics", "Maple & Oak Consulting", "Northwind Digital"]
CITIES = ["Pune, India", "Bengaluru, India", "Hyderabad, India", "Chennai, India", "Mumbai, India", "Nagpur, India"]

# family -> (titles, summary noun, skill pool, bullet pool); a bullet is (text, tags)
FAMILIES = {
    "backend": (["Python Developer", "Backend Engineer", "Software Engineer"], "Backend developer",
                ["Python", "FastAPI", "REST APIs", "PostgreSQL", "Docker", "Git", "pytest", "Redis", "CI/CD"],
                [b("Built FastAPI REST APIs backed by PostgreSQL", "FastAPI", "REST APIs", "PostgreSQL"),
                 b("Wrote pytest suites and ran them in CI/CD pipelines", "pytest", "CI/CD"),
                 b("Containerised services with Docker for repeatable deployments", "Docker"),
                 b("Cached hot queries in Redis to cut API latency", "Redis")]),
    "backend_related": (["Python Developer", "Backend Engineer"], "Backend developer",
                        ["Python", "Flask", "REST APIs", "MySQL", "Git", "SQL"],
                        [b("Built Flask REST APIs backed by MySQL", "Flask", "REST APIs", "MySQL"),
                         b("Version-controlled releases with Git branching", "Git")]),
    "ml": (["Machine Learning Engineer", "Data Scientist"], "Machine learning engineer",
           ["Python", "Machine Learning", "scikit-learn", "PyTorch", "NLP", "SQL", "Docker", "Git"],
           [b("Trained scikit-learn models for churn prediction on SQL data", "scikit-learn", "SQL", "Machine Learning"),
            b("Built NLP classifiers with PyTorch for support tickets", "NLP", "PyTorch"),
            b("Packaged inference services with Docker", "Docker")]),
    "data": (["Data Analyst", "Business Analyst"], "Data analyst",
             ["SQL", "Excel", "Tableau", "Data Analysis", "Data Visualization", "Statistics", "Python", "Pandas"],
             [b("Wrote SQL reports and built Tableau dashboards for weekly reviews", "SQL", "Tableau", "Data Visualization"),
              b("Ran hypothesis tests and regression analysis in Excel and Python", "Excel", "Statistics", "Python"),
              b("Cleaned datasets with Pandas before analysis", "Pandas", "Data Analysis")]),
    "java": (["Java Developer", "Backend Engineer"], "Java backend developer",
             ["Java", "Spring Boot", "Hibernate", "MySQL", "REST APIs", "Microservices", "Maven", "JUnit"],
             [b("Developed Spring Boot microservices with Hibernate and MySQL", "Spring Boot", "Hibernate", "MySQL", "Microservices"),
              b("Exposed REST APIs and covered them with JUnit tests", "REST APIs", "JUnit"),
              b("Managed builds with Maven", "Maven")]),
    "devops": (["DevOps Engineer", "Cloud Engineer"], "DevOps engineer",
               ["AWS", "Docker", "Kubernetes", "Terraform", "CI/CD", "Jenkins", "Linux", "Python"],
               [b("Provisioned AWS infrastructure with Terraform", "AWS", "Terraform"),
                b("Ran Docker workloads on Kubernetes with Jenkins CI/CD pipelines", "Docker", "Kubernetes", "Jenkins", "CI/CD"),
                b("Automated Linux maintenance tasks with Python scripts", "Linux", "Python")]),
    "fullstack": (["Full Stack Developer", "Frontend Engineer"], "Full stack developer",
                  ["React", "TypeScript", "Node.js", "PostgreSQL", "REST APIs", "HTML", "CSS", "Git"],
                  [b("Built React and TypeScript interfaces consuming REST APIs", "React", "TypeScript", "REST APIs"),
                   b("Implemented Node.js services storing data in PostgreSQL", "Node.js", "PostgreSQL"),
                   b("Styled responsive pages with HTML and CSS", "HTML", "CSS")]),
    "sales": (["Sales Executive", "Accounts Manager"], "Sales professional", ["Excel", "Communication"],
              [b("Managed regional accounts and weekly forecasts in Excel", "Excel")]),
    "accountant": (["Accountant", "Finance Associate"], "Accountant", ["Excel", "Communication"],
                   [b("Reconciled ledgers and prepared monthly statements in Excel", "Excel")]),
}
# (family, tier) for the 50 resumes, strong -> poor. tier sets the amount of evidence
PLAN = ([("backend", "strong")] * 6 + [("backend", "medium")] * 3 + [("backend_related", "medium")] * 4 + [("backend", "weak")] * 3
        + [("ml", "strong")] * 3 + [("ml", "medium")] * 3 + [("data", "strong")] * 3 + [("data", "medium")] * 3 + [("data", "weak")] * 2
        + [("java", "strong")] * 3 + [("java", "medium")] * 2 + [("devops", "strong")] * 3 + [("devops", "medium")] * 2
        + [("fullstack", "strong")] * 3 + [("fullstack", "medium")] * 2 + [("sales", "weak")] * 2 + [("accountant", "weak")] * 3)
LAYOUTS = ["pdf_single", "pdf_two_col"] * 21 + ["docx_headings", "docx_table"] * 4          # 42 PDF + 8 DOCX


def profile(i: int, family: str, tier: str, name: str, rng: random.Random) -> dict:
    """One synthetic profile; the tier controls years of experience and how much skill evidence the resume shows."""
    titles, noun, skills, bullets = FAMILIES[family]
    years = {"strong": rng.randint(4, 10), "medium": rng.randint(2, 6), "weak": rng.choice([0, 1, 1, 2])}[tier]
    n_b = {"strong": len(bullets), "medium": max(2, len(bullets) - 1), "weak": 1}[tier]
    keep = skills if tier == "strong" else skills[: max(3, round(len(skills) * (0.7 if tier == "medium" else 0.4)))]
    start_year = 2026 - years
    exp = [E(rng.choice(titles), rng.choice(COMPANIES), (start_year, rng.randint(1, 12)), PRESENT, bullets[:n_b], tags=(keep[0],))] if years else []
    if years >= 6:
        exp.append(E("Junior " + titles[0], rng.choice(COMPANIES), (start_year - 3, 6), (start_year, 1), bullets[:1]))
    summary = b(f"{noun} with {years} years of experience." if years else f"{noun}, recent graduate.", ())
    edu = [BTECH.format(a=start_year - 4 if years else 2021, b=start_year if years else 2025)]
    return P(f"p{100 + i}", f"resume_{i + 1:02d}_{name.lower().replace(' ', '_')}", LAYOUTS[i],
             name, [0] * 6, {"Skills": keep}, exp, edu, [], [], summary, loc=rng.choice(CITIES))


def main() -> None:
    rng = random.Random(2026)
    names = [f"{f} {l}" for f, l in zip(rng.sample(FIRST, 50), (rng.sample(LAST, 30) * 2)[:50])]
    assert len(set(names)) == 50
    plan = PLAN[:]
    rng.shuffle(plan)                                   # file order must not reveal the fit
    assert len(plan) == 50 and len(LAYOUTS) == 50
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "edge_cases").mkdir(exist_ok=True)
    for f in list(OUT.glob("resume_*")) + list((OUT / "edge_cases").glob("*")):
        f.unlink()
    manifest = []
    for i, ((family, tier), name) in enumerate(zip(plan, names)):
        p = profile(i, family, tier, name, rng)
        content = g.build_content(p)
        ext = "pdf" if p["layout"].startswith("pdf") else "docx"
        path = OUT / f"{p['file']}.{ext}"
        {"pdf_single": g.render_pdf_single, "pdf_two_col": g.render_pdf_two_col,
         "docx_headings": lambda c, q: g.render_docx(c, q, False), "docx_table": lambda c, q: g.render_docx(c, q, True)}[p["layout"]](content, path)
        manifest.append({"file": path.name, "name": name, "email": content["email"], "family": family, "tier": tier})
    # edge cases: the same generators as the main sample set
    seed = g.build_content(g.PROFILES[0])
    g.render_encrypted(seed, OUT / "edge_cases" / "password_protected_resume.pdf")
    (OUT / "edge_cases" / "corrupted_resume.pdf").write_bytes(b"%PDF-1.4\n" + random.Random(42).randbytes(3000))
    scanned = next(s for s in g.SPECIAL if s["kind"] == "scanned")
    sp = dict(key="p30", name=scanned["name"], links=("email", "phone", "loc"), loc="Pune, India", protected=[], projects=[], certs=[],
              summary=("Machine learning engineer with 3 years of experience.", ("Machine Learning",)),
              skills={"Skills": ["Python", "Machine Learning", "scikit-learn", "SQL", "Docker"]},
              exp=[dict(title="ML Engineer", company="Cobalt Systems", start=(2022, 1), end=PRESENT, type="full_time", ds="mon", tags=("Machine Learning",),
                        bullets=[("Trained scikit-learn models and shipped them in Docker containers", ("scikit-learn", "Docker"))])],
              edu=["B.Tech in Computer Science | Sunrise Institute of Technology | 2017 – 2021"], grades={}, extra={})
    g.render_scanned(g.build_content(sp), OUT / "edge_cases" / "scanned_resume_image_only.pdf")
    # one byte-identical copy to demonstrate duplicate handling
    first = OUT / manifest[0]["file"]
    (OUT / "edge_cases" / ("duplicate_of_" + first.name)).write_bytes(first.read_bytes())
    (OUT / "manifest.json").write_text(json.dumps({"synthetic": True, "note": "Fictional people; all e-mails are @example.com.", "resumes": manifest}, indent=1), encoding="utf-8")
    print(f"generated {len(manifest)} resumes and {len(list((OUT / 'edge_cases').iterdir()))} edge cases in {OUT}")


if __name__ == "__main__":
    main()
