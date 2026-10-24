import os

import pytest

from utils.validation import InputError, clean_text, validate_diagnosis_input, validate_learner_code


def test_input_limits_and_required():
    with pytest.raises(InputError):
        validate_diagnosis_input("", "x", "")
    with pytest.raises(InputError):
        validate_diagnosis_input("q", "", "")
    with pytest.raises(InputError):
        clean_text("a" * 11, 10, "Field")
    assert clean_text("a\x00b", 10, "F") == "ab"
    assert validate_diagnosis_input(" q ", " a ", None)[2] == ""


def test_learner_code():
    assert validate_learner_code("abcdefgh1234") == "abcdefgh1234"
    for bad in ("short", "has space 1234", "../../etc/passwd", ""):
        with pytest.raises(InputError):
            validate_learner_code(bad)


@pytest.fixture
def app_env(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'app.db'}")
    for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("AI_PROVIDER", "anthropic")


def test_app_boots_and_every_page_renders_without_exceptions(app_env):
    from streamlit.testing.v1 import AppTest
    root = os.path.dirname(os.path.dirname(__file__))
    for page in ("pages/home.py", "pages/dashboard.py", "pages/diagnose.py", "pages/results.py",
                 "pages/mission.py", "pages/knowledge_map.py", "pages/analytics.py", "pages/settings.py"):
        at = AppTest.from_file(os.path.join(root, page), default_timeout=30).run()
        assert not at.exception, f"{page}: {at.exception}"


def test_missing_key_shows_configuration_error_and_no_fake_result(app_env):
    from streamlit.testing.v1 import AppTest
    root = os.path.dirname(os.path.dirname(__file__))
    at = AppTest.from_file(os.path.join(root, "pages/diagnose.py"), default_timeout=30).run()
    assert any("AI is not configured" in e.value for e in at.error)
    at.session_state["dx_question"] = 'Solve "2x + 3 = 11"'
    at.session_state["dx_answer"] = "2x = 14\nx = 7"
    at.run()
    submit = [b for b in at.get("form_submit_button")]
    assert submit, "diagnosis form has a submit button"
    submit[0].click()
    at.run()
    assert not at.exception
    assert any("not configured" in e.value or "ANTHROPIC_API_KEY" in e.value for e in at.error)
    from database.session import make_engine, make_session_factory
    from database.repository import Repository
    from sqlalchemy import select, func
    from database.models import DiagnosisSession
    repo = Repository(make_session_factory(make_engine(os.environ["DATABASE_URL"])))
    # nothing saved because no AI call could succeed
    with repo._scope() as s:
        assert s.scalar(select(func.count(DiagnosisSession.id))) == 0


def test_entrypoint_with_navigation_boots(app_env):
    from streamlit.testing.v1 import AppTest
    root = os.path.dirname(os.path.dirname(__file__))
    at = AppTest.from_file(os.path.join(root, "app.py"), default_timeout=30).run()
    assert not at.exception


def test_ui_flow_results_and_mission_with_stored_records(app_env, monkeypatch):
    """Seed real DB rows through the service layer (scripted AI), then drive the actual pages."""
    from streamlit.testing.v1 import AppTest
    from database.repository import Repository
    from database.session import init_schema, make_engine, make_session_factory
    from services.ai_client import StructuredAI
    from services.workflow import ensure_mission, run_diagnosis
    from tests.conftest import DIAGNOSIS, PRACTICE, FakeProvider

    root = os.path.dirname(os.path.dirname(__file__))
    engine = make_engine(os.environ["DATABASE_URL"])
    init_schema(engine)
    repo = Repository(make_session_factory(engine))
    learner = repo.get_or_create_learner("uiflowlearner001")
    provider = FakeProvider([DIAGNOSIS, PRACTICE])
    f = lambda: StructuredAI(provider)
    sess, _ = run_diagnosis(repo, f, learner.id, "Mathematics (Algebra)", "Two-step equations",
                            'Solve "2x + 3 = 11"', "2x = 14\nx = 7", "")
    ensure_mission(repo, f, learner.id, sess)

    res = AppTest.from_file(os.path.join(root, "pages/results.py"), default_timeout=30)
    res.session_state["learner_code"] = "uiflowlearner001"
    res.run()
    assert not res.exception
    assert "Added instead of subtracting" in " ".join(m.value for m in res.markdown)

    ms = AppTest.from_file(os.path.join(root, "pages/mission.py"), default_timeout=30)
    ms.session_state["learner_code"] = "uiflowlearner001"
    ms.run()
    assert not ms.exception
    assert "Solve x + 4 = 9" in " ".join(m.value for m in ms.markdown)
    assert "x = 5" not in " ".join(m.value for m in ms.markdown)  # answer hidden before attempt
    ms.text_input[0].set_value("x = 99")
    ms.get("form_submit_button")[0].click()
    ms.run()
    assert not ms.exception
    assert any("Not quite" in m.value for m in ms.markdown)
    assert repo.dashboard(learner.id)["attempts"] == 1

    dash = AppTest.from_file(os.path.join(root, "pages/dashboard.py"), default_timeout=30)
    dash.session_state["learner_code"] = "uiflowlearner001"
    dash.run()
    assert not dash.exception
