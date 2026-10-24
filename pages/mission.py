import streamlit as st

from components.state import get_context
from components.ui import card, chip, empty_state, esc, mastery_bar, page_header, render_ai_error, steps_block
from models.concepts import concept_name
from models.schemas import DiagnosisResult
from services import mastery as M
from services.ai_providers.base import AIError
from services.workflow import ensure_mission, submit_attempt
from utils.validation import InputError

ctx = get_context()
page_header("Repair mission", "One question at a time. Hints are optional; answers stay hidden until you attempt.", "Repair")

sessions = [s for s in ctx.repo.list_sessions(ctx.learner_id) if s.status != "insufficient_evidence"]
if not sessions:
    empty_state("No mission available", "Run a diagnosis first. A mission is built from the misconception it finds.")
    if st.button("Go to diagnosis workspace", type="primary"):
        st.switch_page("pages/diagnose.py")
    st.stop()

ids = [s.id for s in sessions]
cur = st.session_state.get("current_session_id")
if st.session_state.get("mission_pick") not in ids:
    st.session_state["mission_pick"] = cur if cur in ids else ids[0]
chosen = st.selectbox("Mission for diagnosis", ids, key="mission_pick",
                      format_func=lambda i: next(f"{s.created_at:%b %d %H:%M} · {s.question[:48]}" for s in sessions if s.id == i))
st.session_state["current_session_id"] = chosen
sess = next(s for s in sessions if s.id == chosen)
res = DiagnosisResult.model_validate(sess.result)
qs = ctx.repo.get_questions(sess.id)

if not qs:
    note = res.diagnosis.misconception_label if res.diagnosis else "general reinforcement"
    card("Mission not generated yet", f"<p>Targeted practice for: <b>{esc(note)}</b>. Every question is verified by a maths engine before you see it.</p>")
    if st.session_state.get("ms_error") is not None:
        retry = render_ai_error(st.session_state["ms_error"], ctx.settings)
    if st.button("Generate repair mission", type="primary"):
        st.session_state.pop("ms_error", None)
        try:
            with st.spinner("Writing and verifying practice questions…"):
                ensure_mission(ctx.repo, ctx.ai_factory(), ctx.learner_id, sess)
            st.rerun()
        except (AIError, InputError) as exc:
            st.session_state["ms_error"] = exc
            st.rerun()
    st.stop()

total, answered = len(qs), sum(1 for _, a in qs if a)
st.progress(answered / total, text=f"{answered} of {total} questions answered")

fb = st.session_state.get("ms_feedback")
if fb and fb["session_id"] == sess.id:
    if fb["correct"]:
        card("Correct", f"<p>Verified: <b>{esc(fb['expected'])}</b>. {'' if not fb['hints'] else 'Credited partially because hints were used.'}</p>", "ok")
    else:
        body = f"<p>Your answer <span class='mt-quote'>{esc(fb['answer'])}</span> is not correct. Verified answer: <b>{esc(fb['expected'])}</b>.</p>"
        if fb.get("ai"):
            body += f"<p>{esc(fb['ai']['feedback'])}</p>" + (f"<p><i>{esc(fb['ai']['next_tip'])}</i></p>" if fb['ai'].get('next_tip') else "")
        else:
            body += "<p class='mt-muted'>AI coaching was unavailable; the verified solution is shown below.</p>"
        card("Not quite", body, "err")
    if fb["steps"] and (not fb["correct"]):
        steps_block(fb["steps"])
    elif fb["steps"]:
        with st.expander("Show worked solution"):
            steps_block(fb["steps"])

if answered < total:
    q, _ = next((q, a) for q, a in qs if a is None)
    n = [x.id for x, _ in qs].index(q.id) + 1
    kind = "Transfer question" if q.kind == "transfer" else f"Question {n} of {total}"
    st.markdown(chip(kind, "accent") + chip(q.difficulty) + (chip("No hints", "warn") if q.kind == "transfer" else ""), unsafe_allow_html=True)
    card("", f"<h3 style='margin:.2rem 0'>{esc(q.question)}</h3>", "elev")
    if q.kind == "transfer":
        st.caption("This checks whether the idea transfers to a fresh problem, so hints are off.")
    else:
        for i in range(q.hints_revealed):
            st.info(f"Hint {i + 1}: {q.hints[i]}")
        if q.hints_revealed < len(q.hints) and st.button(f"Show hint {q.hints_revealed + 1}", key=f"hint_{q.id}"):
            ctx.repo.reveal_hint(q.id, ctx.learner_id)
            st.rerun()
    with st.form(f"ans_{q.id}"):
        raw = st.text_input("Your answer", placeholder="x = 5", max_chars=200)
        go = st.form_submit_button("Submit answer", type="primary")
    if go:
        try:
            outcome, steps = submit_attempt(ctx.repo, ctx.ai_factory(), ctx.learner_id, sess, q, raw)
            a = outcome.attempt
            st.session_state["ms_feedback"] = dict(session_id=sess.id, correct=a.correct, answer=a.answer, expected=q.expected_answer,
                                                   steps=steps, ai=(a.feedback or {}).get("ai"), hints=a.hints_used)
            st.rerun()
        except InputError as exc:
            st.error(str(exc))
else:
    attempts = [(q, a) for q, a in qs]
    practice = [a for q, a in attempts if q.kind == "practice"]
    transfer = next((a for q, a in attempts if q.kind == "transfer"), None)
    p_acc = sum(a.correct for a in practice) / len(practice) if practice else 0
    st.markdown("### Mission complete")
    c1, c2, c3 = st.columns(3)
    c1.metric("Practice accuracy", f"{p_acc:.0%}", f"{sum(a.correct for a in practice)}/{len(practice)}")
    c2.metric("Transfer question", "Correct" if transfer and transfer.correct else "Incorrect")
    c3.metric("Hints used", str(sum(a.hints_used for a in practice)))
    rows = [r for r in ctx.repo.mastery_rows(ctx.learner_id) if r.concept_id == res.concept_id]
    if rows:
        r = rows[0]
        mastery_bar(concept_name(r.concept_id), r.mastery if M.is_assessed(r.attempts) else None,
                    f"{r.attempts} attempts recorded")
    st.caption("One mission is a single data point. Repeat on new problems before concluding a misconception is resolved.")
    if st.button("Run another diagnosis", type="primary"):
        st.switch_page("pages/diagnose.py")

with st.expander("Practice history for this mission"):
    for q, a in qs:
        if a:
            st.markdown(f"{'✓' if a.correct else '✗'} `{q.question}` → `{a.answer}` · {q.kind} · hints {a.hints_used}")
        else:
            st.markdown(f"· `{q.question}` · {q.kind} · not attempted")
