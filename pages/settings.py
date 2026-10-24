import streamlit as st
from sqlalchemy.engine import make_url

from components.state import get_context
from components.ui import card, esc, page_header, render_config_help
from services.ai_providers.base import AIError
from services.ai_providers.factory import build_provider
from services.config import DEFAULT_MODELS, KEY_ENV, SUPPORTED_PROVIDERS
from utils.validation import InputError, validate_learner_code

ctx = get_context()
s = ctx.settings
page_header("Settings & AI configuration", "API keys are read from environment variables or Streamlit secrets and are never displayed.", "Settings")

st.markdown("### AI provider")
if s.ai_configured:
    card("AI is configured", f"<p>Provider <b>{esc(s.provider)}</b>, model <b>{esc(s.model)}</b>. Key variable <code>{esc(s.key_env_name)}</code> is set (value hidden).</p>", "ok")
else:
    render_config_help(s)

with st.expander("Change provider or model for this browser session"):
    prov = st.selectbox("Provider", SUPPORTED_PROVIDERS, index=SUPPORTED_PROVIDERS.index(s.provider) if s.provider in SUPPORTED_PROVIDERS else 0)
    model = st.text_input("Model", value=s.model if prov == s.provider else DEFAULT_MODELS[prov])
    if st.button("Apply for this session"):
        st.session_state["ai_provider_override"], st.session_state["ai_model_override"] = prov, model.strip()
        st.rerun()
    st.caption(f"Keys cannot be entered here by design. Set {KEY_ENV[prov]} in .env or Streamlit secrets. Permanent defaults: AI_PROVIDER and AI_MODEL.")

if st.button("Test AI connection"):
    try:
        with st.spinner("Sending a minimal request…"):
            build_provider(s).complete('Reply with the JSON object {"ok": true}', "ping")
        st.success("The provider accepted the request and replied.")
    except AIError as exc:
        st.error(str(exc))

st.markdown("### Database")
url = make_url(s.database_url)
backend = url.get_backend_name()
st.markdown(f"Backend: **{backend}**")
if backend == "sqlite":
    st.warning("SQLite is for local development. On Streamlit Community Cloud the local file is not guaranteed to persist; use hosted PostgreSQL via DATABASE_URL.")
else:
    st.success("Using a networked database (credentials hidden).")

st.markdown("### Learner code")
st.markdown("Your progress is stored under an anonymous code, **not** an account. Anyone holding the code can open this data, so keep it private.")
st.code(ctx.learner_code)
with st.form("resume"):
    code = st.text_input("Resume with an existing code")
    if st.form_submit_button("Switch learner"):
        try:
            code = validate_learner_code(code)
            if not ctx.repo.learner_exists(code):
                st.error("No learner with that code exists in this database.")
            else:
                st.session_state["learner_code"] = code
                st.query_params["learner"] = code
                st.session_state.pop("current_session_id", None)
                st.rerun()
        except InputError as exc:
            st.error(str(exc))

st.markdown("### Delete my data")
if st.checkbox("I understand this permanently deletes all my diagnoses, attempts and mastery"):
    if st.button("Delete all my data"):
        ctx.repo.delete_learner_data(ctx.learner_id)
        for k in ("learner_code", "current_session_id", "ms_feedback"):
            st.session_state.pop(k, None)
        st.query_params.clear()
        st.rerun()
