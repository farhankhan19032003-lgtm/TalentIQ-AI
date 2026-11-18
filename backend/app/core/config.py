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

# --- Scoring knobs (every number the score depends on lives here; docs/ALGORITHM.md explains each one) ---------------
SCORING = {
    "must_weight": 1.0,             # requirement weight of a must-have skill
    "preferred_weight": 0.5,        # ... of a preferred (good-to-have) skill
    "credit_context": 1.0,          # skill used in experience/projects text
    "credit_listed_only": 0.85,     # skill only named in a skills list
    "partial_credit": 0.35,         # a related (same-family / parent) skill instead of the requested one
    "semantic_credit_min": 0.10,    # skill not named but a resume line is similar enough ...
    "semantic_credit_max": 0.25,    # ... credit grows linearly with similarity up to this cap
    "rel_fit_min": 0.25,            # a role is 'relevant experience' if it shows >= 25 % of the weighted requirements ...
    "rel_fit_min_title": 0.15,      # ... or >= 15 % when its job title matches the JD title
    "claimed_years_credit": 0.6,    # "5+ years" stated in text but no dated roles: credited at 60 % (unverifiable)
    "high_match": 70.0,             # UI/analytics threshold for 'high match' (display only, never used to reject)
    # Components that carry no resume evidence AND are low-stakes are left out of the point estimate (the other weights are
    # renormalised) instead of being scored 0; the score range still shows the 0..100 possibilities. Technical, semantic,
    # experience and education stay at 0 when unverified, so an empty/unreadable resume can never score well.
    "renormalise_unverified": ["project_domain"],
}
# Cosine -> 0..100 calibration. 'doc' maps whole-narrative similarity, 'resp' maps (JD responsibility, best resume line)
# similarity. Sentence-to-sentence cosines are systematically lower than document-to-document ones, so they get their own
# range. Ranges are anchored on the synthetic benchmark (see docs/ALGORITHM.md "Calibration"), not learned from real data.
CALIBRATION = {
    "minilm": {"doc": (0.25, 0.75), "resp": (0.15, 0.45), "evidence_threshold": 0.50},
    "tfidf": {"doc": (0.02, 0.40), "resp": (0.02, 0.30), "evidence_threshold": 0.28},
}
HIGH_SCORE = SCORING["high_match"]


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
