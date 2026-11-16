"""Bundled Unicode fonts: Hindi (Devanagari) in the PDF reports."""
import io

import pymupdf
import pytest

from app.core.config import COMPONENTS
from app.services import exports

HINDI_NAME = "आशा वर्मा"
HINDI_NOTE = "बहुत अच्छा इंटरव्यू। क्षत्रिय, ज्ञान, श्रेष्ठ, कि/की; द्वारा (पर्यावरण)"


def _sample_pdf(note=HINDI_NOTE, name=HINDI_NAME) -> bytes:
    comp = {k: {"score": 62.5, "status": "scored", "weight_effective": 0.2, "contribution": 12.5} for k in COMPONENTS}
    d = {"result": {"components": comp, "requirements": [{"name": "डेटा विश्लेषण", "importance": "must", "match_type": "exact", "verification": "verified", "page": 1}],
                    "explanation": {"summary": "Overall match 62.5/100.", "why_matched": ["ok"], "why_not_matched": ["-"], "missing_information": ["-"],
                                    "evidence_supporting_score": [{"requirement": "Python", "match_type": "exact", "page": 1, "verification": "verified", "text": "Python से सेवा बनाई"}],
                                    "disclaimer": "Decision-support only."}}}
    iv = {"items": [{"id": 1, "round": "technical", "interviewed_on": "2026-11-12", "interviewer": name, "job_title": None, "recommendation": "yes",
                     "ratings": {"technical": 4}, "rating_avg": 4.0, "strengths": "", "concerns": "", "notes": note}],
          "summary": {"count": 1, "avg_rating": 4.0, "avg_by_criterion": {}, "recommendations": {"strong_yes": 0, "yes": 1, "no": 0, "strong_no": 0, "undecided": 0}}}
    return exports.candidate_pdf(name, "Backend डेवलपर", d, iv)


def _fonts(pdf: bytes) -> set[str]:
    doc = pymupdf.open(stream=pdf, filetype="pdf")
    return {f[3].split("+")[-1] for p in doc for f in p.get_fonts()}


def _pixels(pdf: bytes) -> bytes:
    doc = pymupdf.open(stream=pdf, filetype="pdf")
    return b"".join(p.get_pixmap(dpi=72).samples for p in doc)


# ---- the markup helper -----------------------------------------------------------------------------------------------------------
def test_bundled_font_files_exist():
    for _, name in exports._FONT_FILES:
        f = exports.FONT_DIR / name
        assert f.is_file() and f.read_bytes()[:4] == b"\x00\x01\x00\x00", f"{name} must be a TrueType file"
    assert (exports.FONT_DIR / "OFL.txt").read_text(encoding="utf-8").count("SIL Open Font License") >= 2, "licence ships with the fonts"


def test_rich_wraps_hindi_runs_and_leaves_other_text_alone():
    assert exports._setup_fonts() is True
    assert exports._rich("plain English text") == "plain English text"
    out = exports._rich("Python में अनुभव")
    assert out == 'Python <font name="NotoSansDevanagari">में अनुभव</font>', "one run per Hindi phrase; spaces between Hindi words stay inside it"
    assert exports._rich("A क B ख").count("<font") == 2, "a Latin word ends the run"


def test_rich_keeps_attached_punctuation_in_the_same_run():
    out = exports._rich("अनुभव; ज्ञान, कि/की (अच्छा).")
    assert out == '<font name="NotoSansDevanagari">अनुभव; ज्ञान, कि/की (अच्छा).</font>'


def test_rich_never_leaves_hindi_glued_to_latin_in_one_word():
    """reportlab draws a space-free word with the font of its first fragment, so scripts must be separated by a space."""
    face = '<font name="NotoSansDevanagari">'
    assert exports._rich("Pythonमें") == f"Python {face}में</font>"
    assert exports._rich("(Kubernetes)।") == f"(Kubernetes) {face}।</font>"
    assert exports._rich("क,x") == f"{face}क,</font> x"
    assert exports._rich("क") == f"{face}क</font>", "no stray spaces at the edges of the text"
    assert exports._rich("a क b") == f"a {face}क</font> b", "existing spaces are not doubled"
    assert exports._rich("क😀") == f"{face}क?</font>", "an unsupported character becomes '?', which the Devanagari font can draw, so it stays in the run"
    assert exports._rich("क😀x") == f"{face}क?</font> x"


def test_rich_escapes_markup_and_marks_unsupported_scripts():
    assert exports._rich("a < b & c > d") == "a &lt; b &amp; c &gt; d"
    assert exports._rich("<b>क</b>").startswith("&lt;b&gt;"), "user text can never inject markup"
    assert exports._rich("日本語 العربية 👍") == "??? ??????? ?", "scripts without a bundled font show '?' rather than empty boxes"
    assert exports._rich("résumé naïve café — · ’") == "résumé naïve café — · ’", "Latin-extended and typographic characters are kept"
    assert exports._rich(None) == ""


def test_rich_bold_uses_the_bold_devanagari_face():
    assert 'name="NotoSansDevanagari-Bold"' in exports._rich("शीर्षक", bold=True)
    assert 'name="NotoSansDevanagari"' in exports._rich("शीर्षक")


def test_rich_falls_back_to_plain_escaping_when_fonts_are_unavailable(monkeypatch):
    monkeypatch.setattr(exports, "_fonts_ready", False)
    assert exports._rich("क & ख") == "क &amp; ख"
    assert exports._font() == "Helvetica" and exports._font(True) == "Helvetica-Bold"


# ---- whole PDFs ------------------------------------------------------------------------------------------------------------------
def test_hindi_pdf_embeds_both_noto_families():
    fonts = _fonts(_sample_pdf())
    assert {"NotoSans-Regular", "NotoSans-Bold", "NotoSansDevanagari-Regular", "NotoSansDevanagari-Bold"} <= fonts, fonts


def test_all_pdf_text_moves_off_helvetica_for_ordinary_latin_reports():
    latin_only = _sample_pdf(note="Plain English note.", name="Asha Verma")
    fonts = _fonts(latin_only)
    assert "NotoSans-Regular" in fonts and "NotoSans-Bold" in fonts


@pytest.mark.skipif(exports._setup_fonts() and not getattr(__import__("reportlab.pdfbase.pdfmetrics", fromlist=["x"]).getFont("NotoSansDevanagari"), "shapable", False),
                    reason="uharfbuzz is not installed, so Hindi cannot be shaped")
def test_shaping_changes_how_hindi_is_drawn(monkeypatch):
    import reportlab.pdfbase.ttfonts as ttfonts
    shaped = _pixels(_sample_pdf())
    monkeypatch.setattr(ttfonts, "uharfbuzz", None)                 # what a machine without uharfbuzz would do
    unshaped = _pixels(_sample_pdf())
    assert shaped != unshaped, "with HarfBuzz the vowel signs and conjuncts are laid out differently from the raw character order"


def test_pdf_still_builds_without_uharfbuzz_and_without_the_fonts(monkeypatch):
    import reportlab.pdfbase.ttfonts as ttfonts
    monkeypatch.setattr(ttfonts, "uharfbuzz", None)
    pdf = _sample_pdf()
    assert pdf[:5] == b"%PDF-" and "Interview notes" in pymupdf.open(stream=pdf, filetype="pdf")[0].get_text()
    monkeypatch.setattr(exports, "_fonts_ready", False)             # font files missing: Helvetica, Latin only
    pdf = _sample_pdf(note="Latin note still works", name="Asha")
    text = pymupdf.open(stream=pdf, filetype="pdf")[0].get_text()
    assert pdf[:5] == b"%PDF-" and "Latin note still works" in text


def test_extracted_text_keeps_the_latin_parts_next_to_hindi():
    text = pymupdf.open(stream=_sample_pdf("Great design sense. बहुत अच्छा. résumé"), filetype="pdf")[0].get_text()
    assert "Great design sense." in text and "résumé" in text and "Recommendation:" in text


def test_job_pdf_accepts_hindi_candidate_names_and_titles():
    run = {"algorithm_version": "2.0.0", "similarity_method": "tfidf", "n_candidates": 1}
    row = {"rank": 1, "name": HINDI_NAME, "overall": 61.0, "score_low": 61.0, "score_high": 66.0, "skill_coverage": 50.0, "relevant_years": 3.0,
           "confidence": 90, "completeness": 80, "review_status": "new"}
    pdf = exports.job_pdf("Backend डेवलपर <b>&</b>", run, [row])
    assert pdf[:5] == b"%PDF-" and "NotoSansDevanagari-Regular" in _fonts(pdf) and "NotoSansDevanagari-Bold" in _fonts(pdf)
    assert "<b>&</b>" in pymupdf.open(stream=pdf, filetype="pdf")[0].get_text(), "title markup characters are shown literally"
