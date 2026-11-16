"""Central configuration. Everything is overridable through environment variables."""
import os
from dataclasses import dataclass
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
ROOT_DIR = BACKEND_DIR.parent

ALGORITHM_VERSION = "2.0.0"

# Component keys are stable identifiers used in the DB, API and UI.
COMPONENTS = ["technical_skills", "semantic_relevance", "relevant_experience", "education", "project_domain"]
DEFAULT_WEIGHTS = {
    "technical_skills": 0.40,
    "semantic_relevance": 0.25,
    "relevant_experience": 0.20,
    "education": 0.10,
    "project_domain": 0.05,
}
COMPONENT_LABELS = {
    "technical_skills": "Technical Skill Match",
    "semantic_relevance": "Semantic Relevance",
    "relevant_experience": "Relevant Experience",
    "education": "Education & Qualification",
    "project_domain": "Project & Domain Relevance",
}


def _bool(name: str, default: bool) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Settings:
    database_url: str
    upload_dir: Path
    max_upload_mb: float
    max_pages: int
    max_batch_files: int
    embedding_backend: str  # auto | minilm | tfidf
    embedding_model: str
    embedding_model_dir: Path   # local copy of the model for the NumPy runtime (see scripts/fetch_minilm.py)
    api_key: str
    retention_days: int
    store_original_files: bool
    cors_origins: list
    ontology_path: Path
    ocr_enabled: bool


def load_settings() -> Settings:
    default_db = f"sqlite:///{(BACKEND_DIR / 'talentiq.db').as_posix()}"
    return Settings(
        database_url=os.environ.get("DATABASE_URL", default_db),
        upload_dir=Path(os.environ.get("UPLOAD_DIR", str(BACKEND_DIR / "storage" / "uploads"))),
        max_upload_mb=float(os.environ.get("MAX_UPLOAD_MB", "5")),
        max_pages=int(os.environ.get("MAX_PDF_PAGES", "30")),
        max_batch_files=int(os.environ.get("MAX_BATCH_FILES", "60")),
        embedding_backend=os.environ.get("EMBEDDING_BACKEND", "auto").lower(),   # auto: MiniLM if available, else TF-IDF (reason is shown)
        embedding_model=os.environ.get("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
        embedding_model_dir=Path(os.environ.get("EMBEDDING_MODEL_DIR", str(BACKEND_DIR / "storage" / "models" / "all-MiniLM-L6-v2"))),
        api_key=os.environ.get("API_KEY", ""),
        retention_days=int(os.environ.get("RETENTION_DAYS", "0")),  # 0 = keep until deleted
        store_original_files=_bool("STORE_ORIGINAL_FILES", True),
        cors_origins=[o.strip() for o in os.environ.get(
            "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()],
        ontology_path=Path(os.environ.get("ONTOLOGY_PATH", str(BACKEND_DIR / "app" / "data" / "skill_ontology.json"))),
        ocr_enabled=_bool("OCR_ENABLED", True),
    )


settings = load_settings()
