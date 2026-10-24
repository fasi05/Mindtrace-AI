"""Per-run application context: settings, repository, anonymous learner."""
from __future__ import annotations

import uuid
from dataclasses import dataclass

import streamlit as st

from database.repository import Repository
from database.session import init_schema, make_engine, make_session_factory
from services.config import Settings, load_settings
from services.workflow import build_ai
from utils.validation import InputError, validate_learner_code


@st.cache_resource(show_spinner=False)
def _repository(database_url: str) -> Repository:
    engine = make_engine(database_url)
    init_schema(engine)
    return Repository(make_session_factory(engine))


def current_settings() -> Settings:
    settings = load_settings()
    prov = st.session_state.get("ai_provider_override")
    model = st.session_state.get("ai_model_override")
    if prov or model:
        settings = settings.with_overrides(prov, model)
    return settings


@dataclass
class AppContext:
    settings: Settings
    repo: Repository
    learner_id: int
    learner_code: str

    def ai_factory(self):
        return lambda: build_ai(self.settings)


def get_context() -> AppContext:
    settings = current_settings()
    repo = _repository(settings.database_url)
    code = st.session_state.get("learner_code") or st.query_params.get("learner")
    try:
        code = validate_learner_code(code or "")
    except InputError:
        code = uuid.uuid4().hex[:20]
    learner = repo.get_or_create_learner(code)
    st.session_state["learner_code"] = code
    if st.query_params.get("learner") != code:
        st.query_params["learner"] = code
    return AppContext(settings, repo, learner.id, code)


def goto(page: str) -> None:
    st.switch_page(page)
