"""Pure mastery math. Mastery is a weighted Beta-style estimate from real evaluated attempts."""
from __future__ import annotations

MIN_EVIDENCE = 3          # attempts needed before a concept counts as "assessed"
HINT_CREDIT = 0.7         # a correct answer after hints earns partial credit
ATTEMPT_WEIGHT = {"diagnosis": 1.0, "practice": 1.0, "transfer": 2.0}


def credit(correct: bool, hints_used: int = 0) -> float:
    if not correct:
        return 0.0
    return HINT_CREDIT if hints_used > 0 else 1.0


def estimate(weighted_credit: float, weighted_total: float) -> float:
    """(credit + 1) / (total + 2): starts at 0.5 with no data and moves with evidence."""
    return round((weighted_credit + 1.0) / (weighted_total + 2.0), 4)


def is_assessed(attempts: int) -> bool:
    return attempts >= MIN_EVIDENCE


def label(mastery: float, attempts: int) -> str:
    if not is_assessed(attempts):
        return "Not enough data"
    if mastery >= 0.75:
        return "Strong"
    if mastery >= 0.5:
        return "Developing"
    return "Needs work"
