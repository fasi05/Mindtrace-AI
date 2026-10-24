"""Provider registry. Add a new provider by writing a class and registering it here."""
from __future__ import annotations

from services.ai_providers.base import AIConfigError, LLMProvider
from services.config import KEY_ENV, SUPPORTED_PROVIDERS, Settings


def build_provider(settings: Settings) -> LLMProvider:
    if settings.provider not in SUPPORTED_PROVIDERS:
        raise AIConfigError(
            f"Unknown AI_PROVIDER '{settings.provider}'. Supported: {', '.join(SUPPORTED_PROVIDERS)}.")
    if not settings.api_key:
        raise AIConfigError(
            f"AI is not configured: {KEY_ENV[settings.provider]} is missing. "
            "Add it to your .env file locally or to Streamlit secrets in the cloud (see the Settings page).")
    if not settings.model:
        raise AIConfigError("AI_MODEL is empty. Set AI_MODEL or use the provider default.")
    if settings.provider == "anthropic":
        from services.ai_providers.anthropic_provider import AnthropicProvider
        return AnthropicProvider(settings.api_key, settings.model, settings.timeout, settings.max_tokens)
    if settings.provider == "gemini":
        from services.ai_providers.gemini_provider import GeminiProvider
        return GeminiProvider(settings.api_key, settings.model, settings.timeout, settings.max_tokens)
    from services.ai_providers.openai_provider import OpenAIProvider
    return OpenAIProvider(settings.api_key, settings.model, settings.timeout, settings.max_tokens)
