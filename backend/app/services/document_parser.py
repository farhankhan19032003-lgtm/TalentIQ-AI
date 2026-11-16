"""PDF / DOCX text extraction with layout handling and per-page diagnostics.

PDF: PyMuPDF block extraction + column detection (reading order), pdfplumber fallback for
malformed files, scanned-page detection, optional Tesseract OCR, password detection.
DOCX: body-order traversal of paragraphs and tables (layout tables read column-wise).
"""
from __future__ import annotations

import io
import re
import unicodedata
from dataclasses import dataclass, field

from ..core.config import settings


class DocumentError(Exception):
    def __init__(self, code: str, message: str):
        self.code, self.message = code, message
        super().__init__(message)


@dataclass
class PageText:
    number: int | None
    text: str
    method: str
    columns: int = 1
    quality: float = 1.0
    scanned: bool = False
    warnings: list = field(default_factory=list)

    def diag(self) -> dict:
        return {"page": self.number, "chars": len(self.text), "method": self.method, "columns": self.columns,
                "quality": round(self.quality, 3), "scanned": self.scanned, "warnings": self.warnings}


@dataclass
class ParsedDocument:
    file_type: str
    pages: list
    quality: float
    ocr_used: bool = False
    warnings: list = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\f".join(p.text for p in self.pages)


_BULLETS = "•▪●◦‣➢➤■□◆◇○*·–"  # leading bullet-like glyphs
_ZERO_WIDTH = dict.fromkeys(map(ord, "​‌‍⁠﻿­"), None)


def normalize_text(text: str) -> str:
    """Unicode NFKC (fixes ligatures/full-width), strips control & zero-width chars, unifies bullets."""
    text = unicodedata.normalize("NFKC", text).translate(_ZERO_WIDTH)
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\t", " ").replace("\xa0", " ")
    text = "".join(ch for ch in text if ch == "\n" or unicodedata.category(ch)[0] != "C")
    out = []
    for line in text.split("\n"):
        line = re.sub(r"[ ]{2,}", " ", line).rstrip()
        m = re.match(rf"^\s*([{re.escape(_BULLETS)}]|-(?=\s))\s*(.*)$", line)
        if m and m.group(2):
            line = "• " + m.group(2).strip()
        out.append(line.strip() if not line.startswith("• ") else line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()


def text_quality(text: str) -> float:
    """Heuristic 0..1 quality: share of alphanumeric/space chars, no replacement chars, sane word length."""
    if not text.strip():
        return 0.0
    n = len(text)
    good = sum(ch.isalnum() or ch.isspace() or ch in ".,;:-()/@+#&%•|'\"" for ch in text) / n
    bad = text.count("�") / n
    words = text.split()
    avg = sum(map(len, words)) / max(1, len(words))
    word_ok = 1.0 if 2.5 <= avg <= 12 else 0.6
    return round(max(0.0, min(1.0, good - 5 * bad)) * word_ok, 4)


# ----------------------------------------------------------------------------- PDF
def _order_blocks(blocks: list, page_width: float) -> tuple[list, int]:
    """Return blocks in reading order and the detected column count (1 or 2).

    Two-column detection: find the x position where a right-hand column starts (>=2 blocks share that left edge in the
    25-65% band of the page); blocks ending before it are the left column, blocks starting at/after it are the right
    column, blocks crossing the gutter are spanning (header/footer) blocks."""
    if not blocks:
        return [], 1
    plain = sorted(blocks, key=lambda b: (round(b[1], 0), b[0]))
    band = [b[0] for b in blocks if 0.25 * page_width < b[0] < 0.65 * page_width]
    xr = None
    for x in sorted(band):
        if sum(1 for y in band if abs(y - x) <= 4) >= 2:
            xr = x
            break
    if xr is None:
        return plain, 1
    right_starts = [b for b in blocks if abs(b[0] - xr) <= 4]
    rest = [b for b in blocks if b not in right_starts]
    left_edge = min((b[0] for b in rest if b[2] <= xr + 3), default=None)
    if left_edge is None:
        return plain, 1
    left_starts = [b for b in rest if abs(b[0] - left_edge) <= 4 and b[2] <= xr + 3]
    if len(right_starts) < 2 or len(left_starts) < 2:
        return plain, 1
    col_top = min(b[1] for b in left_starts)   # the left column begins the body; everything above it is header
    header = sorted([b for b in blocks if b[3] <= col_top + 2], key=lambda b: (b[1], b[0]))
    body = [b for b in blocks if b not in header]
    right = [b for b in body if b[0] >= xr - 5]
    left = [b for b in body if b not in right and b[2] <= xr + 3]
    span = [b for b in body if b not in right and b not in left]
    if len(span) > 0.3 * max(1, len(body)):
        return plain, 1
    return header + sorted(left, key=lambda b: b[1]) + sorted(right, key=lambda b: b[1]) + sorted(span, key=lambda b: b[1]), 2


def _ocr_page(page) -> str:
    import pytesseract
    from PIL import Image
    pix = page.get_pixmap(dpi=200)
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    return pytesseract.image_to_string(img)


def _ocr_available() -> bool:
    if not settings.ocr_enabled:
        return False
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def parse_pdf(data: bytes) -> ParsedDocument:
    import pymupdf
    pymupdf.TOOLS.mupdf_display_errors(False)
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception:
        return _parse_pdf_fallback(data)
    if doc.needs_pass:
        raise DocumentError("password_protected", "The PDF is password-protected. Remove the password and re-upload.")
    if doc.page_count == 0:
        raise DocumentError("empty_document", "The PDF has no pages.")
    if doc.page_count > settings.max_pages:
        raise DocumentError("too_many_pages", f"The PDF has {doc.page_count} pages (limit {settings.max_pages}).")
    pages, warnings, ocr_used = [], [], False
    ocr_ok = None
    for i, page in enumerate(doc, start=1):
        try:
            blocks = [b for b in page.get_text("blocks") if b[6] == 0 and b[4].strip()]
            ordered, ncols = _order_blocks(blocks, page.rect.width)
            text = "\n".join(b[4].strip() for b in ordered)
            method = "pymupdf_blocks"
            scanned = False
            if len(text.strip()) < 30 and page.get_images():
                scanned = True
                if ocr_ok is None:
                    ocr_ok = _ocr_available()
                if ocr_ok:
                    text, method, ocr_used = _ocr_page(page), "tesseract_ocr", True
                else:
                    method = "none_scanned"
            text = normalize_text(text)
            q = text_quality(text)
            pw = []
            if scanned and not ocr_ok:
                pw.append("scanned_page_no_ocr")
            elif q < 0.5 and text:
                pw.append("low_text_quality")
            pages.append(PageText(i, text, method, ncols, q, scanned, pw))
        except Exception as e:  # one bad page must not kill the document
            pages.append(PageText(i, "", "error", 1, 0.0, False, [f"page_error:{type(e).__name__}"]))
    total_chars = sum(len(p.text) for p in pages)
    if total_chars < 40:
        if any(p.scanned for p in pages):
            raise DocumentError("scanned_no_ocr", "Scanned/image-only PDF detected and OCR is unavailable or found no text. "
                                "Install Tesseract (see README) or upload a text-based PDF.")
        raise DocumentError("no_text", "No extractable text was found in the PDF.")
    nonempty = [p for p in pages if p.text]
    quality = sum(p.quality for p in nonempty) / len(nonempty)
    if ocr_used:
        quality *= 0.85  # OCR text is inherently less reliable
        warnings.append("ocr_used")
    return ParsedDocument("pdf", pages, round(quality, 4), ocr_used, warnings)


def _parse_pdf_fallback(data: bytes) -> ParsedDocument:
    """Recovery path for malformed PDFs that PyMuPDF cannot open."""
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            pages = []
            for i, p in enumerate(pdf.pages[: settings.max_pages], start=1):
                t = normalize_text(p.extract_text() or "")
                pages.append(PageText(i, t, "pdfplumber_fallback", 1, text_quality(t), False, ["recovered_with_fallback"]))
    except Exception:
        raise DocumentError("corrupt", "The PDF is corrupted or malformed and could not be read.")
    if sum(len(p.text) for p in pages) < 40:
        raise DocumentError("corrupt", "The PDF is corrupted or malformed and no text could be recovered.")
    q = sum(p.quality for p in pages) / len(pages)
    return ParsedDocument("pdf", pages, round(q * 0.9, 4), False, ["recovered_with_fallback"])


# ----------------------------------------------------------------------------- DOCX
def parse_docx(data: bytes) -> ParsedDocument:
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    try:
        d = Document(io.BytesIO(data))
    except Exception:
        raise DocumentError("corrupt", "The DOCX file is corrupted and could not be opened.")

    def para_text(p: Paragraph) -> str:
        t = p.text.strip()
        if not t:
            return ""
        style = (p.style.name if p.style is not None else "") or ""
        if style.lower().startswith("list") and not t.startswith("•"):
            return "• " + t
        return t

    lines: list[str] = []
    for child in d.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            t = para_text(Paragraph(child, d))
            if t:
                lines.append(t)
        elif tag == "tbl":
            tbl = Table(child, d)
            rows = []
            for r in tbl.rows:
                cells = []
                cells.extend(r.cells)
                rows.append(cells)
            # layout table: any cell holding many paragraphs -> read column by column
            layout = any(len([p for p in c.paragraphs if p.text.strip()]) >= 4 for r in rows for c in r)
            if layout:
                ncols = max(len(r) for r in rows)
                done = set()
                for ci in range(ncols):
                    for r in rows:
                        if ci < len(r) and id(r[ci]._tc) not in done:
                            done.add(id(r[ci]._tc))
                            for p in r[ci].paragraphs:
                                t = para_text(p)
                                if t:
                                    lines.append(t)
            else:
                for r in rows:
                    vals, last = [], None
                    for c in r:
                        if c._tc is last:
                            continue
                        last = c._tc
                        v = " ".join(p.text.strip() for p in c.paragraphs if p.text.strip())
                        if v:
                            vals.append(v)
                    if vals:
                        lines.append(" | ".join(vals))
    text = normalize_text("\n".join(lines))
    if len(text) < 40:
        raise DocumentError("no_text", "No extractable text was found in the DOCX.")
    q = text_quality(text)
    return ParsedDocument("docx", [PageText(None, text, "python_docx", 1, q)], q, False,
                          ["docx_has_no_page_numbers", "text_boxes_not_extracted"])


def parse_document(data: bytes, kind: str) -> ParsedDocument:
    if kind == "pdf":
        return parse_pdf(data)
    if kind == "docx":
        return parse_docx(data)
    raise DocumentError("unsupported_type", "Unsupported document type.")
