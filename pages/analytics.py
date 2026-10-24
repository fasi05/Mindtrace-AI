import pandas as pd
import streamlit as st

from components import charts
from components.state import get_context
from components.theme import stretch
from components.ui import empty_state, page_header
from services import mastery as M

ctx = get_context()
page_header("Progress analytics", "Charts are drawn from saved records only. Nothing is estimated or back-filled.", "Analytics")
att = ctx.repo.attempts_frame(ctx.learner_id)
sess = ctx.repo.sessions_frame(ctx.learner_id)
mastery_rows = ctx.repo.mastery_rows(ctx.learner_id)

if att.empty and sess.empty:
    empty_state("No data to analyse yet", "Complete a diagnosis and a repair mission to see analytics.")
    st.stop()

st.markdown("### Accuracy over time")
if att.empty:
    st.caption("No practice attempts yet.")
else:
    st.plotly_chart(charts.accuracy_over_time(att), **stretch())
    st.markdown("### Practice activity")
    st.plotly_chart(charts.activity_by_day(att), **stretch())

st.markdown("### Concept mastery")
if mastery_rows:
    st.plotly_chart(charts.mastery_bars(mastery_rows), **stretch())
    st.caption(f"Grey bars have fewer than {M.MIN_EVIDENCE} attempts and are not considered assessed.")
else:
    st.caption("No mastery records yet.")

st.markdown("### Repeated misconceptions")
found = sess[sess["status"] == "misconception_found"] if not sess.empty else sess
if found.empty:
    st.caption("No misconceptions diagnosed yet.")
else:
    st.plotly_chart(charts.misconception_counts(found), **stretch())
    if (found.groupby("misconception_category").size() >= 2).any():
        st.caption("Amber bars: the same category was diagnosed more than once.")

st.markdown("### Before and after repair missions")
done = sess[sess["mission_completed_at"].notna()] if not sess.empty else sess
if done.empty or att.empty:
    st.caption("Complete a repair mission to compare your original answer with practice and transfer results.")
else:
    rows = []
    for i, (_, s) in enumerate(done.iterrows(), 1):
        a = att[att["session_id"] == s["id"]]
        p, t = a[a["kind"] == "practice"], a[a["kind"] == "transfer"]
        if p.empty or t.empty:
            continue
        rows.append(dict(label=f"Mission {i}", diagnosis=0.0 if s["status"] == "misconception_found" else 1.0,
                         practice=float(p["correct"].mean()), transfer=float(t["correct"].iloc[0])))
    if rows:
        st.plotly_chart(charts.before_after(pd.DataFrame(rows)), **stretch())
        st.caption(f"{len(rows)} completed mission(s). This shows recorded results only; it is not evidence of a learning effect.")
