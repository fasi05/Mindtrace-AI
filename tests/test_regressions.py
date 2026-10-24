"""Regression tests for: wrong working marked correct, and stale/old results after a new submission."""
import os

import pytest

from models.schemas import DiagnosisResult
from services.ai_client import StructuredAI
from services.ai_providers.base import AIRequestError
from services.diagnosis import DiagnosisService
from services.math_verifier import analyze_work
from services.workflow import run_diagnosis
from tests.conftest import DIAGNOSIS, FakeProvider

Q = "Solve `2x + 3 = 11`"
Q2 = 'Solve "2x + 3 = 11"'
SUBJ = ("Mathematics (Algebra)", "Two-step equations")


def svc(*replies):
    p = FakeProvider(replies)
    return DiagnosisService(StructuredAI(p)), p


# ---- the reported bug ------------------------------------------------------
@pytest.mark.parametrize("q", [Q, Q2, "Solve 2x+3=11", "solve for x: 2x + 3 = 11"])
def test_incorrect_working_is_never_correct(q):
    s, _ = svc(DIAGNOSIS)
    r = s.diagnose(q, "2x = 14\nx = 7")
    assert r.status != "correct"
    assert r.analysis.final_answer_correct is False and r.analysis.first_inconsistent_step == 0


@pytest.mark.parametrize("q", [Q, Q2])
def test_correct_working_is_correct_without_ai(q):
    s, p = svc()
    r = s.diagnose(q, "2x = 8\nx = 4")
    assert r.status == "correct" and p.calls == 0


@pytest.mark.parametrize("answer", ["2x = 14, x = 7", "2x=14; x=7", "2x = 14 -> x = 7", "2x = 14 => x = 7"])
def test_separator_styles_do_not_hide_wrong_work(answer):
    a = analyze_work(Q2, answer)
    assert a.final_answer_correct is False and a.first_inconsistent_step == 0


@pytest.mark.parametrize("answer", ["2x = 8, x = 4", "2x = 8 -> x = 4"])
def test_separator_styles_correct(answer):
    assert analyze_work(Q2, answer).final_answer_correct is True


def test_explanation_names_the_real_error_even_if_ai_declines():
    s, _ = svc({"can_diagnose": False, "follow_up_request": "Tell me how you got 14."})
    r = s.diagnose(Q2, "2x = 14\nx = 7")
    assert r.status == "incorrect"
    assert r.correct_solution_steps[:3] == ["2x + 3 = 11", "2x = 11 - 3", "2x = 8"]
    assert any("subtracting 3 from both sides" in sig for sig in r.analysis.signals)


def test_correct_final_answer_with_invalid_steps_is_not_correct():
    s, p = svc(DIAGNOSIS)
    r = s.diagnose(Q2, "2x = 14\nx = 4")
    assert r.status != "correct" and r.analysis.final_answer_correct is True
    assert r.analysis.first_inconsistent_step == 0 and p.calls == 1


def test_wrong_final_answer_only_is_insufficient_but_marked_wrong():
    s, p = svc()
    r = s.diagnose(Q2, "x = 7")
    assert r.status == "insufficient_evidence" and p.calls == 0
    assert r.analysis.final_answer_correct is False and "not correct" in r.message


def test_unsupported_problem_is_not_marked_correct_or_diagnosed():
    s, p = svc()
    for q, a in [("Prove that sqrt(2) is irrational", "trivial"), ("Solve sin(x) = 1", "x = 90")]:
        assert s.diagnose(q, a).status == "insufficient_evidence"
    assert p.calls == 0


def test_ai_cannot_turn_wrong_work_into_correct():
    s, _ = svc({**DIAGNOSIS, "misconception_label": "Looks fine", "explanation": "Your answer is correct."})
    assert s.diagnose(Q2, "2x = 14\nx = 7").status != "correct"


def test_quotes_must_exist_in_submission():
    bad = {**DIAGNOSIS, "incorrect_step_quote": "x = 100"}
    s, _ = svc(bad)
    r = s.diagnose(Q2, "2x = 14\nx = 7")
    assert r.status == "misconception_found" and r.diagnosis.incorrect_step_quote == ""
    assert all(e.quote in "2x = 14\nx = 7" for e in r.diagnosis.evidence)


def test_ai_provider_error_propagates_and_is_not_a_result():
    s, _ = svc(AIRequestError("timed out"))
    with pytest.raises(AIRequestError):
        s.diagnose(Q2, "2x = 14\nx = 7")


# ---- freshness / caching ----------------------------------------------------
def test_new_submission_after_previous_is_a_new_session(repo, learner):
    p = FakeProvider([DIAGNOSIS, DIAGNOSIS])
    f = lambda: StructuredAI(p)
    right, c1 = run_diagnosis(repo, f, learner.id, *SUBJ, Q2, "2x = 8\nx = 4", "")
    wrong, c2 = run_diagnosis(repo, f, learner.id, *SUBJ, Q2, "2x = 14\nx = 7", "")
    assert c1 and c2 and right.id != wrong.id
    assert right.status == "correct" and wrong.status == "misconception_found"
    assert DiagnosisResult.model_validate(wrong.result).analysis.final_answer_text == "7"
    assert wrong.answer == "2x = 14\nx = 7" and right.answer == "2x = 8\nx = 4"


def test_same_question_different_wrong_answers_get_separate_diagnoses(repo, learner):
    p = FakeProvider([DIAGNOSIS, DIAGNOSIS])
    f = lambda: StructuredAI(p)
    a, _ = run_diagnosis(repo, f, learner.id, *SUBJ, Q2, "2x = 14\nx = 7", "")
    b, _ = run_diagnosis(repo, f, learner.id, *SUBJ, Q2, "2x = 8\nx = 5", "")
    assert a.id != b.id and p.calls == 2
    assert DiagnosisResult.model_validate(b.result).analysis.final_answer_text == "5"


def test_identical_duplicate_click_returns_same_session_without_ai(repo, learner):
    p = FakeProvider([DIAGNOSIS])
    f = lambda: StructuredAI(p)
    a, c1 = run_diagnosis(repo, f, learner.id, *SUBJ, Q2, "2x = 14\nx = 7", "")
    b, c2 = run_diagnosis(repo, f, learner.id, *SUBJ, Q2, "2x = 14\nx = 7", "")
    assert c1 and not c2 and a.id == b.id and p.calls == 1


def test_unfinished_result_is_reevaluated_not_stuck(repo, learner):
    decline = {"can_diagnose": False, "follow_up_request": "More please."}
    p = FakeProvider([decline, DIAGNOSIS])
    f = lambda: StructuredAI(p)
    a, _ = run_diagnosis(repo, f, learner.id, *SUBJ, Q2, "2x = 14\nx = 7", "")
    assert a.status == "incorrect"
    b, _ = run_diagnosis(repo, f, learner.id, *SUBJ, Q2, "2x = 14\nx = 7", "")
    assert b.id == a.id and b.status == "misconception_found" and p.calls == 2
    assert len(repo.list_sessions(learner.id)) == 1
    assert repo.mastery_rows(learner.id)[0].attempts == 1  # counted once, not per retry


def test_provider_failure_saves_nothing(repo, learner):
    p = FakeProvider([AIRequestError("rate limit")])
    with pytest.raises(AIRequestError):
        run_diagnosis(repo, lambda: StructuredAI(p), learner.id, *SUBJ, Q2, "2x = 14\nx = 7", "")
    assert repo.list_sessions(learner.id) == []


# ---- UI: results page shows the selected submission -------------------------
@pytest.fixture
def app_env(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'r.db'}")
    for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"):
        monkeypatch.delenv(k, raising=False)


def test_results_page_never_shows_another_submissions_result(app_env):
    from streamlit.testing.v1 import AppTest
    from database.repository import Repository
    from database.session import init_schema, make_engine, make_session_factory
    root = os.path.dirname(os.path.dirname(__file__))
    engine = make_engine(os.environ["DATABASE_URL"]); init_schema(engine)
    repo = Repository(make_session_factory(engine))
    learner = repo.get_or_create_learner("freshresults0001")
    p = FakeProvider([DIAGNOSIS])
    f = lambda: StructuredAI(p)
    good, _ = run_diagnosis(repo, f, learner.id, *SUBJ, Q2, "2x = 8\nx = 4", "")
    bad, _ = run_diagnosis(repo, f, learner.id, *SUBJ, Q2, "2x = 14\nx = 7", "")

    def page(session_id):
        at = AppTest.from_file(os.path.join(root, "pages/results.py"), default_timeout=30)
        at.session_state["learner_code"] = "freshresults0001"
        at.session_state["current_session_id"] = session_id
        at.run()
        assert not at.exception
        return " ".join(m.value for m in at.markdown)

    shown_bad = page(bad.id)
    assert "2x = 14" in shown_bad and "Verified incorrect" in shown_bad and "Verified correct" not in shown_bad
    shown_good = page(good.id)
    assert "Verified correct" in shown_good and "Likely misconception" not in shown_good


# ---- Gemini provider --------------------------------------------------------
def test_gemini_configuration_and_error_mapping(monkeypatch):
    from google.genai import errors
    from services.ai_providers.base import AIConfigError
    from services.ai_providers.factory import build_provider
    from services.config import Settings
    s = Settings("gemini", "gemini-2.5-flash", None, "sqlite://", 5, 100)
    with pytest.raises(AIConfigError) as e:
        build_provider(s)
    assert "GEMINI_API_KEY" in str(e.value)
    prov = build_provider(Settings("gemini", "gemini-2.5-flash", "placeholder", "sqlite://", 5, 100))

    def boom(code):
        def _raise(**kw):
            raise errors.APIError(code, {"error": {"message": "x"}})
        return _raise
    for code, word in [(429, "rate limit"), (403, "rejected"), (404, "not found"), (500, "HTTP 500")]:
        monkeypatch.setattr(prov._client.models, "generate_content", boom(code))
        with pytest.raises(AIRequestError) as exc:
            prov.complete("s", "u")
        assert word in str(exc.value)


def test_gemini_key_alias(monkeypatch):
    from services.config import get_api_key
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "placeholder")
    assert get_api_key("gemini") == "placeholder"
