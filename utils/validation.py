"""Input validation and sanitising for all learner-provided text."""
from __future__ import annotations

import re

MAX_QUESTION, MAX_ANSWER, MAX_REASONING = 300, 1000, 2000
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
LEARNER_CODE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


class InputError(ValueError):
    """Message is safe to show to the learner."""


def clean_text(value: str | None, max_len: int, field: str, required: bool = True) -> str:
    text = _CTRL.sub("", (value or "")).strip()
    if required and not text:
        raise InputError(f"{field} is required.")
    if len(text) > max_len:
        raise InputError(f"{field} must be at most {max_len} characters (currently {len(text)}).")
    return text


def validate_diagnosis_input(question: str, answer: str, reasoning: str) -> tuple[str, str, str]:
    q = clean_text(question, MAX_QUESTION, "Question")
    a = clean_text(answer, MAX_ANSWER, "Your answer")
    r = clean_text(reasoning, MAX_REASONING, "Reasoning", required=False)
    return q, a, r


def validate_learner_code(code: str) -> str:
    code = (code or "").strip()
    if not LEARNER_CODE.match(code):
        raise InputError("A learner code is 8-64 letters, digits, '-' or '_'.")
    return code
