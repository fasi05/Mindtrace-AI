"""Repair-mission content: generate verified practice/transfer items, evaluate answers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from models.schemas import AttemptFeedback, DiagnosisResult, PracticeItem, PracticeSet
from services import prompts
from services.ai_client import StructuredAI
from services.ai_providers.base import AIError, AIResponseError
from services.math_verifier import canonical_steps, evaluate_answer, extract_math, verify_practice_question
from utils.validation import InputError, clean_text

_ORDER = {"easy": 0, "medium": 1, "hard": 2}


@dataclass
class VerifiedItem:
    kind: str                 # "practice" | "transfer"
    question: str
    expected_answer: str      # computed by sympy, never taken from the AI
    hints: list[str]
    difficulty: str


def _norm(q: str) -> str:
    return "".join(extract_math(q).split())


def _verify(items: list[PracticeItem], kind: str, banned: set[str]) -> list[VerifiedItem]:
    out: list[VerifiedItem] = []
    for it in items:
        key = _norm(it.question)
        expected = verify_practice_question(it.question)
        if expected is None or key in banned:
            continue
        banned.add(key)
        out.append(VerifiedItem(kind, it.question.strip(), expected, [it.hint_1, it.hint_2], it.difficulty))
    return out


class PracticeService:
    MIN_PRACTICE = 3

    def __init__(self, ai: StructuredAI):
        self.ai = ai

    def generate(self, question: str, result: DiagnosisResult) -> list[VerifiedItem]:
        d = result.diagnosis
        concept = result.concept_id or "two_step_equations"
        misconception = d.misconception_statement if d else "general practice on this concept"
        why = d.why_incorrect if d else ""
        note = ""
        for _ in range(2):
            ps: PracticeSet = self.ai.generate(
                PracticeSet, prompts.PRACTICE_SYSTEM,
                prompts.practice_user_prompt(question, concept, misconception, why, retry_note=note))
            banned = {_norm(question)}
            practice = _verify(ps.practice, "practice", banned)
            transfer = _verify([ps.transfer], "transfer", banned)
            if len(practice) >= self.MIN_PRACTICE and transfer:
                practice.sort(key=lambda i: _ORDER[i.difficulty])
                return practice + transfer
            note = ("\nPrevious attempt had unverifiable or duplicate questions. Use only one-variable linear "
                    "problems or simple expressions written with digits and + - * / ( ) =, each with one solution.")
        raise AIResponseError("Could not generate enough verifiable practice questions. Please retry.")

    def feedback(self, question: str, learner_answer: str, expected: str, misconception: str) -> Optional[AttemptFeedback]:
        """AI coaching for a wrong attempt; None if the AI is unavailable (caller shows verified facts only)."""
        try:
            return self.ai.generate(AttemptFeedback, prompts.FEEDBACK_SYSTEM,
                                    prompts.feedback_user_prompt(question, learner_answer, expected, misconception))
        except AIError:
            return None


def judge_attempt(question: str, learner_answer: str) -> tuple[bool, str]:
    """Deterministic grading. Returns (correct, cleaned answer). Raises InputError if unreadable."""
    answer = clean_text(learner_answer, 200, "Answer")
    correct, analysis = evaluate_answer(question, answer)
    if correct is None:
        raise InputError("I couldn't read that as a final answer. Enter something like  x = 5  or just  5.")
    return correct, answer


def solution_for(question: str) -> list[str]:
    return canonical_steps(question) or []
