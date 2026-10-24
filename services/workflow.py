"""Orchestrates AI services + repository. The only module UI code calls for end-to-end actions."""
from __future__ import annotations

from typing import Optional

from database.models import DiagnosisSession, PracticeQuestion
from database.repository import AttemptOutcome, Repository
from models.schemas import DiagnosisResult
from services.ai_client import StructuredAI
from services.ai_providers.factory import build_provider
from services.config import Settings
from services.diagnosis import DiagnosisService
from services.practice import PracticeService, judge_attempt, solution_for
from utils.validation import InputError, clean_text, validate_diagnosis_input


def build_ai(settings: Settings) -> StructuredAI:
    """Raises AIConfigError with setup instructions when credentials are missing."""
    return StructuredAI(build_provider(settings))


def run_diagnosis(repo: Repository, ai_factory, learner_id: int, subject: str, topic: str,
                  question: str, answer: str, reasoning: str) -> tuple[DiagnosisSession, bool]:
    """Validate -> reuse identical earlier session (no AI call) -> else diagnose -> persist."""
    q, a, r = validate_diagnosis_input(question, answer, reasoning)
    # Reuse ONLY an identical earlier submission that reached a final result. Different answers always
    # produce a fresh diagnosis; unfinished results (insufficient/incorrect) are re-evaluated.
    existing = repo.find_session(learner_id, subject, topic, q, a, r)
    if existing is not None and existing.status in repo.FINAL_STATUSES:
        return existing, False
    ai = ai_factory()  # surfaces missing-credential errors with setup instructions
    result = DiagnosisService(ai).diagnose(q, a, r)
    return repo.create_diagnosis(learner_id, subject, topic, q, a, r, result)


def ensure_mission(repo: Repository, ai_factory, learner_id: int, session: DiagnosisSession) -> list:
    existing = repo.get_questions(session.id)
    if existing:
        return existing
    result = DiagnosisResult.model_validate(session.result)
    if result.status == "insufficient_evidence":
        raise InputError("A repair mission needs a verified diagnosis first. Add more working and re-run the diagnosis.")
    items = PracticeService(ai_factory()).generate(session.question, result)
    repo.add_practice_set(session.id, learner_id, result.concept_id, items)
    return repo.get_questions(session.id)


def submit_attempt(repo: Repository, ai_factory, learner_id: int, session: DiagnosisSession,
                   question: PracticeQuestion, raw_answer: str) -> tuple[AttemptOutcome, list[str]]:
    """Deterministic grading; AI coaching only for wrong answers (optional, never fabricated)."""
    correct, answer = judge_attempt(question.question, raw_answer)
    feedback: Optional[dict] = None
    steps = solution_for(question.question)
    if not correct:
        coach = None
        try:
            result = DiagnosisResult.model_validate(session.result)
            label = result.diagnosis.misconception_statement if result.diagnosis else ""
            coach = PracticeService(ai_factory()).feedback(question.question, answer, question.expected_answer, label)
        except Exception:  # AI unavailable: show verified facts only
            coach = None
        feedback = {"ai": coach.model_dump() if coach else None}
    outcome = repo.record_attempt(question.id, learner_id, answer, correct, feedback)
    return outcome, steps
