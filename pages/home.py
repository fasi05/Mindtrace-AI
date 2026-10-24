import streamlit as st

from components.state import get_context
from components.ui import card, esc, page_header

ctx = get_context()
st.markdown("""
<div class="mt-hero">
<div class="mt-eyebrow">AI learning diagnostics</div>
<h1>Don't just correct the answer.<br>Discover the misconception.</h1>
<p>A wrong answer is a symptom. MindTrace reads the learner's actual working, finds the likely faulty idea behind it,
checks the maths symbolically, and builds a repair mission that proves whether the idea was fixed.</p>
</div>""", unsafe_allow_html=True)
if st.button("Start a diagnosis", type="primary"):
    st.switch_page("pages/diagnose.py")
st.write("")

c1, c2, c3 = st.columns(3)
with c1:
    card("The problem", "<p>Tutors and chatbots usually fix the answer. The learner repeats the same flawed idea on the next problem, because the cause was never named.</p>")
with c2:
    card("The approach", "<p>A diagnosis grounded in quoted evidence from the submitted work, separated from inference, and cross-checked by a symbolic maths engine.</p>")
with c3:
    card("The value", "<p>A targeted mini-lesson, practice that attacks the specific misconception, and an unseen transfer question that tests real understanding.</p>")

st.markdown("### How the Misconception Trace Engine works")
steps = [("1 · Verify", "Every line of the submitted work is checked with sympy. No AI is trusted as a calculator."),
         ("2 · Trace", "The AI proposes a likely misconception and must quote the learner's own steps as evidence."),
         ("3 · Repair", "Targeted practice with hints; each answer is graded deterministically."),
         ("4 · Transfer", "A fresh question, no hints. Mastery updates only from real, recorded attempts.")]
cols = st.columns(4)
for col, (t, d) in zip(cols, steps):
    with col:
        card(t, f"<p>{esc(d)}</p>", "accent")
st.caption("Fully supported subject: algebra and equation solving. Diagnoses are hypotheses shown with a confidence level, never certainties.")
