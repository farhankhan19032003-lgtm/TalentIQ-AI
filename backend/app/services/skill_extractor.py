"""Ontology-driven skill extraction with alias normalisation, section/context awareness
and explicit evidence. A keyword is *evidence of a mention*, never proof of proficiency."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from ..core.config import settings

SOFT = "Soft Skills"
_LEFT = r"(?<![A-Za-z0-9+#.\-_])"
_RIGHT = r"(?![A-Za-z0-9+#_]|\.[A-Za-z0-9])"


@dataclass
class Line:
    page: int | None
    section: str
    text: str


def _pat(aliases: list[str], flags: int):
    if not aliases:
        return None
    parts = []
    for a in sorted(aliases, key=len, reverse=True):
        parts.append(re.escape(a).replace(r"\ ", r"[\s\-]+"))
    return re.compile(_LEFT + "(?:" + "|".join(parts) + ")" + _RIGHT, flags)


class Ontology:
    def __init__(self, path: Path | None = None):
        self.path = Path(path or settings.ontology_path)
        self.reload()

    def reload(self):
        doc = json.loads(self.path.read_text(encoding="utf-8"))
        self.version = doc.get("version", "0")
        self.domains = doc.get("domains", [])
        self.skills = {s["name"]: s for s in doc["skills"]}
        self.lookup = {}
        for s in doc["skills"]:
            self.lookup[s["name"].lower()] = s["name"]
            for a in s.get("aliases", []):
                self.lookup[a.lstrip("!").lower()] = s["name"]
        self._compiled = {}
        for name, s in self.skills.items():
            ci, cs = [], []
            for a in s.get("aliases", []):
                (cs if a.startswith("!") else ci).append(a.lstrip("!"))
            bare = name
            if s.get("ambiguous"):
                bare_pat = _pat([bare], 0)           # only used in list context
                self._compiled[name] = (_pat(ci, re.I), _pat(cs, 0), bare_pat)
            elif s.get("case_sensitive"):
                self._compiled[name] = (_pat(ci, re.I), _pat(cs + [bare], 0), None)
            else:
                self._compiled[name] = (_pat(ci + [bare], re.I), _pat(cs, 0), None)

    # -- lookups ------------------------------------------------------------------
    def canonical(self, text: str) -> str | None:
        return self.lookup.get(text.strip().lower())

    def category(self, name: str) -> str:
        return self.skills.get(name, {}).get("category", "Other")

    def related(self, name: str) -> list[str]:
        return self.skills.get(name, {}).get("related", [])

    def is_soft(self, name: str) -> bool:
        return self.category(name) == SOFT

    def semantic_query(self, name: str) -> str:
        s = self.skills.get(name)
        if not s:
            return name
        return " ".join([name] + [a.lstrip("!") for a in s.get("aliases", [])] + s.get("related", []))

    def save(self, doc: dict):
        self.path.write_text(json.dumps(doc, indent=1), encoding="utf-8")
        self.reload()


_PROF_LEVEL = re.compile(r"\b(beginner|basic|familiar(?:ity)?|intermediate|proficient|advanced|expert(?:ise)?|strong|extensive)\b", re.I)
_PROF_YEARS = re.compile(r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)", re.I)
_NEG_AFTER = {"Excel": re.compile(r"\s+(?:at|in|as)\b")}  # verb "excel at ..." is not the spreadsheet
_LIST_SPLIT = re.compile(r"[,;|•/:()]+")


class SkillExtractor:
    def __init__(self, ontology: Ontology):
        self.onto = ontology

    def _snippet(self, text: str, start: int, end: int) -> str:
        t = text.strip()
        if len(t) <= 240:
            return t
        a = max(0, start - 110)
        return text[a:a + 240].strip()

    _BEFORE_Y = re.compile(r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)\s*(?:of\s+)?(?:hands-on\s+)?(?:experience\s+)?(?:with|in|using|on)?\s*$", re.I)
    _AFTER_Y = re.compile(r"^\s*[\(\[:,\-–]*\s*(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)", re.I)
    _BEFORE_L = re.compile(r"(beginner|basic|familiar(?:ity)?|intermediate|proficient|advanced|expert(?:ise)?|strong|extensive)\s+(?:(?:knowledge|experience|command)\s+)?(?:of|in|with)?\s*$", re.I)
    _AFTER_L = re.compile(r"^\s*[\(\[:\-–]\s*(beginner|basic|intermediate|proficient|advanced|expert)", re.I)

    def _proficiency(self, text: str, start: int, end: int) -> dict | None:
        """Only explicit, directly-attached statements (e.g. '5 years of Python', 'Python (Advanced)')."""
        before, after = text[:start], text[end:]
        yrs = lvl = None
        for rx, src in ((self._BEFORE_Y, before), (self._AFTER_Y, after)):
            m = rx.search(src)
            if m:
                yrs = float(m.group(1)); break
        for rx, src in ((self._BEFORE_L, before), (self._AFTER_L, after)):
            m = rx.search(src)
            if m:
                lvl = m.group(1).lower(); break
        if yrs is None and lvl is None:
            return None
        return {"level": lvl, "years": yrs, "evidence": text[max(0, start - 45): end + 45].strip()}

    def find_in_text(self, text: str, in_list_context: bool = False) -> list[tuple]:
        """Return [(canonical, alias_text, start, end)] for one line of text."""
        out = []
        items = [i.strip() for i in _LIST_SPLIT.split(text)]
        for name, (ci, cs, bare) in self.onto._compiled.items():
            for pat in (ci, cs):
                if pat:
                    for m in pat.finditer(text):
                        if name in _NEG_AFTER and _NEG_AFTER[name].match(text[m.end():]):
                            continue
                        out.append((name, m.group(0), m.start(), m.end()))
            if bare is not None:
                if name in items:
                    for m in bare.finditer(text):
                        out.append((name, m.group(0), m.start(), m.end()))
        return out

    def extract(self, lines: list[Line], extra_skills: list[str] | None = None) -> dict:
        found: dict[str, dict] = {}
        for ln in lines:
            if ln.section == "header" or not ln.text.strip():
                continue
            in_list = ln.section == "skills"
            for name, alias, s, e in self.find_in_text(ln.text, in_list):
                rec = found.setdefault(name, {"name": name, "category": self.onto.category(name), "mentions": [],
                                              "context_mentions": 0, "listed_only": True, "proficiency": None,
                                              "method": "extracted"})
                ctx = ln.section not in ("skills", "header")
                if ctx:
                    rec["context_mentions"] += 1
                    rec["listed_only"] = False
                if len(rec["mentions"]) < 6:
                    rec["mentions"].append({"page": ln.page, "section": ln.section, "snippet": self._snippet(ln.text, s, e),
                                            "alias": alias, "method": "exact" if alias.lower() == name.lower() else "synonym",
                                            "context": ctx})
                if rec["proficiency"] is None:
                    rec["proficiency"] = self._proficiency(ln.text, s, e)
        return found
