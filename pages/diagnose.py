import streamlit as st

from components.state import get_context
from components.ui import page_header, render_ai_error
from models.concepts import PLANNED_SUBJECTS, SUBJECTS
from services.ai_providers.base import AIConfigError, AIError
from services.workflow import run_diagnosis
from utils.validation import MAX_ANSWER, MAX_QUESTION, MAX_REASONING, InputError, validate_diagnosis_input

ctx = get_context()
page_header("Diagnosis workspace", "Submit a problem and your working. The more steps you show, the more precise the diagnosis.",
            "Trace")

SAMPLE = {"dx_question": 'Solve "2x + 3 = 11"', "dx_answer": "2x = 14\nx = 7", "dx_reasoning": ""}


def _load_sample():
    st.session_state.update(SAMPLE)


def _execute(payload: dict) -> None:
    st.session_state.pop("dx_error", None)
    session = None
    with st.spinner("Verifying your work and tracing the misconception…"):
        try:
            session, _ = run_diagnosis(ctx.repo, ctx.ai_factory(), ctx.learner_id, **payload)
        except InputError as exc:
            st.error(str(exc))
        except AIError as exc:
            st.session_state["dx_error"] = exc
        except Exception:
            st.error("Unexpected error while saving or analysing. Your input was not lost; try again.")
    if session is not None:
        st.session_state["current_session_id"] = session.id
        for stale in ("results_pick", "mission_pick", "ms_feedback", "ms_error"):
            st.session_state.pop(stale, None)
        st.switch_page("pages/results.py")


if not ctx.settings.ai_configured:
    render_ai_error(AIConfigError(""), ctx.settings)

st.button("Load sample input (2x + 3 = 11)", on_click=_load_sample, help="Fills the fields only. The analysis still runs the real pipeline.")

with st.form("dx_form"):
    subject = st.selectbox("Subject", list(SUBJECTS))
    topic = st.selectbox("Topic", SUBJECTS[subject]["topics"])
    question = st.text_area("Question", key="dx_question", height=80, max_chars=MAX_QUESTION,
                            placeholder='e.g. Solve "2x + 3 = 11"')
    answer = st.text_area("Your answer (one step per line)", key="dx_answer", height=130, max_chars=MAX_ANSWER,
                          placeholder="2x = 14\nx = 7")
    reasoning = st.text_area("Your reasoning (optional)", key="dx_reasoning", height=90, max_chars=MAX_REASONING,
                             placeholder="Explain in your own words what you did and why.")
    submitted = st.form_submit_button("Analyse my work", type="primary")
st.caption(f"Planned subjects: {', '.join(PLANNED_SUBJECTS)}. Only mathematics is supported today.")

if submitted:
    try:
        q, a, r = validate_diagnosis_input(question, answer, reasoning)
        st.session_state["dx_pending"] = dict(subject=subject, topic=topic, question=q, answer=a, reasoning=r)
        _execute(st.session_state["dx_pending"])
    except InputError as exc:
        st.error(str(exc))

err = st.session_state.get("dx_error")
if err is not None:
    can_retry = render_ai_error(err, ctx.settings)
    if can_retry and st.session_state.get("dx_pending") and st.button("Retry analysis", type="primary"):
        _execute(st.session_state["dx_pending"])
