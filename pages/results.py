import streamlit as st

from components.state import get_context
from components.ui import card, chip, empty_state, esc, page_header, steps_block
from models.concepts import concept_name
from models.schemas import DiagnosisResult

ctx = get_context()
page_header("Diagnosis results", "A hypothesis grounded in your own words, with the evidence shown.", "Trace")

sessions = ctx.repo.list_sessions(ctx.learner_id)
if not sessions:
    empty_state("No diagnoses yet", "Submit a problem in the diagnosis workspace to see results here.")
    if st.button("Go to diagnosis workspace", type="primary"):
        st.switch_page("pages/diagnose.py")
    st.stop()

ids = [s.id for s in sessions]
# The selection lives in ONE keyed widget; diagnose.py resets it after each new submission,
# so a previous result can never be shown for a different submission.
if st.session_state.get("results_pick") not in ids:
    cur = st.session_state.get("current_session_id")
    st.session_state["results_pick"] = cur if cur in ids else ids[0]
by_id = {s.id: s for s in sessions}
chosen = st.selectbox("Diagnosis", ids, key="results_pick",
                      format_func=lambda i: f"{by_id[i].created_at:%b %d %H:%M} · {by_id[i].question[:48]}")
st.session_state["current_session_id"] = chosen
sess = by_id[chosen]
res = DiagnosisResult.model_validate(sess.result)
an = res.analysis

card("Submitted work", f"<p><b>Question:</b> {esc(sess.question)}</p>"
     f"<p><b>Your answer:</b></p><div class='mt-step'>{esc(sess.answer).replace(chr(10), '<br>')}</div>"
     + (f"<p><b>Your reasoning:</b> {esc(sess.reasoning)}</p>" if sess.reasoning else ""))


def checks_panel(expanded: bool = True):
    with st.expander("Independent math checks (symbolic, not AI)", expanded=expanded):
        if not an.steps:
            st.caption("No readable steps were found.")
        for s in an.steps:
            icon = "✓" if s.consistent else "✗" if s.consistent is False else "·"
            st.markdown(f"`{icon}` `{s.text}`: {s.note or 'not checked'}")
        for sig in an.signals:
            st.markdown(f"- {sig}")
        for n in res.verification_notes + an.notes:
            st.caption(n)


if res.status == "correct":
    card("Verified correct", f"<p>{esc(res.message)}</p>", "ok")
    if res.correct_solution_steps:
        st.markdown("#### Reference solution")
        steps_block(res.correct_solution_steps)
    checks_panel(False)
    st.stop()

if res.status == "insufficient_evidence":
    card("Not enough evidence to diagnose", f"<p>{esc(res.message)}</p>", "warn")
    if an.final_answer_correct is False:
        st.markdown(chip("Final answer verified incorrect", "err"), unsafe_allow_html=True)
    checks_panel()
    if st.button("Add more working", type="primary"):
        st.switch_page("pages/diagnose.py")
    st.stop()

if res.status == "incorrect":
    card("Verified incorrect", f"<p>{esc(res.message)}</p>", "err")
    st.markdown("#### Correct solution")
    if res.correct_solution_steps:
        steps_block(res.correct_solution_steps)
    if res.correct_answer:
        st.success(f"Verified answer: {res.correct_answer}")
    checks_panel()
    c1, c2 = st.columns(2)
    if c1.button("Add more working", type="primary"):
        st.switch_page("pages/diagnose.py")
    if c2.button("Practice this concept"):
        st.switch_page("pages/mission.py")
    st.stop()

d = res.diagnosis
conf_kind = {"high": "ok", "medium": "warn", "low": "err"}[res.confidence or "low"]
st.markdown(chip("Verified incorrect", "err") + chip(f"Confidence: {res.confidence}", conf_kind)
            + chip(concept_name(res.concept_id or ""), "accent") + chip(d.misconception_category.replace("_", " "))
            + chip(f"{res.provider} · {res.model}"), unsafe_allow_html=True)
st.caption("Your answer is verified wrong by a math engine. The misconception is a hypothesis; confidence reflects how directly "
           "your written work supports it, not what you were thinking.")
card(f"Likely misconception: {d.misconception_label}", f"<p>{esc(d.misconception_statement)}</p>", "accent")

t1, t2, t3 = st.tabs(["Evidence & reasoning", "Correct solution", "Mini-lesson"])
with t1:
    st.markdown("**Evidence from your work** (quoted)")
    for e in d.evidence:
        st.markdown(f'<div class="mt-card"><span class="mt-quote">{esc(e.quote)}</span><p>{esc(e.observation)}</p></div>', unsafe_allow_html=True)
    if d.incorrect_step_quote:
        card("Incorrect reasoning step", f"<span class='mt-quote'>{esc(d.incorrect_step_quote)}</span><p>{esc(d.why_incorrect)}</p>", "err")
    else:
        card("Why it is incorrect", f"<p>{esc(d.why_incorrect)}</p>", "err")
    card("Inference, not certainty", f"<p>{esc(d.inference_note)}</p>", "warn")
    card("Explanation for you", f"<p>{esc(d.explanation)}</p>")
    checks_panel()
with t2:
    if res.correct_solution_steps:
        steps_block(res.correct_solution_steps)
    if res.correct_answer:
        st.success(f"Verified answer: {res.correct_answer}")
    else:
        st.warning("The correct answer could not be independently verified for this problem.")
with t3:
    ml = d.mini_lesson
    card(ml.title, f"<p><b>Principle.</b> {esc(ml.principle)}</p>", "accent")
    st.markdown("**Worked example**")
    st.markdown(f'<div class="mt-step" style="white-space:pre-wrap">{esc(ml.worked_example)}</div>', unsafe_allow_html=True)
    st.markdown("**Key takeaways**")
    for k in ml.key_takeaways:
        st.markdown(f"- {k}")

st.write("")
card("Recommended practice", "<p>A repair mission with targeted questions, hints, and an unseen transfer question will test whether the idea is fixed.</p>")
if st.button("Start repair mission", type="primary"):
    st.switch_page("pages/mission.py")
