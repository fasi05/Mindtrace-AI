"""UI building blocks (cards, chips, bars, shared error rendering). Styling lives in components/theme.py."""
from __future__ import annotations

from html import escape as esc

import streamlit as st

from services.ai_providers.base import AIConfigError, AIError
from services.config import KEY_ENV, Settings

from components.theme import C, inject_css, stretch  # noqa: F401  (re-exported for pages)


def page_header(title: str, subtitle: str = "", eyebrow: str = "") -> None:
    html = (f'<div class="mt-eyebrow">{esc(eyebrow)}</div>' if eyebrow else "") + f"<h1 style='margin:.1rem 0 .3rem'>{esc(title)}</h1>"
    if subtitle:
        html += f'<p class="mt-muted" style="margin-top:0;max-width:720px">{esc(subtitle)}</p>'
    st.markdown(html, unsafe_allow_html=True)


def card(title: str, body_html: str = "", kind: str = "") -> None:
    """body_html must already be escaped by the caller (use esc())."""
    t = f"<h4>{esc(title)}</h4>" if title else ""
    st.markdown(f'<div class="mt-card {kind}">{t}{body_html}</div>', unsafe_allow_html=True)


def metric(label: str, value: str, hint: str = "") -> None:
    st.markdown(f'<div class="mt-metric"><div class="l">{esc(label)}</div><div class="v">{esc(value)}</div>'
                f'<div class="h">{esc(hint)}</div></div>', unsafe_allow_html=True)


def chip(text: str, kind: str = "") -> str:
    return f'<span class="mt-chip {kind}">{esc(text)}</span>'


def mastery_bar(label: str, value: float | None, detail: str = "") -> None:
    if value is None:
        pct, color, txt = 0, C["neutral"], "Not enough data"
    else:
        pct = round(value * 100)
        color = C["success"] if value >= 0.75 else C["warn"] if value >= 0.5 else C["error"]
        txt = f"{pct}%"
    st.markdown(f'<div class="mt-row"><span>{esc(label)}</span><span class="mt-muted">{esc(txt)}'
                f'{" · " + esc(detail) if detail else ""}</span></div>'
                f'<div class="mt-bar"><div style="width:{pct}%;background:{color}"></div></div>', unsafe_allow_html=True)


def steps_block(steps: list[str], bad: set[int] | None = None, good: set[int] | None = None) -> None:
    bad, good = bad or set(), good or set()
    st.markdown("".join(f'<div class="mt-step {"bad" if i in bad else "good" if i in good else ""}">{esc(s)}</div>'
                        for i, s in enumerate(steps)), unsafe_allow_html=True)


def empty_state(title: str, text: str) -> None:
    card(title, f"<p>{esc(text)}</p>")


def render_config_help(settings: Settings) -> None:
    env = KEY_ENV.get(settings.provider, "API_KEY")
    st.error("AI is not configured. Diagnosis, lessons and practice generation need a real AI provider key.")
    st.markdown(f"""
**Local (Windows / VS Code):** copy `.env.example` to `.env`, set `AI_PROVIDER={settings.provider}` and `{env}=<your key>` (Gemini also accepts `GOOGLE_API_KEY`), then restart `streamlit run app.py`.

**Streamlit Community Cloud:** App → Settings → Secrets, add `{env} = "<your key>"` (see `.streamlit/secrets.toml.example`).

Nothing is simulated: until a valid key is set, AI features stay disabled. Open **Settings** for a connection test.""")


def render_ai_error(exc: Exception, settings: Settings) -> bool:
    """Show an actionable message. Returns True if a retry makes sense."""
    if isinstance(exc, AIConfigError):
        render_config_help(settings)
        return False
    st.error(str(exc) if isinstance(exc, AIError) else "Something went wrong while contacting the AI service.")
    return getattr(exc, "retryable", True)
