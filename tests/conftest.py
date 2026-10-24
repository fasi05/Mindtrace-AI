import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.repository import Repository  # noqa: E402
from database.session import init_schema, make_engine, make_session_factory  # noqa: E402
from services.ai_client import StructuredAI  # noqa: E402
from services.ai_providers.base import LLMProvider  # noqa: E402


class FakeProvider(LLMProvider):
    """TEST-ONLY scripted provider. Never imported by application code."""
    name, model = "fake", "fake-1"

    def __init__(self, replies):
        self.replies, self.calls = list(replies), 0

    def complete(self, system, user):
        self.calls += 1
        r = self.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return r if isinstance(r, str) else json.dumps(r)


DIAGNOSIS = {
    "can_diagnose": True, "concept_id": "two_step_equations", "misconception_category": "inverse_operation_error",
    "misconception_label": "Added instead of subtracting", "confidence": "high",
    "misconception_statement": "Likely believed the +3 moves across the equals sign by being added to the other side.",
    "evidence": [{"quote": "2x = 14", "observation": "14 equals 11 + 3, so 3 was added to the right side."}],
    "incorrect_step_quote": "2x = 14", "why_incorrect": "Undoing +3 requires subtracting 3 from both sides.",
    "inference_note": "This is inferred from the numbers in the steps; you did not explain your thinking.",
    "explanation": "You combined 11 and 3 with addition, but the inverse of adding 3 is subtracting 3.",
    "mini_lesson": {"title": "Undo with the inverse", "principle": "Apply the inverse operation to both sides.",
                    "worked_example": "x + 5 = 9 -> x = 9 - 5 -> x = 4", "key_takeaways": ["Inverse of + is -"]},
    "correct_solution_steps": ["2x = 8", "x = 4"],
}
PRACTICE = {
    "practice": [
        {"question": "Solve x + 4 = 9", "hint_1": "What undoes +4?", "hint_2": "Subtract 4 from both sides.", "difficulty": "easy"},
        {"question": "Solve 2x + 5 = 13", "hint_1": "Undo +5 first.", "hint_2": "Subtract 5 from both sides.", "difficulty": "medium"},
        {"question": "Solve 4x + 7 = 23", "hint_1": "Undo +7 first.", "hint_2": "Subtract 7, then divide.", "difficulty": "medium"},
        {"question": "Solve 5x + 12 = 47", "hint_1": "Undo +12.", "hint_2": "Subtract 12 from both sides.", "difficulty": "hard"},
    ],
    "transfer": {"question": "Solve 3x + 5 = 20", "hint_1": "n/a", "hint_2": "n/a", "difficulty": "hard"},
}


@pytest.fixture
def repo(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 't.db'}")
    init_schema(engine)
    return Repository(make_session_factory(engine))


@pytest.fixture
def learner(repo):
    return repo.get_or_create_learner("testlearner0001")


def ai_with(*replies) -> StructuredAI:
    return StructuredAI(FakeProvider(replies))
