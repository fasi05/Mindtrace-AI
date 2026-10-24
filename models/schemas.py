"""Pydantic schemas: AI response contracts and persisted result objects."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from models.concepts import CONCEPTS, MISCONCEPTION_CATEGORIES

Confidence = Literal["low", "medium", "high"]


# ---------------------------------------------------------------- verifier ---
class StepCheck(BaseModel):
    text: str
    parsed: bool
    consistent: Optional[bool] = None  # None = could not be checked
    note: str = ""


class WorkAnalysis(BaseModel):
    """Deterministic (sympy) analysis of the learner's submitted work."""

    problem_type: Literal["equation", "expression", "unknown"] = "unknown"
    verifiable: bool = False
    math_text: str = ""
    correct_answer: Optional[str] = None
    final_answer_correct: Optional[bool] = None
    final_answer_text: Optional[str] = None
    steps: list[StepCheck] = Field(default_factory=list)
    first_inconsistent_step: Optional[int] = None
    signals: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


# --------------------------------------------------------------- AI output ---
class Evidence(BaseModel):
    quote: str = Field(min_length=1, max_length=300)
    observation: str = Field(min_length=1, max_length=500)


class MiniLesson(BaseModel):
    title: str
    principle: str
    worked_example: str
    key_takeaways: list[str] = Field(min_length=1, max_length=5)


class DiagnosisAI(BaseModel):
    can_diagnose: bool
    follow_up_request: str = ""
    concept_id: str = ""
    misconception_category: str = "other"
    misconception_label: str = ""
    misconception_statement: str = ""
    confidence: Confidence = "low"
    evidence: list[Evidence] = Field(default_factory=list)
    incorrect_step_quote: str = ""
    why_incorrect: str = ""
    inference_note: str = ""
    explanation: str = ""
    mini_lesson: Optional[MiniLesson] = None
    correct_solution_steps: list[str] = Field(default_factory=list)

    @field_validator("misconception_label")
    @classmethod
    def _short_label(cls, v: str) -> str:
        return v.strip()[:90]

    @model_validator(mode="after")
    def _check_complete(self) -> "DiagnosisAI":
        if not self.can_diagnose:
            if not self.follow_up_request.strip():
                raise ValueError("follow_up_request is required when can_diagnose is false")
            return self
        if self.concept_id not in CONCEPTS:
            raise ValueError(f"concept_id must be one of {sorted(CONCEPTS)}")
        if self.misconception_category not in MISCONCEPTION_CATEGORIES:
            raise ValueError(f"misconception_category must be one of {MISCONCEPTION_CATEGORIES}")
        for name in ("misconception_label", "misconception_statement", "why_incorrect",
                     "explanation", "inference_note"):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} must not be empty when can_diagnose is true")
        if not self.evidence:
            raise ValueError("at least one evidence item quoting the learner's work is required")
        if self.mini_lesson is None:
            raise ValueError("mini_lesson is required when can_diagnose is true")
        return self


class PracticeItem(BaseModel):
    question: str = Field(min_length=3, max_length=200)
    hint_1: str = Field(min_length=1, max_length=400)
    hint_2: str = Field(min_length=1, max_length=400)
    difficulty: Literal["easy", "medium", "hard"]
    rationale: str = Field(default="", max_length=400)


class PracticeSet(BaseModel):
    practice: list[PracticeItem] = Field(min_length=3, max_length=6)
    transfer: PracticeItem


class AttemptFeedback(BaseModel):
    feedback: str = Field(min_length=1, max_length=900)
    next_tip: str = Field(default="", max_length=400)


# ------------------------------------------------------------- app results ---
class DiagnosisResult(BaseModel):
    status: Literal["misconception_found", "incorrect", "correct", "insufficient_evidence"]
    message: str
    analysis: WorkAnalysis
    diagnosis: Optional[DiagnosisAI] = None
    confidence: Optional[Confidence] = None
    concept_id: Optional[str] = None
    correct_answer: Optional[str] = None
    correct_solution_steps: list[str] = Field(default_factory=list)
    verification_notes: list[str] = Field(default_factory=list)
    dropped_evidence: int = 0
    provider: str = ""
    model: str = ""
