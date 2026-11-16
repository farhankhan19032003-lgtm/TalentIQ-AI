from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.database import Base


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    role: Mapped[str | None] = mapped_column(String(200))
    category: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text)
    min_experience_years: Mapped[float | None] = mapped_column(Float)
    preferred_experience_years: Mapped[float | None] = mapped_column(Float)
    education_level: Mapped[int | None] = mapped_column(Integer)           # 2 diploma .. 5 phd
    preferred_education_level: Mapped[int | None] = mapped_column(Integer)
    requirements: Mapped[list] = mapped_column(JSON, default=list)          # recruiter-editable
    analysis: Mapped[dict] = mapped_column(JSON, default=dict)              # automatic extraction
    is_template: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    runs = relationship("MatchRun", back_populates="job", cascade="all, delete-orphan")


class Candidate(Base):
    __tablename__ = "candidates"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str | None] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(60))
    location: Mapped[str | None] = mapped_column(String(200))
    linkedin: Mapped[str | None] = mapped_column(String(300))
    github: Mapped[str | None] = mapped_column(String(300))
    portfolio: Mapped[str | None] = mapped_column(String(300))
    summary: Mapped[str | None] = mapped_column(Text)
    parsed: Mapped[dict] = mapped_column(JSON, default=dict)
    parse_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    review_status: Mapped[str] = mapped_column(String(30), default="new")   # new|in_review|reviewed|shortlisted|interview|on_hold|not_progressing
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    resume = relationship("Resume", back_populates="candidate", uselist=False, cascade="all, delete-orphan")
    skills = relationship("ExtractedSkill", cascade="all, delete-orphan")
    employment = relationship("Employment", cascade="all, delete-orphan")
    education = relationship("Education", cascade="all, delete-orphan")
    projects = relationship("Project", cascade="all, delete-orphan")
    notes = relationship("CandidateNote", cascade="all, delete-orphan")
    interviews = relationship("InterviewNote", cascade="all, delete-orphan")   # erased with the candidate (privacy)
    results = relationship("MatchResult", cascade="all, delete-orphan")


class Resume(Base):
    __tablename__ = "resumes"
    __table_args__ = (UniqueConstraint("file_hash", name="uq_resume_hash"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[str | None] = mapped_column(String(40), index=True)
    original_filename: Mapped[str] = mapped_column(String(200))
    stored_filename: Mapped[str | None] = mapped_column(String(100))
    file_hash: Mapped[str] = mapped_column(String(64))
    file_size: Mapped[int] = mapped_column(Integer)
    file_type: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(20), default="pending")      # parsed | failed
    error_code: Mapped[str | None] = mapped_column(String(40))
    error_message: Mapped[str | None] = mapped_column(String(400))
    page_count: Mapped[int | None] = mapped_column(Integer)
    diagnostics: Mapped[dict] = mapped_column(JSON, default=dict)
    raw_text: Mapped[str | None] = mapped_column(Text)                      # scrubbed of protected-attribute lines
    processing_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    candidate_id: Mapped[int | None] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    candidate = relationship("Candidate", back_populates="resume")


class ExtractedSkill(Base):
    __tablename__ = "extracted_skills"
    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100), index=True)
    category: Mapped[str] = mapped_column(String(60))
    method: Mapped[str] = mapped_column(String(20), default="extracted")    # extracted | inferred
    listed_only: Mapped[bool] = mapped_column(Boolean, default=False)
    mentions: Mapped[list] = mapped_column(JSON, default=list)
    proficiency: Mapped[dict | None] = mapped_column(JSON)


class Employment(Base):
    __tablename__ = "employment"
    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    title: Mapped[str | None] = mapped_column(String(200))
    company: Mapped[str | None] = mapped_column(String(200))
    start: Mapped[str | None] = mapped_column(String(10))
    end: Mapped[str | None] = mapped_column(String(10))
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)
    type: Mapped[str] = mapped_column(String(20), default="full_time")
    date_uncertain: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[list] = mapped_column(JSON, default=list)
    page: Mapped[int | None] = mapped_column(Integer)


class Education(Base):
    __tablename__ = "education"
    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    degree: Mapped[str | None] = mapped_column(String(200))
    level: Mapped[int | None] = mapped_column(Integer)
    institution: Mapped[str | None] = mapped_column(String(200))
    year: Mapped[int | None] = mapped_column(Integer)
    field: Mapped[str | None] = mapped_column(String(200))
    page: Mapped[int | None] = mapped_column(Integer)


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[list] = mapped_column(JSON, default=list)
    skills: Mapped[list] = mapped_column(JSON, default=list)
    page: Mapped[int | None] = mapped_column(Integer)


class MatchRun(Base):
    __tablename__ = "match_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    algorithm_version: Mapped[str] = mapped_column(String(20))
    similarity_method: Mapped[str] = mapped_column(String(20))
    model_name: Mapped[str] = mapped_column(String(200))
    fallback_reason: Mapped[str | None] = mapped_column(String(300))
    weights: Mapped[dict] = mapped_column(JSON)
    as_of: Mapped[str] = mapped_column(String(10))
    n_candidates: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    job_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)          # requirements used (reproducibility)
    job = relationship("Job", back_populates="runs")
    results = relationship("MatchResult", back_populates="run", cascade="all, delete-orphan")


class MatchResult(Base):
    __tablename__ = "match_results"
    __table_args__ = (UniqueConstraint("run_id", "candidate_id", name="uq_run_candidate"), Index("ix_result_run_rank", "run_id", "rank"))
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("match_runs.id", ondelete="CASCADE"), index=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    rank: Mapped[int] = mapped_column(Integer)
    overall: Mapped[float] = mapped_column(Float)
    score_low: Mapped[float] = mapped_column(Float)
    score_high: Mapped[float] = mapped_column(Float)
    skill_coverage: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    completeness: Mapped[float] = mapped_column(Float)
    relevant_years: Mapped[float] = mapped_column(Float, default=0.0)
    total_years: Mapped[float] = mapped_column(Float, default=0.0)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)                # requirements, experience, semantic, etc.
    explanation: Mapped[dict] = mapped_column(JSON, default=dict)
    sensitivity: Mapped[dict] = mapped_column(JSON, default=dict)
    run = relationship("MatchRun", back_populates="results")
    components = relationship("ScoreComponent", cascade="all, delete-orphan")
    evidence = relationship("EvidenceItem", cascade="all, delete-orphan")
    overrides = relationship("ManualOverride", cascade="all, delete-orphan")


class ScoreComponent(Base):
    __tablename__ = "score_components"
    id: Mapped[int] = mapped_column(primary_key=True)
    result_id: Mapped[int] = mapped_column(ForeignKey("match_results.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(40))
    score: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20))
    weight_configured: Mapped[float] = mapped_column(Float)
    weight_effective: Mapped[float | None] = mapped_column(Float)
    contribution: Mapped[float | None] = mapped_column(Float)


class EvidenceItem(Base):
    __tablename__ = "evidence_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    result_id: Mapped[int] = mapped_column(ForeignKey("match_results.id", ondelete="CASCADE"), index=True)
    candidate_id: Mapped[int] = mapped_column(Integer, index=True)
    requirement_id: Mapped[str] = mapped_column(String(100))
    requirement: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(30))
    match_type: Mapped[str] = mapped_column(String(20))    # exact | synonym | semantic | partial | none
    evidence_text: Mapped[str | None] = mapped_column(Text)
    page: Mapped[int | None] = mapped_column(Integer)
    similarity: Mapped[float | None] = mapped_column(Float)
    verification: Mapped[str] = mapped_column(String(30))


class ManualOverride(Base):
    __tablename__ = "manual_overrides"
    id: Mapped[int] = mapped_column(primary_key=True)
    result_id: Mapped[int] = mapped_column(ForeignKey("match_results.id", ondelete="CASCADE"), index=True)
    original_score: Mapped[float] = mapped_column(Float)
    new_score: Mapped[float] = mapped_column(Float)
    reason: Mapped[str] = mapped_column(Text)
    reviewer: Mapped[str] = mapped_column(String(100), default="recruiter")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class CandidateNote(Base):
    __tablename__ = "candidate_notes"
    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(Text)
    author: Mapped[str] = mapped_column(String(100), default="recruiter")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class InterviewNote(Base):
    """A structured interview scorecard written by a human interviewer. Never used by the matching score."""
    __tablename__ = "interview_notes"
    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"))
    round: Mapped[str] = mapped_column(String(30), default="technical")          # phone_screen|technical|hr|culture|final|other
    interviewer: Mapped[str] = mapped_column(String(100), default="")
    interviewed_on: Mapped[date] = mapped_column(Date, default=lambda: utcnow().date())
    recommendation: Mapped[str] = mapped_column(String(20), default="undecided")  # strong_yes|yes|no|strong_no|undecided
    ratings: Mapped[dict] = mapped_column(JSON, default=dict)                      # criterion -> 1..5
    strengths: Mapped[str] = mapped_column(Text, default="")
    concerns: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class SavedSearch(Base):
    __tablename__ = "saved_searches"
    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100))
    filters: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AuditLog(Base):
    """Audit trail. Stores action + ids + non-personal metadata only (never names, emails or resume text)."""
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    actor: Mapped[str] = mapped_column(String(60), default="recruiter")
    action: Mapped[str] = mapped_column(String(60), index=True)
    entity_type: Mapped[str | None] = mapped_column(String(40))
    entity_id: Mapped[int | None] = mapped_column(Integer)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
