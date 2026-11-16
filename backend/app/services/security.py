"""Upload hardening: extension + magic-byte validation, size/zip-bomb limits,
randomised storage names, path-traversal-safe storage, prompt-injection flagging."""
import hashlib
import io
import re
import unicodedata
import uuid
import zipfile
from pathlib import Path

from ..core.config import settings
from ..core.errors import AppError

ALLOWED_EXT = {".pdf": "pdf", ".docx": "docx"}
MAX_DOCX_UNCOMPRESSED = 60 * 1024 * 1024
ACTIVE_PDF_MARKERS = [b"/JavaScript", b"/JS ", b"/JS(", b"/Launch", b"/EmbeddedFile", b"/OpenAction"]

INJECTION_PATTERNS = [
    r"ignore (all |any )?(previous|prior|above) (instructions|prompts)",
    r"disregard (the )?(previous|above|system)",
    r"you are (now )?an? (ai|assistant|language model)",
    r"(rank|score|rate) (me|this candidate) (first|highest|100)",
    r"system prompt",
]
_inj = re.compile("|".join(INJECTION_PATTERNS), re.I)


def sanitize_filename(name: str) -> str:
    """Display-only filename. It is NEVER used to build a filesystem path."""
    name = unicodedata.normalize("NFKC", name or "unnamed")
    name = name.replace("\\", "/").split("/")[-1]
    name = re.sub(r"[^\w.\- ]", "_", name).strip(" .") or "unnamed"
    return name[:120]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class UploadRejected(Exception):
    def __init__(self, code: str, message: str):
        self.code, self.message = code, message
        super().__init__(message)


def validate_upload(filename: str, data: bytes) -> str:
    """Return 'pdf' or 'docx' or raise UploadRejected. Checks extension, size, real signature."""
    ext = Path(filename or "").suffix.lower()
    if ext not in ALLOWED_EXT:
        raise UploadRejected("unsupported_type", f"Unsupported file type '{ext or 'none'}'. Only PDF and DOCX are accepted.")
    if not data:
        raise UploadRejected("empty_file", "The file is empty.")
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise UploadRejected("file_too_large", f"File exceeds the {settings.max_upload_mb:g} MB limit.")
    kind = ALLOWED_EXT[ext]
    if kind == "pdf":
        if b"%PDF-" not in data[:1024]:
            raise UploadRejected("signature_mismatch", "File content is not a PDF (signature check failed).")
        head = data
        for marker in ACTIVE_PDF_MARKERS:
            if marker in head:
                raise UploadRejected("active_content", "PDF contains active content (JavaScript/launch/embedded files) and was rejected.")
    else:
        if not data.startswith(b"PK"):
            raise UploadRejected("signature_mismatch", "File content is not a DOCX (signature check failed).")
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                names = set(z.namelist())
                if "word/document.xml" not in names:
                    raise UploadRejected("signature_mismatch", "ZIP archive is not a Word document.")
                total = sum(i.file_size for i in z.infolist())
                if total > MAX_DOCX_UNCOMPRESSED or (len(data) and total / len(data) > 200):
                    raise UploadRejected("zip_bomb", "Document expands to an unsafe size and was rejected.")
                if any(n.startswith("/") or ".." in Path(n).parts for n in names):
                    raise UploadRejected("unsafe_archive", "Archive contains unsafe paths.")
                if "word/vbaProject.bin" in names:
                    raise UploadRejected("active_content", "Document contains macros and was rejected.")
        except zipfile.BadZipFile:
            raise UploadRejected("corrupt", "The DOCX archive is corrupted.")
    return kind


def store_file(data: bytes, kind: str) -> str:
    """Store under a random server-generated name; returns that name (no client input in path)."""
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    stored = f"{uuid.uuid4().hex}.{kind}"
    path = (settings.upload_dir / stored).resolve()
    if settings.upload_dir.resolve() not in path.parents:
        raise AppError("Invalid storage path", 500, "storage_error")
    path.write_bytes(data)
    return stored


def read_stored(stored: str) -> bytes | None:
    path = (settings.upload_dir / Path(stored).name).resolve()
    if settings.upload_dir.resolve() not in path.parents or not path.exists():
        return None
    return path.read_bytes()


def delete_stored(stored: str | None) -> bool:
    if not stored:
        return False
    path = (settings.upload_dir / Path(stored).name).resolve()
    if settings.upload_dir.resolve() in path.parents and path.exists():
        path.unlink()
        return True
    return False


def detect_injection(text: str) -> list[str]:
    """Resume text is untrusted DATA. We never execute it; we only flag instruction-like content."""
    return sorted({m.group(0).lower() for m in _inj.finditer(text or "")})
