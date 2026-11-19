"""Turns a ParsedDocument into structured, provenance-tracked candidate data.
Nothing is invented: absent fields are None. Every value carries page, evidence, method, confidence."""
from __future__ import annotations

import re
from datetime import date

from .document_parser import ParsedDocument
from .security import detect_injection
from .skill_extractor import Line, SkillExtractor

SECTION_PATTERNS = {
    "summary": r"(?:professional |career |executive )?(?:summary|profile|objective|about(?: me)?)",
    "experience": r"(?:work |professional |relevant |industry |employment )?(?:experience|history)(?:(?: &| and) internships?)?|employment(?: history| record)?|work history|"
                  r"career (?:history|progression)|professional background|work background",
    "internships": r"(?:internships?(?: experience)?|(?:industrial )?training(?: (?:&|and) internships?)?)",
    "education": r"education(?:al)?(?: qualifications?| background)?|academics?(?: background| qualifications?)?|qualifications",
    "skills": r"(?:technical |core |key )?skills(?:(?: &| and) tools)?|technologies|tech stack|technical expertise|competencies|skills & technologies",
    "projects": r"(?:academic |personal |key |selected |major )?projects",
    "certifications": r"certifications?(?:(?: &| and) courses)?|licen[sc]es?|courses",
    "achievements": r"achievements?|awards?(?:(?: &| and) honou?rs)?|honou?rs|accomplishments",
    "publications": r"publications?|research papers?",
}
_SECTION_RE = {k: re.compile(v, re.I) for k, v in SECTION_PATTERNS.items()}
HEADING_DECOR = " -–—|•▪■●◆►▶#*_=:·~"   # decoration stripped around a heading line ("— EXPERIENCE —", "## Skills")
PROTECTED = re.compile(
    r"^\s*(?:date of birth|d\.?o\.?b\.?|birth ?date|gender|sex|marital status|religion|caste|race|ethnicity|nationality|"
    r"age|father'?s name|mother'?s name|photo(?:graph)?|disability|political (?:views|affiliation)|spouse)\s*[:\-–]", re.I)

MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
_MON = r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
_DATE = rf"(?:{_MON}\.?,?\s+(?:'?\d{{2}}\b|\d{{4}})|\d{{1,2}}[/.](?:19|20)\d{{2}}|(?:19|20)\d{{2}}[/.]\d{{1,2}}\b|(?:19|20)\d{{2}})"
_END = rf"(?:{_DATE}|present|current|currently|now|till date|till now|to date|ongoing|today|date)"
# "Jan 2020 - Present", "2019-2023", "03/2020 to 05/2021", "03.2020 - 05.2021", "2019-23" (two-digit end year), "since 2021"
RANGE_RE = re.compile(rf"(?P<s>{_DATE})\s*(?:-|–|—|to|until|till)\s*(?P<e>{_END})|"
                      rf"(?P<y1>(?:19|20)\d{{2}})\s*[-–—]\s*(?P<y2>\d{{2}})(?!\d)|"
                      rf"\bsince\s+(?P<since>{_DATE})", re.I)
TITLE_WORDS = re.compile(r"\b(engineer|developer|analyst|scientist|manager|intern|lead|architect|consultant|specialist|administrator|designer|"
                         r"tester|associate|executive|officer|accountant|chef|researcher|programmer|trainee|director|head|assistant|coordinator|"
                         r"technician|sde|devops|sre|qa)\b", re.I)
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?<![\w/])(\+?\d[\d\s\-().]{8,17}\d)(?![\w/])")
LINKEDIN_RE = re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/in/[\w\-%]+", re.I)
GITHUB_RE = re.compile(r"(?:https?://)?(?:www\.)?github\.com/[\w\-]+", re.I)
URL_RE = re.compile(r"(?:https?://|www\.)[^\s,;|]+", re.I)
LEVELS = [("phd", 5, r"ph\.?\s?d|doctorate"), ("masters", 4, r"m\.?\s?tech|m\.?e\.?(?=\s|,|$)|m\.?sc|m\.?s\.?(?=\s|,|$)|mca|mba|master(?:'?s)?|m\.?a\.?(?=\s|,|$)"),
          ("bachelors", 3, r"b\.?\s?tech|b\.?e\.?(?=\s|,|$)|b\.?sc|bca|b\.?s\.?(?=\s|,|$)|bachelor(?:'?s)?|b\.?com|b\.?a\.?(?=\s|,|$)|undergraduate"),
          ("diploma", 2, r"diploma|polytechnic|associate degree")]
LEVEL_RE = [(n, lv, re.compile(rf"\b(?:{p})", re.I)) for n, lv, p in LEVELS]
ROLE_NOUN = r"(?:engineer|developer|analyst|scientist|manager|architect|consultant|designer|programmer|administrator|specialist|researcher|intern|tester|devops|accountant|executive|associate|officer|coordinator|recruiter|trainee|professional)"
HEADLINE_SUMMARY_RE = re.compile(rf"^(?:(?:an?|the)\s+)?(?:(?:experienced|results[- ]driven|motivated|passionate|dedicated|enthusiastic|aspiring|talented|detail[- ]oriented|"
                                 rf"driven|skilled|proficient|dynamic|creative|ambitious|highly\s+\w+)\s+)*((?:[A-Za-z/+.&#-]+\s+){{0,3}}?{ROLE_NOUN})\b", re.I)
CLAIMED_YEARS_RE = re.compile(r"(\d{1,2}(?:\.\d)?)\s*\+?\s*(?:years?|yrs?)(?:\s+of)?(?:\s+[\w/&+.-]+){0,4}?\s+experience|"
                              r"experience\s+(?:of|for)\s+(\d{1,2}(?:\.\d)?)\s*\+?\s*(?:years?|yrs?)", re.I)
INSTITUTION_RE = re.compile(r"\b(university|institute|college|school|academy|polytechnic|iit|nit)\b", re.I)


def _fld(value, page=None, evidence=None, method=None, confidence=0.0):
    return {"value": value, "page": page, "evidence": evidence, "method": method, "confidence": confidence,
            "status": "extracted" if value not in (None, "", []) else "unknown"}


def range_bounds(m: re.Match) -> tuple[str, str]:
    """(start text, end text) of a RANGE_RE match; 'since X' and 'Y1-YY' forms are normalised."""
    if m.group("since"):
        return m.group("since"), "present"
    if m.group("y1"):
        return m.group("y1"), m.group("y1")[:2] + m.group("y2")
    return m.group("s"), m.group("e")


def _parse_date(s: str, end: bool = False):
    s = s.strip().lower().rstrip(".")
    if s in ("present", "current", "currently", "now", "till date", "till now", "to date", "ongoing", "today", "date"):
        return {"current": True}
    m = re.match(rf"({_MON})\.?,?\s+'?(\d{{2,4}})", s, re.I)
    if m:
        y = int(m.group(2)); y = y + 2000 if y < 100 else y
        return {"year": y, "month": MONTHS[m.group(1)[:3].lower()], "precision": "month"}
    m = re.match(r"(\d{1,2})[/.]((?:19|20)\d{2})", s)
    if m and 1 <= int(m.group(1)) <= 12:
        return {"year": int(m.group(2)), "month": int(m.group(1)), "precision": "month"}
    m = re.match(r"((?:19|20)\d{2})[/.](\d{1,2})", s)
    if m and 1 <= int(m.group(2)) <= 12:
        return {"year": int(m.group(1)), "month": int(m.group(2)), "precision": "month"}
    m = re.match(r"((?:19|20)\d{2})", s)
    if m:
        return {"year": int(m.group(1)), "month": 6 if end else 7, "precision": "year"}
    return None


def month_index(d: dict) -> int:
    """Months since year 0 for a parsed date dict (for month-set arithmetic)."""
    return d["year"] * 12 + d["month"] - 1


class ResumeExtractor:
    def __init__(self, skills: SkillExtractor):
        self.skills = skills

    # ---------------------------------------------------------------- segmentation
    def segment(self, doc: ParsedDocument) -> tuple[list[Line], int]:
        """Split the document into labelled lines (header, experience, education, ...) and drop protected-attribute lines."""
        lines, section, removed = [], "header", 0
        for pg in doc.pages:
            for raw in pg.text.split("\n"):
                t = raw.strip()
                if not t:
                    continue
                if PROTECTED.match(t):
                    removed += 1
                    continue
                head = re.sub(r"[:\s]+$", "", t)
                if len(head) <= 45 and not t.startswith("•"):
                    hit = next((k for k, rx in _SECTION_RE.items() if rx.fullmatch(head.strip(HEADING_DECOR))), None)
                    if hit:
                        section = hit
                        lines.append(Line(pg.number, "heading:" + hit, t))
                        continue
                lines.append(Line(pg.number, section, t))
        return lines, removed

    # ---------------------------------------------------------------- main
    def extract(self, doc: ParsedDocument, today: date | None = None) -> dict:
        """Parse a document into structured candidate data: contact fields, employment, education, projects, skills, with provenance for each value."""
        lines, removed = self.segment(doc)
        body = [l for l in lines if not l.section.startswith("heading:")]
        header = [l for l in body if l.section == "header"]
        sections: dict[str, list] = {}
        for l in body:
            sections.setdefault(l.section, []).append({"page": l.page, "text": l.text})

        fields = {}
        fields["name"] = self._name(header)
        fields["email"] = self._regex_field(body, EMAIL_RE, "regex_email", 0.97)
        fields["phone"] = self._phone(header or body[:12])
        fields["linkedin"] = self._regex_field(body, LINKEDIN_RE, "regex_linkedin", 0.97)
        fields["github"] = self._regex_field(body, GITHUB_RE, "regex_github", 0.97)
        fields["portfolio"] = self._portfolio(body)
        fields["location"] = self._location(header)
        fields["summary"] = self._summary(sections, header)
        fields["headline"] = self._headline(header, fields["summary"])
        fields["claimed_years"] = self._claimed_years(sections, header)

        employment = self._employment(body)
        education = self._education(sections.get("education", []))
        projects = self._projects(sections.get("projects", []))
        skills = self.skills.extract([l for l in lines if l.section != "education"])  # degree names are not skill evidence
        for p in projects:
            p["skills"] = sorted(self.skills.extract([Line(p["page"], "projects", t) for t in [p["name"]] + p["description"]]).keys())
        for e in employment:
            e["skills"] = sorted(self.skills.extract([Line(e["page"], "experience", t) for t in e["description"] + [e["title"] or ""]]).keys())

        confs = [fields["name"]["confidence"], fields["email"]["confidence"], 1.0 if skills else 0.0,
                 max([e["confidence"] for e in education], default=0.0),
                 max([e["confidence"] for e in employment] + [0.7 if projects else 0.0])]
        parse_conf = round(0.4 * doc.quality + 0.6 * sum(confs) / len(confs), 4)
        return {
            "fields": fields, "employment": employment, "education": education, "projects": projects,
            "certifications": self._simple_list(sections.get("certifications", [])),
            "achievements": self._simple_list(sections.get("achievements", [])),
            "publications": self._simple_list(sections.get("publications", [])),
            "skills": skills, "sections": sections,
            "protected_lines_removed": removed,
            "injection_flags": detect_injection("\n".join(l.text for l in body)),
            "parse_confidence": parse_conf, "document_quality": doc.quality,
            "section_names_found": sorted({l.section for l in body if l.section != "header"}),
        }

    # ---------------------------------------------------------------- fields
    def _name(self, header):
        for i, l in enumerate(header[:6]):
            t = l.text.strip()
            words = t.split()
            if not (2 <= len(words) <= 4) or len(t) > 40 or re.search(r"[\d@:/|,]", t):
                continue
            if re.search(r"resume|curriculum|vitae|\bcv\b|engineer|developer|analyst|scientist|manager|profile", t, re.I):
                continue
            if all(re.fullmatch(r"[A-Z][A-Za-z'.\-]+|[A-Z]+", w) for w in words):
                val = t.title() if t.isupper() else t
                return _fld(val, l.page, t, "header_first_lines", 0.85 if i == 0 else 0.65)
        return _fld(None)

    def _regex_field(self, lines, rx, method, conf):
        for l in lines:
            m = rx.search(l.text)
            if m:
                return _fld(m.group(0), l.page, l.text, method, conf)
        return _fld(None)

    def _phone(self, lines):
        for l in lines:
            for m in PHONE_RE.finditer(l.text):
                digits = re.sub(r"\D", "", m.group(1))
                if 10 <= len(digits) <= 13 and not RANGE_RE.search(m.group(1)):
                    return _fld(m.group(1).strip(), l.page, l.text, "regex_phone", 0.85)
        return _fld(None)

    def _portfolio(self, lines):
        for l in lines:
            for m in URL_RE.finditer(l.text):
                u = m.group(0)
                if not re.search(r"linkedin\.com|github\.com|@", u, re.I):
                    return _fld(u.rstrip(".)"), l.page, l.text, "regex_url", 0.8)
        return _fld(None)

    def _location(self, header):
        for l in header[:8]:
            for seg in re.split(r"\s*[|•·]\s*", l.text):
                seg = re.sub(r"^(?:location|address|city)\s*:\s*", "", seg.strip(), flags=re.I)
                if EMAIL_RE.search(seg) or re.search(r"\d|http|linkedin|github", seg, re.I):
                    continue
                if re.fullmatch(r"[A-Z][A-Za-z.\- ]+,\s*[A-Z][A-Za-z.\- ]+", seg) and not TITLE_WORDS.search(seg):
                    return _fld(seg, l.page, l.text, "header_city_region_pattern", 0.7)
        return _fld(None)

    def _summary(self, sections, header):
        if sections.get("summary"):
            txt = " ".join(x["text"].lstrip("• ") for x in sections["summary"])
            return _fld(txt, sections["summary"][0]["page"], txt[:200], "section:summary", 0.9)
        for l in header:
            if len(l.text.split()) >= 15 and not EMAIL_RE.search(l.text):
                return _fld(l.text, l.page, l.text[:200], "header_paragraph", 0.55)
        return _fld(None)

    def _headline(self, header: list[Line], summary: dict) -> dict:
        """The role the candidate presents themselves as (title line under the name, else the first words of the summary).
        Used only as a display fallback when no dated job title exists (e.g. freshers); it is never counted as experience."""
        for l in header[1:6]:
            t = l.text.split("|")[0].strip(" -–—•·")
            if 1 <= len(t.split()) <= 6 and TITLE_WORDS.search(t) and not re.search(r"[\d@:/]", t) and not re.search(r"resume|curriculum|vitae", t, re.I):
                return _fld(t.title() if t.isupper() else t, l.page, l.text, "header_title_line", 0.7)
        s = summary.get("value")
        if s:
            m = HEADLINE_SUMMARY_RE.match(s.strip())
            val = " ".join(w if any(c.isupper() for c in w) else w.capitalize() for w in m.group(1).split()) if m else ""
            if val and val.lower() != "professional":      # a bare "Experienced professional" says nothing about the role
                return _fld(val, summary.get("page"), s[:160], "summary_first_clause", 0.55)
        return _fld(None)

    def _claimed_years(self, sections: dict, header: list[Line]) -> dict:
        """'5+ years of experience' written as text in the summary/header. A claim, not evidence: scored at a reduced credit."""
        texts = [(x["page"], x["text"]) for x in sections.get("summary", [])] + [(l.page, l.text) for l in header[:10]]
        best = None
        for page, txt in texts:
            for m in CLAIMED_YEARS_RE.finditer(txt):
                val = float(m.group(1) or m.group(2))
                if 0 < val <= 45 and (best is None or val > best[0]):
                    best = (val, page, txt[:200])
        return _fld(best[0], best[1], best[2], "regex_claimed_years", 0.5) if best else _fld(None)

    # ---------------------------------------------------------------- employment
    def _employment(self, body: list[Line]) -> list[dict]:
        out = []
        for secname in ("experience", "internships"):
            lines = [l for l in body if l.section == secname]
            idx = [i for i, l in enumerate(lines) if RANGE_RE.search(l.text) and not l.text.startswith("•")]
            starts = []
            for i in idx:
                rest = RANGE_RE.sub("", lines[i].text)
                rest_clean = re.sub(r"[\s|,\-–—()@]+", " ", rest).strip()
                if len(re.sub(r"[^A-Za-z]", "", rest_clean)) >= 4:
                    starts.append((i, i))      # header on the same line as the dates
                else:
                    j = i - 1
                    hdr = [lines[j]] if j >= 0 and not lines[j].text.startswith("•") and j not in idx else []
                    k = j
                    # three-line header: "Title" / "Company" / "dates" - the title sits one line above the company line
                    if (hdr and not TITLE_WORDS.search(lines[j].text) and j >= 1 and (j - 1) not in idx
                            and not lines[j - 1].text.startswith("•") and not lines[j - 1].text.rstrip().endswith(".")
                            and len(lines[j - 1].text) < 70 and TITLE_WORDS.search(lines[j - 1].text)):
                        k = j - 1
                    starts.append((k if hdr else i, i))
            for n, (hi, ri) in enumerate(starts):
                nxt = starts[n + 1][0] if n + 1 < len(starts) else len(lines)
                rline = lines[ri]
                m = RANGE_RE.search(rline.text)
                header_parts = [RANGE_RE.sub("", lines[hi].text)] if hi == ri else [l.text for l in lines[hi:ri]] + [RANGE_RE.sub("", rline.text)]
                desc_lines = lines[ri + 1: nxt]
                # an un-bulleted line right after the dates may be company/location, not a description
                extra_hdr = []
                while desc_lines and not desc_lines[0].text.startswith("•") and len(desc_lines[0].text) < 70 and len(extra_hdr) < 1 and hi != ri:
                    extra_hdr.append(desc_lines.pop(0).text)
                header = " | ".join(p for p in header_parts + extra_hdr if p.strip())
                title, company = self._title_company(header)
                s_txt, e_txt = range_bounds(m)
                s = _parse_date(s_txt)
                e = _parse_date(e_txt, end=True)
                if not s or not e:
                    continue
                precise = s.get("precision") == "month" and (e.get("current") or e.get("precision") == "month")
                typ = self._emp_type(title or "", header, secname)
                out.append({
                    "title": title, "company": company, "start": s, "end": e, "is_current": bool(e.get("current")),
                    "type": typ, "description": [d.text.lstrip("• ").strip() for d in desc_lines],
                    "date_uncertain": not precise, "page": rline.page, "evidence": rline.text[:240],
                    "method": "regex_date_range", "confidence": 0.9 if precise and title else 0.7,
                })
        return out

    @staticmethod
    def _emp_type(title, header, section):
        h = (title + " " + header).lower()
        if section == "internships" or re.search(r"\bintern(ship)?\b|\btrainee\b", h):
            return "internship"
        if re.search(r"part[\s\-]?time", h):
            return "part_time"
        if re.search(r"\bcontract\b|\bfreelance\b", h):
            return "contract"
        return "full_time"

    @staticmethod
    def _title_company(header: str):
        header = re.sub(r"\((?:remote|hybrid|on-?site|full[\s\-]?time|part[\s\-]?time|contract)[^)]*\)", "", header, flags=re.I)
        parts = [p.strip(" ,-–—") for p in re.split(r"\s*\|\s*|\s+[–—-]\s+|\s+at\s+|\s*@\s*|,\s+(?=[A-Z])", header) if p.strip(" ,-–—")]
        title = company = None
        for p in parts:
            if title is None and TITLE_WORDS.search(p):
                title = p
            elif company is None:
                company = p
        if title is None and parts:
            title = parts[0]
            company = parts[1] if len(parts) > 1 else None
        return title, company

    # ---------------------------------------------------------------- education
    def _education(self, items: list[dict]) -> list[dict]:
        out, cur = [], None
        def flush() -> None:
            nonlocal cur
            if cur:
                out.append(cur)
            cur = None
        for it in items:
            t = it["text"].lstrip("• ").strip()
            level = next(((n, lv) for n, lv, rx in LEVEL_RE if rx.search(t)), None)
            if level:
                flush()
                years = [int(y) for y in re.findall(r"\b((?:19|20)\d{2})\b", t)]
                inst = next((p.strip() for p in re.split(r"\s*[|,–—]\s*|\s+-\s+", t) if INSTITUTION_RE.search(p)), None)
                fld = re.search(r"(?:in|of)\s+([A-Z][A-Za-z &/]+?)(?:\s*[|,(–—]|$)", t)
                cur = {"degree": re.split(r"\s*[|(–—]", t)[0].strip(), "level_name": level[0], "level": level[1], "institution": inst,
                       "year": max(years) if years else None, "field": fld.group(1).strip() if fld else None,
                       "page": it["page"], "evidence": t[:240], "method": "degree_keyword_regex",
                       "confidence": 0.85 if inst or years else 0.65}
            elif cur:
                if not cur["institution"] and INSTITUTION_RE.search(t):
                    cur["institution"] = re.split(r"\s*[|,–—]\s*", t)[0]
                ys = [int(y) for y in re.findall(r"\b((?:19|20)\d{2})\b", t)]
                if ys and not cur["year"]:
                    cur["year"] = max(ys)
                cur["confidence"] = 0.85 if cur["institution"] or cur["year"] else cur["confidence"]
        flush()
        return out

    # ---------------------------------------------------------------- projects & lists
    def _projects(self, items: list[dict]) -> list[dict]:
        out, cur = [], None
        for it in items:
            t = it["text"]
            if t.startswith("•"):
                if cur is None:
                    out.append({"name": t.lstrip("• ")[:80], "description": [t.lstrip("• ")], "page": it["page"], "evidence": t[:240],
                                "method": "bullet_as_project", "confidence": 0.5})
                else:
                    cur["description"].append(t.lstrip("• "))
            else:
                cur = {"name": re.split(r"\s+[–—|]\s+|\s+-\s+", t)[0][:100], "description": ([t] if len(t) > 100 else []), "page": it["page"],
                       "evidence": t[:240], "method": "project_heading", "confidence": 0.8}
                out.append(cur)
        return out

    @staticmethod
    def _simple_list(items):
        return [{"text": i["text"].lstrip("• ").strip(), "page": i["page"]} for i in items]
