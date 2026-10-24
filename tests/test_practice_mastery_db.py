import pytest

from models.schemas import DiagnosisResult
from services import mastery as M
from services.practice import PracticeService, judge_attempt
from services.ai_providers.base import AIResponseError
from services.diagnosis import DiagnosisService
from services.ai_client import StructuredAI
from services.workflow import ensure_mission, run_diagnosis, submit_attempt
from tests.conftest import DIAGNOSIS, PRACTICE, FakeProvider, ai_with
from utils.validation import InputError

Q = 'Solve "2x + 3 = 11"'


def diag_result():
    return DiagnosisService(ai_with(DIAGNOSIS)).diagnose(Q, "2x = 14\nx = 7")


def test_practice_generation_verifies_and_orders():
    items = PracticeService(ai_with(PRACTICE)).generate(Q, diag_result())
    assert [i.kind for i in items] == ["practice"] * 4 + ["transfer"]
    assert items[-1].expected_answer == "x = 5"
    assert [i.difficulty for i in items[:4]] == ["easy", "medium", "medium", "hard"]


def test_unverifiable_and_duplicate_items_are_dropped_then_fail_after_retry():
    bad = {"practice": [{"question": "Explain love", "hint_1": "h", "hint_2": "h", "difficulty": "easy"}] * 3,
           "transfer": PRACTICE["transfer"]}
    with pytest.raises(AIResponseError):
        PracticeService(ai_with(bad, bad)).generate(Q, diag_result())


def test_original_question_cannot_be_reused_as_transfer():
    same = {**PRACTICE, "transfer": {**PRACTICE["transfer"], "question": "Solve 2x + 3 = 11"}}
    with pytest.raises(AIResponseError):
        PracticeService(ai_with(same, same)).generate(Q, diag_result())


def test_judging_and_bad_input():
    assert judge_attempt("Solve 3x + 5 = 20", "x = 5")[0] is True
    assert judge_attempt("Solve 3x + 5 = 20", "x = 6")[0] is False
    with pytest.raises(InputError):
        judge_attempt("Solve 3x + 5 = 20", "five")


def test_mastery_math():
    assert M.estimate(0, 0) == 0.5
    assert M.estimate(3, 3) > M.estimate(1, 3) > M.estimate(0, 3)
    assert M.credit(True, 1) < M.credit(True, 0) and M.credit(False) == 0
    assert not M.is_assessed(2) and M.is_assessed(3)


def test_empty_dashboard_and_analytics(repo, learner):
    d = repo.dashboard(learner.id)
    assert d["diagnoses"] == 0 and d["attempts"] == 0 and d["accuracy"] is None and d["mastery"] == []
    assert repo.attempts_frame(learner.id).empty and repo.sessions_frame(learner.id).empty
    assert "first diagnosis" in repo.recommend_next(learner.id)["text"]


def test_full_persistence_flow_and_idempotency(repo, learner):
    provider = FakeProvider([DIAGNOSIS, PRACTICE])
    factory = lambda: StructuredAI(provider)
    sess, created = run_diagnosis(repo, factory, learner.id, "Mathematics (Algebra)", "Two-step equations", Q, "2x = 14\nx = 7", "")
    assert created and provider.calls == 1
    # duplicate submit (Streamlit rerun / double click): no second AI call, no second row
    again, created2 = run_diagnosis(repo, factory, learner.id, "Mathematics (Algebra)", "Two-step equations", Q, "2x = 14\nx = 7", "")
    assert not created2 and again.id == sess.id and provider.calls == 1
    assert len(repo.list_sessions(learner.id)) == 1

    qs = ensure_mission(repo, factory, learner.id, sess)
    assert len(qs) == 5 and provider.calls == 2
    assert len(ensure_mission(repo, factory, learner.id, sess)) == 5 and provider.calls == 2  # not regenerated

    # hints: allowed on practice, blocked on transfer
    q0 = qs[0][0]
    assert repo.reveal_hint(q0.id, learner.id) == 1 and repo.reveal_hint(q0.id, learner.id) == 2
    assert repo.reveal_hint(q0.id, learner.id) == 2
    assert repo.reveal_hint(qs[-1][0].id, learner.id) == 0

    # answer every question; AI feedback replies for the wrong one
    provider.replies = [{"feedback": "Check the inverse operation.", "next_tip": "Subtract first."}]
    answers = ["x = 5", "x = 99", "x = 4", "x = 7", "x = 5"]
    for (q, _), ans in zip(qs, answers):
        out, steps = submit_attempt(repo, factory, learner.id, sess, q, ans)
        assert out.created
    dup, _ = submit_attempt(repo, factory, learner.id, sess, qs[0][0], "x = 5")
    assert not dup.created  # one scored attempt per question

    att = repo.attempts_frame(learner.id)
    assert len(att) == 5 and int(att["correct"].sum()) == 4
    assert att[att["kind"] == "transfer"]["correct"].iloc[0]
    row = repo.mastery_rows(learner.id)[0]
    assert row.concept_id == "two_step_equations" and row.attempts == 6  # 1 diagnosis + 5 attempts
    assert row.weighted_total == 1 + 4 + 2  # diagnosis + practice + transfer weight 2
    assert 0 < row.mastery < 1
    assert len(repo.mastery_history_frame(learner.id)) == 6
    done = repo.sessions_frame(learner.id)
    assert done["mission_completed_at"].notna().all()
    d = repo.dashboard(learner.id)
    assert d["diagnoses"] == 1 and d["attempts"] == 5 and abs(d["accuracy"] - 0.8) < 1e-9
    assert d["open_mission"] is None


def test_hint_use_reduces_credit(repo, learner):
    provider = FakeProvider([DIAGNOSIS, PRACTICE])
    factory = lambda: StructuredAI(provider)
    sess, _ = run_diagnosis(repo, factory, learner.id, "S", "T", Q, "2x = 14\nx = 7", "")
    qs = ensure_mission(repo, factory, learner.id, sess)
    q = qs[0][0]
    repo.reveal_hint(q.id, learner.id)
    submit_attempt(repo, factory, learner.id, sess, q, "x = 5")
    row = repo.mastery_rows(learner.id)[0]
    assert row.weighted_credit == pytest.approx(M.HINT_CREDIT)


def test_learner_isolation_and_delete(repo, learner):
    other = repo.get_or_create_learner("otherlearner0002")
    provider = FakeProvider([DIAGNOSIS])
    sess, _ = run_diagnosis(repo, lambda: StructuredAI(provider), learner.id, "S", "T", Q, "2x = 14\nx = 7", "")
    assert repo.get_session(sess.id, other.id) is None
    repo.delete_learner_data(learner.id)
    assert not repo.learner_exists("testlearner0001") and repo.learner_exists("otherlearner0002")


def test_ai_failure_persists_nothing(repo, learner):
    from services.ai_providers.base import AIRequestError
    provider = FakeProvider([AIRequestError("down")])
    with pytest.raises(AIRequestError):
        run_diagnosis(repo, lambda: StructuredAI(provider), learner.id, "S", "T", Q, "2x = 14\nx = 7", "")
    assert repo.list_sessions(learner.id) == []


def test_insufficient_evidence_blocks_mission(repo, learner):
    provider = FakeProvider([])
    f = lambda: StructuredAI(provider)
    sess, _ = run_diagnosis(repo, f, learner.id, "S", "T", Q, "x = 7", "")
    assert sess.status == "insufficient_evidence"
    with pytest.raises(InputError):
        ensure_mission(repo, f, learner.id, sess)
    assert repo.mastery_rows(learner.id) == []  # no invented mastery
