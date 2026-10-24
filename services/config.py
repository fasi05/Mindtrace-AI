"""Configuration from environment variables, .env, or Streamlit secrets. Never exposes secret values."""
from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env", override=False)

DEFAULT_MODELS = {"anthropic": "claude-sonnet-4-5", "openai": "gpt-4o-mini", "gemini": "gemini-2.5-flash"}
KEY_ENV = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY", "gemini": "GEMINI_API_KEY"}
# Accepted alternative variable names (checked after the primary one).
KEY_ALIASES = {"gemini": ("GOOGLE_API_KEY",)}
SUPPORTED_PROVIDERS = tuple(KEY_ENV)


def _get(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.environ.get(name)
    if value:
        return value.strip()
    try:  # Streamlit secrets (cloud, or .streamlit/secrets.toml locally)
        import streamlit as st

        if name in st.secrets:
            return str(st.secrets[name]).strip()
    except Exception:
        pass
    return default


def get_api_key(provider: str) -> Optional[str]:
    for name in (KEY_ENV.get(provider), *KEY_ALIASES.get(provider, ())):
        if name and (value := _get(name)):
            return value
    return None


def _int(name: str, default: int) -> int:
    try:
        return int(_get(name, str(default)) or default)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    provider: str
    model: str
    api_key: Optional[str]
    database_url: str
    timeout: int
    max_tokens: int

    @property
    def key_env_name(self) -> str:
        return KEY_ENV.get(self.provider, "API_KEY")

    @property
    def ai_configured(self) -> bool:
        return self.provider in SUPPORTED_PROVIDERS and bool(self.api_key)

    def with_overrides(self, provider: Optional[str] = None, model: Optional[str] = None) -> "Settings":
        """Session-level, non-secret overrides (provider/model)."""
        new_provider = provider or self.provider
        new_model = model or (self.model if new_provider == self.provider else DEFAULT_MODELS.get(new_provider, ""))
        return replace(self, provider=new_provider, model=new_model,
                       api_key=get_api_key(new_provider) if new_provider != self.provider else self.api_key)


def normalize_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg2://" + url[len("postgresql://"):]
    return url


def load_settings() -> Settings:
    provider = (_get("AI_PROVIDER", "anthropic") or "anthropic").lower()
    model = _get("AI_MODEL") or DEFAULT_MODELS.get(provider, "")
    key = get_api_key(provider) if provider in KEY_ENV else None
    db = _get("DATABASE_URL") or f"sqlite:///{(ROOT / 'data' / 'mindtrace.db').as_posix()}"
    return Settings(provider=provider, model=model, api_key=key,
                    database_url=normalize_database_url(db),
                    timeout=_int("AI_TIMEOUT_SECONDS", 60), max_tokens=_int("AI_MAX_TOKENS", 3000))
