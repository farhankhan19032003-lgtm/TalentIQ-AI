"""CSV / Excel / PDF exports. Spreadsheet cells are sanitised against formula injection."""
from __future__ import annotations

import csv
import io
import re
from datetime import datetime, timezone
from pathlib import Path

from openpyxl import Workbook
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from ..core.config import COMPONENTS, COMPONENT_LABELS

DISCLAIMER = "Decision-support only. Scores are not hiring probabilities; a recruiter makes every decision."


def safe_cell(v):
    if isinstance(v, str) and v[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + v
    return v


def ranking_rows(rows: list[dict]) -> tuple[list[str], list[list]]:
    head = ["Rank", "Candidate", "Email", "Latest role", "Match score", "Score range low", "Score range high", "Skill coverage %",
            "Must-have coverage %", *[COMPONENT_LABELS[k] for k in COMPONENTS], "Relevant experience (y)", "Total effective experience (y)",
            "Confidence", "Data completeness", "Review status", "Matched skills", "No-evidence skills"]
    out = []
    for r in rows:
        comp = r["components"]
        out.append([r["rank"], r["name"], r.get("email") or "", r.get("latest_role") or "", r["overall"], r["score_low"], r["score_high"],
                    r["skill_coverage"], r.get("must_have_coverage"),
                    *[("n/a" if comp[k]["status"] == "not_required" else comp[k]["score"]) for k in COMPONENTS],
                    r["relevant_years"], r["total_years"], r["confidence"], r["completeness"], r["review_status"],
                    "; ".join(r["matched_skills"]), "; ".join(r["missing_skills"])])
    return head, out


def to_csv(rows: list[dict], interviews: dict[int, list[dict]] | None = None) -> bytes:
    """interviews: candidate_id -> interview dicts adds two summary columns (count, average rating). Numbers only, never note text."""
    head, data = ranking_rows(rows)
    if interviews is not None:
        head = [*head, "Interviews", "Interview avg rating (1-5)"]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(head)
    for r, d in zip(rows, data):
        extra = list(interview_stats(interviews.get(r["candidate_id"], []))) if interviews is not None else []
        w.writerow([*[safe_cell(c) for c in d], *extra])
    return ("﻿" + buf.getvalue()).encode("utf-8")


def interview_stats(items: list[dict]) -> tuple[int, float | None]:
    """(number of interviews, mean of the per-interview average ratings) - the same figures the screen shows."""
    avgs = [i["rating_avg"] for i in items if i.get("rating_avg") is not None]
    return len(items), (round(sum(avgs) / len(avgs), 2) if avgs else None)


_IV_ROUND = {"phone_screen": "Phone screen", "technical": "Technical", "hr": "HR", "culture": "Culture fit", "final": "Final", "other": "Other"}
_IV_REC = {"strong_yes": "Strong yes", "yes": "Yes", "undecided": "Undecided", "no": "No", "strong_no": "Strong no"}
_IV_CRIT = (("technical", "Technical"), ("communication", "Communication"), ("problem_solving", "Problem solving"), ("collaboration", "Collaboration"))


def _interviews_sheet(wb: Workbook, rows: list[dict], interviews: dict[int, list[dict]], fill: PatternFill):
    """One row per interview scorecard, candidates in ranking order, newest interview first. Free text is formula-injection safe."""
    from datetime import date as _date
    ws = wb.create_sheet("Interviews")
    head = ["Candidate", "Rank", "Stage", "Round", "Date", "Interviewer", "Linked job", "Recommendation",
            *[label for _, label in _IV_CRIT], "Average (1-5)", "Strengths", "Concerns", "Notes"]
    ws.append(head)
    n_rows = 0
    for r in rows:
        for n in interviews.get(r["candidate_id"], []):
            when = None
            if n.get("interviewed_on"):
                try:
                    when = _date.fromisoformat(n["interviewed_on"])
                except ValueError:
                    when = n["interviewed_on"]
            ws.append([safe_cell(r["name"]), r["rank"], STAGE_LABEL.get(r["review_status"], r["review_status"]), _IV_ROUND.get(n["round"], n["round"]), when,
                       safe_cell(n.get("interviewer") or ""), safe_cell(n.get("job_title") or ""), _IV_REC.get(n["recommendation"], n["recommendation"]),
                       *[n["ratings"].get(k) for k, _ in _IV_CRIT], n.get("rating_avg"),
                       safe_cell(n.get("strengths") or ""), safe_cell(n.get("concerns") or ""), safe_cell(n.get("notes") or "")])
            n_rows += 1
    if not n_rows:
        ws.append(["No interviews recorded for these candidates."])
    for c in ws[1]:
        c.font, c.fill = Font(bold=True, color="FFFFFF"), fill
        c.alignment = Alignment(wrap_text=True, vertical="center")
    ws.row_dimensions[1].height = 32
    widths = [26, 7, 15, 14, 12, 18, 24, 16, 11, 14, 15, 15, 12, 38, 38, 55]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    if n_rows:
        last = ws.max_row
        for row in ws.iter_rows(min_row=2, max_row=last):
            row[4].number_format = "yyyy-mm-dd"
            for c in row[8:13]:
                c.alignment = Alignment(horizontal="center", vertical="top")
            row[12].number_format = "0.0"
            for c in row[13:16]:
                c.alignment = Alignment(wrap_text=True, vertical="top")
            for c in row[:8]:
                c.alignment = Alignment(vertical="top")
        ws.conditional_formatting.add(f"I2:M{last}", ColorScaleRule(start_type="num", start_value=1, start_color="FFFFFF", end_type="num", end_value=5, end_color="F5B942"))
        ws.auto_filter.ref = f"A1:P{last}"
    ws.freeze_panes = "B2"


def to_excel(rows: list[dict], run: dict, requirements: list[dict], interviews: dict[int, list[dict]] | None = None,
             interviews_omitted: str | None = None) -> bytes:
    """interviews: candidate_id -> interview dicts adds an 'Interviews' sheet and two summary columns; interviews_omitted: a reason to print instead."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Ranking"
    head, data = ranking_rows(rows)
    if interviews is not None:
        head = [*head, "Interviews", "Interview avg rating (1-5)"]
    ws.append(head)
    for r, d in zip(rows, data):
        extra = list(interview_stats(interviews.get(r["candidate_id"], []))) if interviews is not None else []
        ws.append([*[safe_cell(c) for c in d], *extra])
    if interviews is not None:
        for row in ws.iter_rows(min_row=2, min_col=len(head), max_col=len(head)):
            row[0].number_format = "0.0"
    fill = PatternFill("solid", fgColor="1E3A8A")
    for c in ws[1]:
        c.font, c.fill = Font(bold=True, color="FFFFFF"), fill
    for i in range(1, len(head) + 1):
        ws.column_dimensions[get_column_letter(i)].width = 18
    ws.freeze_panes = "C2"
    if interviews is not None:
        _interviews_sheet(wb, rows, interviews, fill)
    sm = wb.create_sheet("Skill matrix")
    names = [r["name"] for r in requirements if r["importance"] in ("must", "preferred")]
    sm.append(["Candidate", *names])
    for r in rows:
        mt = {x["name"]: x["match_type"] for x in r["requirements"]}
        sm.append([safe_cell(r["name"]), *[mt.get(n, "") for n in names]])
    for c in sm[1]:
        c.font, c.fill = Font(bold=True, color="FFFFFF"), fill
    info = wb.create_sheet("Run info")
    for k, v in run.items():
        info.append([k, str(v)])
    if interviews_omitted:
        info.append(["interview notes", interviews_omitted])
    elif interviews is not None:
        info.append(["interview notes", "The 'Interviews' sheet lists scorecards written by interviewers. They are human opinions and never part of the match score."])
    info.append(["disclaimer", DISCLAIMER])
    info.column_dimensions["A"].width = 24
    info.column_dimensions["B"].width = 90
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


STAGE_LABEL = {"new": "New", "reviewed": "Reviewed", "in_review": "Reviewed", "shortlisted": "Shortlisted", "interview": "Interview",
               "on_hold": "On hold", "not_progressing": "Not progressing"}


def matrix_excel(jobs: list[dict], order_ids: list[int] | None = None, blind: bool = False,
                 interviews: dict[int, list[dict]] | None = None) -> bytes:
    """Talent matrix workbook: every candidate scored against every job.

    jobs: [{"id", "title", "run": run_info dict, "rows": rows_for_run(...) list}] (only jobs that have a ranking run).
    order_ids: candidate ids in the order to export (mirrors the on-screen filter + sort); None = best score first.
    Emails and phone numbers are intentionally never included. Cells are sanitised against formula injection.
    """
    people: dict[int, dict] = {}
    for j in jobs:
        for r in j["rows"]:
            p = people.setdefault(r["candidate_id"], {"id": r["candidate_id"], "name": r["name"], "role": r.get("latest_role") or "",
                                                       "stage": STAGE_LABEL.get(r["review_status"], r["review_status"]), "scores": {}, "ranks": {}})
            p["scores"][j["id"]] = r["overall"]
            p["ranks"][j["id"]] = r["rank"]
    for p in people.values():
        p["best"] = max(p["scores"].items(), key=lambda kv: kv[1]) if p["scores"] else None
        p["strong"] = sum(1 for s in p["scores"].values() if s >= 50)
    if order_ids:
        ordered = [people[i] for i in dict.fromkeys(order_ids) if i in people]
    else:
        ordered = sorted(people.values(), key=lambda p: (-(p["best"][1] if p["best"] else -1), p["name"]))
    title = {j["id"]: j["title"] for j in jobs}

    header_fill = PatternFill("solid", fgColor="1E3A8A")
    header_font = Font(bold=True, color="FFFFFF")

    def style_header(ws, wrap=True):
        for c in ws[1]:
            c.font, c.fill = header_font, header_fill
            c.alignment = Alignment(wrap_text=wrap, vertical="center", horizontal="center" if c.column > 3 else "left")
        ws.row_dimensions[1].height = 34

    wb = Workbook()
    ws = wb.active
    ws.title = "Talent matrix"
    iv_cols = ["Interviews", "Interview avg rating (1-5)"] if interviews is not None else []
    head = ["Candidate", "Latest role", "Stage", *[safe_cell(j["title"]) for j in jobs], "Best fit job", "Best score", "Jobs scoring 50+", *iv_cols]
    ws.append(head)
    for p in ordered:
        ws.append([safe_cell(p["name"]), safe_cell(p["role"]), p["stage"],
                   *[round(p["scores"][j["id"]], 1) if j["id"] in p["scores"] else None for j in jobs],
                   safe_cell(title[p["best"][0]]) if p["best"] else "", round(p["best"][1], 1) if p["best"] else None, p["strong"],
                   *(interview_stats(interviews.get(p["id"], [])) if interviews is not None else ())])
    style_header(ws)
    first_job_col, last_job_col = 4, 3 + len(jobs)
    last_row = max(ws.max_row, 2)
    if jobs:
        rng = f"{get_column_letter(first_job_col)}2:{get_column_letter(last_job_col)}{last_row}"
        ws.conditional_formatting.add(rng, ColorScaleRule(start_type="num", start_value=0, start_color="F3F0FF", end_type="num", end_value=100, end_color="8B7BF5"))
        for row in ws.iter_rows(min_row=2, min_col=first_job_col, max_col=last_job_col + 2):
            for c in row:
                c.number_format = "0.0"
                c.alignment = Alignment(horizontal="center")
    ws.column_dimensions["A"].width = 26
    ws.column_dimensions["B"].width = 28
    ws.column_dimensions["C"].width = 16
    for i in range(first_job_col, last_job_col + 1):
        ws.column_dimensions[get_column_letter(i)].width = 16
    ws.column_dimensions[get_column_letter(last_job_col + 1)].width = 28
    ws.column_dimensions[get_column_letter(last_job_col + 2)].width = 12
    ws.column_dimensions[get_column_letter(last_job_col + 3)].width = 16
    last_col = last_job_col + 3 + len(iv_cols)
    if iv_cols:
        ws.column_dimensions[get_column_letter(last_job_col + 4)].width = 12
        ws.column_dimensions[get_column_letter(last_job_col + 5)].width = 18
        for row in ws.iter_rows(min_row=2, min_col=last_job_col + 4, max_col=last_col):
            for c in row:
                c.alignment = Alignment(horizontal="center")
            row[1].number_format = "0.0"
    ws.freeze_panes = "D2"
    ws.auto_filter.ref = f"A1:{get_column_letter(last_col)}{last_row}"

    rk = wb.create_sheet("Ranks")
    rk.append(["Candidate", *[safe_cell(j["title"]) for j in jobs]])
    for p in ordered:
        rk.append([safe_cell(p["name"]), *[p["ranks"].get(j["id"]) for j in jobs]])
    style_header(rk)
    rk.column_dimensions["A"].width = 26
    for i in range(2, len(jobs) + 2):
        rk.column_dimensions[get_column_letter(i)].width = 16
    rk.freeze_panes = "B2"

    tp = wb.create_sheet("Top picks")
    tp.append(["Job", "Top candidate", "Top score", "Candidates ranked", "Average score", "Scoring 70+"])
    for j in jobs:
        rows = j["rows"]
        top = max(rows, key=lambda r: r["overall"]) if rows else None
        avg = round(sum(r["overall"] for r in rows) / len(rows), 1) if rows else None
        tp.append([safe_cell(j["title"]), safe_cell(top["name"]) if top else "", round(top["overall"], 1) if top else None, len(rows), avg,
                   sum(1 for r in rows if r["overall"] >= 70)])
    style_header(tp)
    for col, w in zip("ABCDEF", (30, 26, 12, 18, 14, 12)):
        tp.column_dimensions[col].width = w

    info = wb.create_sheet("Info")
    info.append(["Generated (UTC)", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")])
    info.append(["Blind screening", "on: names are masked" if blind else "off"])
    info.append(["Candidates exported", len(ordered)])
    info.append(["Scope", "Filtered and sorted as shown on the Talent matrix page" if order_ids else "All candidates, best score first"])
    for j in jobs:
        run = j["run"]
        info.append([safe_cell(j["title"]), f"run #{run['run_id']} · algorithm v{run['algorithm_version']} · {run['similarity_method']} · {run['created_at']}"])
    info.append(["Contact details", "Emails and phone numbers are intentionally not included in this export."])
    if interviews is not None:
        info.append(["Interviews", "Only the number of interviews and their average rating are shown here; interview text is never part of this export."])
    info.append(["Stage", "A candidate's stage is shared across jobs; scores are per job."])
    info.append(["Disclaimer", DISCLAIMER])
    info.column_dimensions["A"].width = 26
    info.column_dimensions["B"].width = 100
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _pdf_doc(buf):
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate
    return SimpleDocTemplate(buf, pagesize=A4, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)


def _esc(s) -> str:
    return str(s if s is not None else "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ---- fonts: Noto Sans (Latin/Greek/Cyrillic) + Noto Sans Devanagari, bundled so PDFs can show Hindi offline -------------------------
FONT_DIR = Path(__file__).resolve().parents[1] / "assets" / "fonts"
_FONT_FILES = (("NotoSans", "NotoSans-Regular.ttf"), ("NotoSans-Bold", "NotoSans-Bold.ttf"), ("NotoSans-Italic", "NotoSans-Italic.ttf"),
               ("NotoSansDevanagari", "NotoSansDevanagari-Regular.ttf"), ("NotoSansDevanagari-Bold", "NotoSansDevanagari-Bold.ttf"))
_fonts_ready: bool | None = None
_covered_cache: set[int] | None = None


def _setup_fonts() -> bool:
    """Register the bundled fonts with reportlab once. False (Helvetica fallback, Latin only) if a font file is missing or unreadable."""
    global _fonts_ready
    if _fonts_ready is None:
        try:
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            for name, file in _FONT_FILES:
                pdfmetrics.registerFont(TTFont(name, str(FONT_DIR / file)))
            pdfmetrics.registerFontFamily("NotoSans", normal="NotoSans", bold="NotoSans-Bold", italic="NotoSans-Italic", boldItalic="NotoSans-Bold")
            pdfmetrics.registerFontFamily("NotoSansDevanagari", normal="NotoSansDevanagari", bold="NotoSansDevanagari-Bold",
                                          italic="NotoSansDevanagari", boldItalic="NotoSansDevanagari-Bold")
            _fonts_ready = True
        except Exception:                       # never let a font problem stop a report from being produced
            _fonts_ready = False
    return _fonts_ready


def _font(bold: bool = False) -> str:
    return ("NotoSans-Bold" if bold else "NotoSans") if _setup_fonts() else ("Helvetica-Bold" if bold else "Helvetica")


def _covered(ch: str) -> bool:
    """True if one of the two bundled fonts has a glyph for the character."""
    global _covered_cache
    if _covered_cache is None:
        from reportlab.pdfbase import pdfmetrics
        _covered_cache = set(pdfmetrics.getFont("NotoSans").face.charToGlyph) | set(pdfmetrics.getFont("NotoSansDevanagari").face.charToGlyph)
    return ord(ch) in _covered_cache


_DEVA = "ऀ-ॿ᳐-᳿꣠-ꣿ‌‍"
_ATTACHED = r",;:/.!?()\-'\""      # ASCII punctuation touching a Hindi word stays in the same run (the Devanagari font has these glyphs);
                                    # mixing two fonts inside one word made reportlab draw the wrong glyph
_LEADING = r"(\"'"                  # opening bracket / quote touching the front of a Hindi word
_WORD = f"[{_LEADING}]*[{_DEVA}][{_DEVA}{_ATTACHED}]*"
_DEVA_RUN = re.compile(f"{_WORD}(?: +{_WORD})*")


def _rich(s, bold: bool = False) -> str:
    """Escaped Paragraph markup in which Devanagari runs use the Devanagari font (shaped by HarfBuzz when uharfbuzz is installed).
    `bold=True` is for text inside bold styles such as headings, where a font tag would otherwise drop the weight.
    Characters neither bundled font can draw (Arabic, CJK, emoji, ...) become '?' instead of empty boxes."""
    text = _esc(s)
    if not _setup_fonts():
        return text
    text = "".join(ch if (ch in "\n\r\t" or ord(ch) < 128 or _covered(ch)) else "?" for ch in text)
    face = "NotoSansDevanagari-Bold" if bold else "NotoSansDevanagari"

    def wrap(m):
        # reportlab draws a whole space-free word with the font of its first fragment, so a Hindi run glued to Latin text
        # ("Pythonमें", "(Kubernetes)।") would lose glyphs. A space between the scripts keeps every word in a single font.
        s = m.string
        before = " " if m.start() > 0 and not s[m.start() - 1].isspace() else ""
        after = " " if m.end() < len(s) and not s[m.end()].isspace() else ""
        return f'{before}<font name="{face}">{m.group(0)}</font>{after}'

    return _DEVA_RUN.sub(wrap, text)


def _pdf_styles():
    """reportlab's sample stylesheet, moved to Noto Sans with complex-script shaping switched on (when the fonts are available)."""
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    st = getSampleStyleSheet()
    if _setup_fonts():
        swap = {"Helvetica": "NotoSans", "Helvetica-Bold": "NotoSans-Bold", "Helvetica-Oblique": "NotoSans-Italic", "Helvetica-BoldOblique": "NotoSans-Bold"}
        for s in st.byName.values():
            if isinstance(s, ParagraphStyle):
                s.fontName = swap.get(s.fontName, s.fontName)
                s.bulletFontName = swap.get(s.bulletFontName, s.bulletFontName)
                s.shaping = 1
    return st


def _cell(text, st, size: int = 8):
    """A table cell that can carry Hindi (plain strings in a Table cannot switch fonts)."""
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Paragraph
    return Paragraph(_rich(text), ParagraphStyle("cell", parent=st["Normal"], fontSize=size, leading=size + 2))


def _table_base() -> list:
    from reportlab.lib import colors
    return [("FONTNAME", (0, 0), (-1, -1), _font()), ("FONTNAME", (0, 0), (-1, 0), _font(True)),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 8), ("GRID", (0, 0), (-1, -1), 0.25, colors.grey)]


def job_pdf(job_title: str, run: dict, rows: list[dict]) -> bytes:
    from reportlab.lib import colors
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle
    st = _pdf_styles()
    buf = io.BytesIO()
    doc = _pdf_doc(buf)
    el = [Paragraph("TalentIQ AI - Screening Report", st["Title"]), Paragraph(_rich(job_title, True), st["Heading2"]),
          Paragraph(f"Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC | Algorithm v{run['algorithm_version']} | Similarity: {_esc(run['similarity_method'])} | "
                    f"Candidates: {run['n_candidates']}", st["Normal"]), Spacer(1, 10)]
    data = [["#", "Candidate", "Score", "Range", "Skills %", "Rel. exp (y)", "Conf.", "Compl.", "Status"]]
    for r in rows:
        data.append([r["rank"], _cell(r["name"][:28], st), f"{r['overall']:.1f}", f"{r['score_low']:.0f}-{r['score_high']:.0f}", r["skill_coverage"],
                     f"{r['relevant_years']:.1f}", f"{r['confidence']:.0f}", f"{r['completeness']:.0f}", r["review_status"]])
    t = Table(data, repeatRows=1)
    t.setStyle(TableStyle([*_table_base(), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")])]))
    el += [t, Spacer(1, 10), Paragraph(DISCLAIMER, st["Italic"])]
    doc.build(el)
    return buf.getvalue()


_ROUND_LABEL = {"phone_screen": "Phone screen", "technical": "Technical", "hr": "HR", "culture": "Culture fit", "final": "Final", "other": "Other"}
_REC_LABEL = {"strong_yes": "Strong yes", "yes": "Yes", "undecided": "Undecided", "no": "No", "strong_no": "Strong no"}
_CRIT_LABEL = {"technical": "Technical", "communication": "Communication", "problem_solving": "Problem solving", "collaboration": "Collaboration"}


def _one_decimal(x: float) -> str:
    """Round half up (3.25 -> 3.3) so the PDF shows the same figure as the screen; Python's f"{x:.1f}" rounds half to even."""
    from decimal import ROUND_HALF_UP, Decimal
    return str(Decimal(str(x)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def _multiline(s) -> str:
    return _rich(s).replace("\r\n", "\n").replace("\n", "<br/>")


def _interview_flow(iv: dict, st) -> list:
    """Interview notes section of the candidate PDF. All free text is escaped; nothing here feeds the match score."""
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import KeepTogether, Paragraph, Spacer, Table, TableStyle
    out = [Spacer(1, 8), Paragraph("Interview notes", st["Heading3"]),
           Paragraph("Written by interviewers. These are human opinions: they are not part of the match score and nothing is decided automatically.", st["Italic"])]
    items, s = iv["items"], iv["summary"]
    if not items:
        return out + [Paragraph("No interviews recorded.", st["Normal"])]
    tally = ", ".join(f"{s['recommendations'][k]} {_REC_LABEL[k].lower()}" for k in _REC_LABEL if s["recommendations"].get(k))
    t = Table([["Interviews", "Average rating", "Interviewers said"],
               [str(s["count"]), "-" if s["avg_rating"] is None else f"{_one_decimal(s['avg_rating'])} / 5", tally or "-"]])
    t.setStyle(TableStyle(_table_base()))
    out += [Spacer(1, 4), t, Spacer(1, 6)]
    small = ParagraphStyle("iv_small", parent=st["Normal"], fontSize=9, leading=12)
    for n in items:
        head = f"<b>{_rich(_ROUND_LABEL.get(n['round'], n['round']))}</b> | {_rich(n['interviewed_on'] or 'no date')}"
        if n["interviewer"]:
            head += f" | {_rich(n['interviewer'])}"
        if n.get("job_title"):
            head += f" | {_rich(n['job_title'])}"
        head += f" | Recommendation: <b>{_rich(_REC_LABEL.get(n['recommendation'], n['recommendation']))}</b>"
        block = [Paragraph(head, st["Normal"])]
        rated = [f"{_CRIT_LABEL[k]} {n['ratings'][k]}/5" for k in _CRIT_LABEL if k in n["ratings"]]
        if rated:
            block.append(Paragraph("Ratings: " + ", ".join(rated) + (f" (average {_one_decimal(n['rating_avg'])} / 5)" if n["rating_avg"] is not None else ""), small))
        for label, key in (("Strengths", "strengths"), ("Concerns", "concerns"), ("Notes", "notes")):
            if n[key]:
                block.append(Paragraph(f"<b>{label}:</b> {_multiline(n[key])}", small))
        block.append(Spacer(1, 6))
        out.append(KeepTogether(block))
    return out


def candidate_pdf(name: str, job_title: str, d: dict, interviews: dict | None = None, interviews_omitted: str | None = None) -> bytes:
    """interviews: {"items": [...], "summary": {...}} to include the interview notes section; interviews_omitted: a reason to print instead."""
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle
    st = _pdf_styles()
    buf = io.BytesIO()
    doc = _pdf_doc(buf)
    r = d["result"]
    el = [Paragraph("TalentIQ AI - Candidate Report", st["Title"]), Paragraph(f"{_rich(name, True)} - {_rich(job_title, True)}", st["Heading2"]),
          Paragraph(_rich(r["explanation"]["summary"]), st["Normal"]), Spacer(1, 8), Paragraph("Score breakdown", st["Heading3"])]
    data = [["Component", "Score", "Eff. weight", "Points", "Status"]]
    for k in COMPONENTS:
        c = r["components"][k]
        data.append([COMPONENT_LABELS[k], "n/a" if c["status"] == "not_required" else f"{c['score']:.1f}",
                     "-" if c["weight_effective"] is None else f"{c['weight_effective'] * 100:.1f}%",
                     "-" if c["contribution"] is None else f"{c['contribution']:.2f}", c["status"]])
    t = Table(data)
    t.setStyle(TableStyle(_table_base()))
    el += [t, Spacer(1, 8), Paragraph("Skill evidence", st["Heading3"])]
    data = [["Requirement", "Importance", "Match", "Verification", "Page"]]
    for q in r["requirements"]:
        data.append([_cell(q["name"], st), q["importance"], q["match_type"], q["verification"], q["page"] or "-"])
    t = Table(data, repeatRows=1)
    t.setStyle(TableStyle(_table_base()))
    el.append(t)
    for title, key in (("Why this candidate matched", "why_matched"), ("Requirements without full evidence", "why_not_matched"), ("Missing information", "missing_information")):
        el.append(Paragraph(title, st["Heading3"]))
        for line in r["explanation"][key] or ["-"]:
            el.append(Paragraph("• " + _rich(line), st["Normal"]))
    el += [Spacer(1, 8), Paragraph("Evidence snippets (verbatim from resume)", st["Heading3"])]
    for e in r["explanation"]["evidence_supporting_score"][:25]:
        el.append(Paragraph(f"<b>{_rich(e['requirement'])}</b> [{e['match_type']}, p.{e['page'] or '-'}, {e['verification']}]: {_rich((e['text'] or '')[:300])}", st["Normal"]))
    if interviews is not None:
        el += _interview_flow(interviews, st)
    elif interviews_omitted:
        el += [Spacer(1, 8), Paragraph("Interview notes", st["Heading3"]), Paragraph(_rich(interviews_omitted), st["Italic"])]
    el += [Spacer(1, 10), Paragraph(_rich(r["explanation"]["disclaimer"]), st["Italic"])]
    doc.build(el)
    return buf.getvalue()
