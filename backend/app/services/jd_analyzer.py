"""Job-description intelligence: turns free text into structured, editable requirements."""
from __future__ import annotations

import re

from .resume_extractor import LEVEL_RE
from .skill_extractor import Line, Ontology, SkillExtractor

RE_PREF = re.compile(r"\b(preferred|nice[\s\-]to[\s\-]have|good[\s\-]to[\s\-]have|bonus|a plus|is a plus|are a plus|desirable|optional|familiarity with|exposure to|advantageous)\b", re.I)
RE_MUST = re.compile(r"\b(must|required|mandatory|essential|minimum)\b", re.I)
HEAD_PREF = re.compile(r"preferred|nice[\s\-]to[\s\-]have|good[\s\-]to[\s\-]have|bonus|desirable|optional|plus", re.I)
HEAD_REQ = re.compile(r"requirement|qualification|must|required|looking for|you(?:'ll)? need|you have|skills|who you are|what we expect", re.I)
HEAD_RESP = re.compile(r"responsibilit|what you(?:'ll| will) do|duties|key tasks|the role|your role|day[\s\-]to[\s\-]day", re.I)
HEAD_IGNORE = re.compile(r"about (us|the company)|benefits|perks|we offer|why join|equal opportunity|how to apply", re.I)
YEARS = re.compile(r"(\d+(?:\.\d+)?)\s*(?:\+|plus)?\s*(?:(?:-|–|to)\s*(\d+(?:\.\d+)?))?\s*\+?\s*(?:years?|yrs?)", re.I)
CORE_WEIGHT = 2.0
# One concept, many names: when a JD names both the practice and a tool that implements it ("unit testing with pytest"),
# counting them as two requirements would penalise a candidate twice for one missing idea. They are merged into a single
# "X (tool)" requirement that any of the names satisfies. Only genuine practice->tool pairs belong here (NOT Python->FastAPI).
CONCEPT_TOOLS = {"Unit Testing": ("pytest", "JUnit", "Jest")}
GENERIC_TITLE = {"senior", "junior", "sr", "jr", "lead", "associate", "i", "ii", "iii", "the", "of", "and", "engineer", "developer", "specialist", "staff", "principal"}

GROUPS = {
    "programming_languages": {"Programming Languages"},
    "frameworks": {"Frontend", "Backend"},
    "databases": {"Databases"},
    "cloud": {"Cloud"},
    "tools_platforms": {"DevOps", "Testing", "Frameworks and Tools", "Security"},
    "ai_ml": {"AI and Machine Learning"},
    "data": {"Data Science", "Data Engineering"},
}


def slug(s: str) -> str:
    """Lower-case identifier used for requirement ids."""
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def _heading(line: str):
    t = line.strip().rstrip(":").strip()
    if not t or len(t) > 70 or t.startswith("•") or t.startswith("-"):
        return None
    is_head = line.strip().endswith(":") or (t.isupper() and len(t.split()) <= 6) or len(t.split()) <= 4
    if not is_head:
        return None
    if HEAD_IGNORE.search(t):
        return "ignore"
    if HEAD_PREF.search(t):
        return "preferred"
    if HEAD_RESP.search(t):
        return "responsibilities"
    if HEAD_REQ.search(t):
        return "must"
    return None


def _merge_concepts(requirements: list[dict], technical: dict[str, str]) -> None:
    """In place: fold tool requirements into the practice requirement they implement (see CONCEPT_TOOLS)."""
    by_name = {r["name"]: r for r in requirements}
    for concept, tools in CONCEPT_TOOLS.items():
        present = [t for t in tools if t in by_name and not by_name[t].get("any_of")]
        base = by_name.get(concept)
        if not present or base is None or base.get("any_of"):
            continue
        imps = [base["importance"]] + [by_name[t]["importance"] for t in present]
        base.update(name=f"{concept} ({', '.join(present)})", any_of=[concept, *present], importance="must" if "must" in imps else "preferred",
                    weight=max(base["weight"], *(by_name[t]["weight"] for t in present)))
        base["id"] = "req_" + slug(base["name"])
        for t in present:
            requirements.remove(by_name[t])
            technical.pop(t, None)
        technical.pop(concept, None)
        technical[base["name"]] = base["importance"]


def analyze_jd(text: str, extractor: SkillExtractor, onto: Ontology, title: str | None = None) -> dict:
    """Parse free-text job description into editable requirements (must/preferred, 'X or Y' alternatives, merged practice+tool), years and education."""
    raw_lines = [l.rstrip() for l in text.replace("\r", "").split("\n")]
    lines = [l for l in raw_lines if l.strip()]
    if not title:
        m = next((re.sub(r"^(job )?title\s*:\s*", "", l.strip(), flags=re.I) for l in lines if len(l.strip()) < 80), None)
        title = m
    mode = "must"
    importance: dict[str, str] = {}
    responsibilities, req_lines, opt_lines, education = [], [], [], []
    years_must, years_pref = [], []
    skill_lines: list[Line] = []
    for l in lines:
        h = _heading(l)
        if h:
            mode = h
            continue
        if mode == "ignore":
            continue
        t = l.strip()
        bullet = t.lstrip("•-*– ").strip()
        line_mode = "preferred" if (mode == "preferred" or RE_PREF.search(t)) else mode
        if line_mode == "responsibilities":
            responsibilities.append(bullet)
        elif line_mode == "preferred":
            opt_lines.append(bullet)
        elif line_mode == "must" and (t.startswith(("•", "-", "*", "–")) or len(bullet.split()) > 3):
            req_lines.append(bullet)
        skill_lines.append(Line(None, line_mode if line_mode in ("must", "preferred", "responsibilities") else "must", bullet))
        for mm in YEARS.finditer(t):
            if re.search(r"experience|exp\b|working|industry", t, re.I):
                lo, hi = float(mm.group(1)), mm.group(2)
                (years_pref if line_mode == "preferred" else years_must).append((lo, float(hi) if hi else None))
        for n, lv, rx in LEVEL_RE:
            if rx.search(t):
                education.append((lv, n, line_mode, bullet))
    # skills with importance (must beats preferred if mentioned in both)
    groups: list[dict] = []
    in_group, outside = set(), set()
    for ln in skill_lines:
        # Skills named only in the Responsibilities section describe the work, not a hard requirement -> preferred (editable by the recruiter)
        imp = "preferred" if ln.section in ("preferred", "responsibilities") else "must"
        hits = sorted({(st, en, nm) for nm, _a, st, en in extractor.find_in_text(ln.text, in_list_context=False)})
        # collapse overlapping matches of the same span, keep order
        chain = []
        for st, en, nm in hits:
            if chain and re.fullmatch(r"\s*(?:or|/)\s*", ln.text[chain[-1][1]:st], re.I) and not onto.is_soft(nm):
                chain[-1] = (chain[-1][0], en, chain[-1][2] + [nm])
            else:
                chain.append((st, en, [nm]))
        for _st, _en, names in chain:
            names = list(dict.fromkeys(names))
            if len(names) > 1:
                groups.append({"names": names, "importance": imp})
                in_group.update(names)
            else:
                outside.add(names[0])
            for nm in names:
                if len(names) == 1 and importance.get(nm) != "must":
                    importance[nm] = imp
    technical = {n: i for n, i in importance.items() if not onto.is_soft(n)}
    for g in groups:   # members only mentioned as alternatives are represented by the group, not separately
        for n in g["names"]:
            if n not in outside:
                technical.pop(n, None)
                importance.pop(n, None)
    soft = sorted(n for n in importance if onto.is_soft(n))
    requirements = [{"id": "req_" + slug(n), "name": n, "category": onto.category(n), "importance": imp, "weight": 1.0, "custom": False}
                    for n, imp in sorted(technical.items(), key=lambda kv: (kv[1] != "must", onto.category(kv[0]), kv[0]))]
    for g in groups:
        nm = " or ".join(g["names"])
        requirements.append({"id": "req_" + slug(nm), "name": nm, "category": onto.category(g["names"][0]), "importance": g["importance"],
                             "weight": 1.0, "custom": False, "any_of": g["names"]})
    _merge_concepts(requirements, technical)
    requirements.sort(key=lambda r: (r["importance"] != "must", r["category"], r["name"]))
    technical.update({r["name"]: r["importance"] for r in requirements if r.get("any_of")})
    # Skills named in the job title are role-defining: weighted x2 (recruiter-editable per requirement)
    title_skills = {nm for nm, _a, _s, _e in extractor.find_in_text(title or "", in_list_context=False)}
    for r in requirements:
        members = set(r.get("any_of") or [r["name"]])
        if r["importance"] == "must" and members & title_skills:
            r["weight"], r["core"] = CORE_WEIGHT, True
    grouped = {g: sorted(n for n in technical if onto.category(n) in cats) for g, cats in GROUPS.items()}
    min_years = max((lo for lo, _ in years_must), default=None)
    pref_years = max([hi for lo, hi in years_must if hi] + [lo for lo, _ in years_pref] + [hi for _, hi in years_pref if hi], default=None)
    if pref_years is not None and min_years is not None and pref_years <= min_years:
        pref_years = None
    req_edu = min((lv for lv, n, m, _ in education if m != "preferred"), default=None)
    pref_edu = max((lv for lv, n, m, _ in education if m == "preferred"), default=None)
    edu_name = {5: "PhD", 4: "Master's", 3: "Bachelor's", 2: "Diploma"}
    dom_text = "\n".join(l for l in lines if not re.match(r"\s*(company|location|salary)\s*:", l, re.I))
    domains = [d for d in onto.domains if re.search(rf"\b{re.escape(d)}\b", dom_text, re.I)]
    domain_terms = sorted(set(domains))
    return {
        "title": title, "technical_skills": sorted(technical), "grouped_skills": grouped, "alternative_groups": [g["names"] for g in groups],
        "must_have": sorted(n for n, i in technical.items() if i == "must"),
        "good_to_have": sorted(n for n, i in technical.items() if i == "preferred"),
        "soft_skills": soft, "domain_knowledge": domain_terms,
        "experience": {"min_years": min_years, "preferred_years": pref_years},
        "education": {"required_level": req_edu, "required_label": edu_name.get(req_edu), "preferred_level": pref_edu,
                      "preferred_label": edu_name.get(pref_edu)},
        "responsibilities": responsibilities, "required_qualifications": req_lines, "optional_qualifications": opt_lines,
        "requirements": requirements,
    }
