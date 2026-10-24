import streamlit as st

from components.state import get_context
from components.ui import card, empty_state, esc, mastery_bar, metric, page_header
from models.concepts import concept_name
from services import mastery as M

ctx = get_context()
page_header("Learner dashboard", "Everything here is calculated from your saved diagnoses and attempts.", "Overview")
d = ctx.repo.dashboard(ctx.learner_id)

c1, c2, c3 = st.columns(3)
with c1:
    metric("Diagnoses completed", str(d["diagnoses"]))
with c2:
    metric("Practice attempts", str(d["attempts"]))
with c3:
    metric("Accuracy", "—" if d["accuracy"] is None else f"{d['accuracy']:.0%}",
           "no attempts yet" if d["accuracy"] is None else "practice + transfer")
st.write("")

rec = ctx.repo.recommend_next(ctx.learner_id, d)
card("Recommended next activity", f"<p>{esc(rec['text'])}</p>", "accent")
if rec["action"] == "mission":
    if st.button("Continue repair mission", type="primary"):
        st.session_state["current_session_id"] = rec["session_id"]
        st.switch_page("pages/mission.py")
elif st.button("Open diagnosis workspace", type="primary"):
    st.switch_page("pages/diagnose.py")

left, right = st.columns([3, 2])
with left:
    st.markdown("### Concept mastery")
    if not d["mastery"]:
        empty_state("No mastery data yet", "Mastery appears after you complete a diagnosis or practice. Nothing is pre-filled.")
    for r in sorted(d["mastery"], key=lambda r: -r.mastery):
        assessed = M.is_assessed(r.attempts)
        mastery_bar(concept_name(r.concept_id), r.mastery if assessed else None,
                    f"{r.attempts}/{M.MIN_EVIDENCE} attempts" if not assessed else f"{r.attempts} attempts")
with right:
    st.markdown("### Strongest")
    if d["strongest"]:
        for r in d["strongest"]:
            st.markdown(f"**{esc(concept_name(r.concept_id))}** · {r.mastery:.0%}")
    else:
        st.caption(f"Needs at least {M.MIN_EVIDENCE} attempts on a concept.")
    st.markdown("### Needs improvement")
    if d["weakest"]:
        for r in d["weakest"]:
            st.markdown(f"**{esc(concept_name(r.concept_id))}** · {r.mastery:.0%}")
    else:
        st.caption("None identified yet.")

st.markdown("### Recent activity")
if not d["recent"]:
    empty_state("No activity yet", "Your diagnoses and practice will be listed here.")
for a in d["recent"]:
    st.markdown(f'<div class="mt-card" style="padding:.6rem 1rem;margin-bottom:.4rem"><span class="mt-muted" style="font-size:.8rem">'
                f'{a.created_at:%Y-%m-%d %H:%M} UTC</span> &nbsp; {esc(a.detail)}</div>', unsafe_allow_html=True)
