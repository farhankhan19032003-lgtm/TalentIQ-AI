from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class RequirementIn(BaseModel):
    id: str | None = None
    name: str = Field(min_length=1, max_length=100)
    category: str | None = None
    importance: Literal["must", "preferred", "ignored"] = "must"
    weight: float = Field(default=1.0, ge=0, le=5)


class JobIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    role: str | None = Field(default=None, max_length=200)
    category: str | None = Field(default=None, max_length=100)
    description: str = Field(min_length=20, max_length=50000)
    min_experience_years: float | None = Field(default=None, ge=0, le=50)
    preferred_experience_years: float | None = Field(default=None, ge=0, le=50)
    education_level: int | None = Field(default=None, ge=0, le=5)
    preferred_education_level: int | None = Field(default=None, ge=0, le=5)
    required_skills: list[str] = []
    optional_skills: list[str] = []
    requirements: list[RequirementIn] | None = None   # explicit recruiter-edited requirements override auto extraction
    is_template: bool = False
    reanalyze: bool = True


class AnalyzeIn(BaseModel):
    description: str = Field(min_length=20, max_length=50000)
    title: str | None = None


class RunIn(BaseModel):
    weights: dict[str, float] | None = None
    resume_ids: list[int] | None = None


# "in_review" is kept for backward compatibility; the UI pipeline uses reviewed/shortlisted/interview.
ReviewStatus = Literal["new", "in_review", "reviewed", "shortlisted", "interview", "on_hold", "not_progressing"]


class StatusIn(BaseModel):
    review_status: ReviewStatus
    reason: str | None = Field(default=None, max_length=500)


class BulkStatusIn(BaseModel):
    candidate_ids: list[int] = Field(min_length=1, max_length=200)
    review_status: ReviewStatus
    reason: str | None = Field(default=None, max_length=500)


class NoteIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


InterviewRound = Literal["phone_screen", "technical", "hr", "culture", "final", "other"]
InterviewRecommendation = Literal["strong_yes", "yes", "no", "strong_no", "undecided"]
RATING_CRITERIA = ("technical", "communication", "problem_solving", "collaboration")


def _check_ratings(v: dict[str, int] | None):
    if v is None:
        return v
    bad_keys = [k for k in v if k not in RATING_CRITERIA]
    if bad_keys:
        raise ValueError(f"Unknown rating criteria: {', '.join(bad_keys)}. Allowed: {', '.join(RATING_CRITERIA)}.")
    if any(not (1 <= n <= 5) for n in v.values()):
        raise ValueError("Ratings must be whole numbers from 1 to 5.")
    return v


class InterviewIn(BaseModel):
    round: InterviewRound = "technical"
    job_id: int | None = None
    interviewer: str = Field(default="", max_length=100)
    interviewed_on: date | None = None
    recommendation: InterviewRecommendation = "undecided"
    ratings: dict[str, int] = Field(default_factory=dict)
    strengths: str = Field(default="", max_length=2000)
    concerns: str = Field(default="", max_length=2000)
    notes: str = Field(default="", max_length=4000)

    @field_validator("ratings")
    @classmethod
    def check_ratings(cls, v):
        return _check_ratings(v)

    @model_validator(mode="after")
    def check_not_empty(self):
        if not (self.ratings or self.strengths.strip() or self.concerns.strip() or self.notes.strip() or self.recommendation != "undecided"):
            raise ValueError("Add at least a rating, a recommendation or some notes.")
        return self


class InterviewPatch(BaseModel):
    round: InterviewRound | None = None
    job_id: int | None = None
    interviewer: str | None = Field(default=None, max_length=100)
    interviewed_on: date | None = None
    recommendation: InterviewRecommendation | None = None
    ratings: dict[str, int] | None = None
    strengths: str | None = Field(default=None, max_length=2000)
    concerns: str | None = Field(default=None, max_length=2000)
    notes: str | None = Field(default=None, max_length=4000)

    @field_validator("ratings")
    @classmethod
    def check_ratings(cls, v):
        return _check_ratings(v)


class OverrideIn(BaseModel):
    new_score: float = Field(ge=0, le=100)
    reason: str = Field(min_length=5, max_length=1000)


class WhatIfIn(BaseModel):
    weights: dict[str, float] | None = None
    requirement_changes: list[dict] = []
    add_requirements: list[dict] = []
    remove_requirement_ids: list[str] = []
    min_years: float | None = Field(default=None, ge=0, le=50)
    preferred_years: float | None = Field(default=None, ge=0, le=50)
    education_level: int | None = Field(default=None, ge=0, le=5)

    @field_validator("add_requirements")
    @classmethod
    def _names(cls, v):
        for a in v:
            if not str(a.get("name", "")).strip():
                raise ValueError("added requirement needs a name")
        return v


class SavedSearchIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    job_id: int | None = None
    filters: dict = {}


class LoginIn(BaseModel):
    api_key: str = ""
