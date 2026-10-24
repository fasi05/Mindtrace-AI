"""MINDTRACE AI entry point: streamlit run app.py"""
import streamlit as st

st.set_page_config(page_title="MindTrace AI", page_icon="◈", layout="wide", initial_sidebar_state="expanded")

from components.state import get_context  # noqa: E402
from components.ui import esc, inject_css  # noqa: E402

inject_css()
ctx = get_context()

with st.sidebar:
    st.markdown('<div class="mt-brand">Mind<span>Trace</span> AI</div>'
                '<div class="mt-tag">Don\'t just correct the answer. Discover the misconception.</div>',
                unsafe_allow_html=True)
    st.write("")

pages = [
    st.Page("pages/home.py", title="Overview", default=True, url_path="home"),
    st.Page("pages/dashboard.py", title="Dashboard", url_path="dashboard"),
    st.Page("pages/diagnose.py", title="Diagnosis workspace", url_path="diagnose"),
    st.Page("pages/results.py", title="Diagnosis results", url_path="results"),
    st.Page("pages/mission.py", title="Repair mission", url_path="mission"),
    st.Page("pages/knowledge_map.py", title="Knowledge map", url_path="knowledge-map"),
    st.Page("pages/analytics.py", title="Progress analytics", url_path="analytics"),
    st.Page("pages/settings.py", title="Settings", url_path="settings"),
]
nav = st.navigation(pages)

with st.sidebar:
    ok = ctx.settings.ai_configured
    st.markdown(
        f'<div class="mt-side-card"><span class="mt-chip">'
        f'{"AI configured" if ok else "AI not configured"}</span>'
        f'<p>{esc(ctx.settings.provider)} · {esc(ctx.settings.model)}</p></div>',
        unsafe_allow_html=True)

nav.run()
