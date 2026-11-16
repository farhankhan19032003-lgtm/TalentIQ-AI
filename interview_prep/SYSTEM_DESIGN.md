# System design (interview summary)

Full detail: `../docs/ARCHITECTURE.md`. One-paragraph version:

A React SPA talks to a FastAPI backend over `/api`. Uploads pass a security gate, are parsed (PyMuPDF/pdfplumber/python-docx, optional Tesseract), turned into a structured profile with evidence for each field, and stored through SQLAlchemy (SQLite by default, Alembic migrations). A job description is analysed into editable requirements. A matching run scores every candidate on five components, ranks deterministically, computes rank sensitivity, builds an explanation, and persists everything with the job snapshot, weights and algorithm version so a result can be reproduced later.

## Why these choices
- **No LLM / no paid API / CPU only:** the brief requires an 8 GB laptop; rule-based extraction plus an ontology is deterministic and every output can be traced to text.
- **Synchronous processing:** 41 files parse in ≈ 1.2 s and 35 candidates match in ≈ 0.4 s per JD, so no job queue was built. This would not scale to thousands of resumes (see LIMITATIONS).
- **Evidence-first data model:** `EvidenceItem` stores the snippet, page, section and verification status per requirement; the UI and PDF report render from it.
- **Separation of concerns:** services are pure functions where possible (`compute_overall`, `rank`, `experience_analyzer`), which made independent verification and unit testing straightforward.

## Scaling story (what I would do next, not what exists)
Move parsing/matching to a worker queue, add Postgres + connection pooling, cache embeddings in a vector store, add per-tenant auth.
