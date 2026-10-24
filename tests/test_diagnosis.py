import pytest

from services.diagnosis import DiagnosisService
from tests.conftest import DIAGNOSIS, FakeProvider
from services.ai_client import StructuredAI
from utils.validation import InputError

Q = 'Solve "2x + 3 = 11"'


def svc(*replies):
    p = FakeProvider(replies)
    return DiagnosisService(StructuredAI(p)), p


def test_required_scenario_end_to_end():
    s, p = svc(DIAGNOSIS)
    r = s.diagnose(Q, "2x = 14\nx = 7")
    assert r.status == "misconception_found" and p.calls == 1
    assert r.correct_solution_steps == ["2x + 3 = 11", "2x = 11 - 3", "2x = 8", "x = 8 / 2", "x = 4"]
    assert r.diagnosis.evidence[0].quote == "2x = 14"
    assert r.confidence == "high"  # a deterministic signal backs it


def test_correct_answer_needs_no_ai():
    s, p = svc()
    r = s.diagnose(Q, "2x = 8\nx = 4")
    assert r.status == "correct" and p.calls == 0 and r.diagnosis is None


def test_bare_wrong_answer_is_insufficient_without_ai():
    s, p = svc()
    r = s.diagnose(Q, "x = 7")
    assert r.status == "insufficient_evidence" and p.calls == 0
    assert "more" in r.message.lower() or "working" in r.message.lower()


def test_ai_can_decline_to_diagnose():
    s, _ = svc({"can_diagnose": False, "follow_up_request": "Show how you got 14."})
    r = s.diagnose(Q, "2x = 14\nx = 7")
    # verified wrong stays visible as "incorrect" - never "correct", never silently "insufficient"
    assert r.status == "incorrect" and "14" in r.message and r.analysis.final_answer_correct is False


def test_ungrounded_evidence_is_dropped_and_diagnosis_refused():
    bad = {**DIAGNOSIS, "evidence": [{"quote": "I forgot to divide", "observation": "invented"}]}
    s, _ = svc(bad)
    r = s.diagnose(Q, "2x = 14\nx = 7")
    assert r.status == "incorrect" and r.diagnosis is None
    assert r.correct_solution_steps[-1] == "x = 4"


def test_partially_grounded_evidence_caps_confidence():
    mixed = {**DIAGNOSIS, "evidence": DIAGNOSIS["evidence"] + [{"quote": "made up", "observation": "x"}]}
    s, _ = svc(mixed)
    r = s.diagnose(Q, "2x = 14\nx = 7")
    assert r.dropped_evidence == 1 and r.confidence == "medium" and len(r.diagnosis.evidence) == 1


def test_unverifiable_problem_gets_no_invented_diagnosis():
    s, p = svc()
    r = s.diagnose("Explain photosynthesis", "step one\nplants eat light", "I think so")
    assert r.status == "insufficient_evidence" and p.calls == 0 and r.diagnosis is None


def test_input_validation():
    s, _ = svc()
    with pytest.raises(InputError):
        s.diagnose("", "x = 1")
    with pytest.raises(InputError):
        s.diagnose(Q, "x" * 5000)
