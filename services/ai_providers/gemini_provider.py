from __future__ import annotations

from services.ai_providers.base import AIRequestError, AIResponseError, LLMProvider


class GeminiProvider(LLMProvider):
    """Google Gemini via the official `google-genai` SDK (GEMINI_API_KEY or GOOGLE_API_KEY)."""
    name = "gemini"

    def __init__(self, api_key: str, model: str, timeout: int = 60, max_tokens: int = 3000):
        from google import genai
        from google.genai import errors, types

        self._types, self._errors = types, errors
        self.model, self.max_tokens = model, max_tokens
        self._client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=int(timeout * 1000)))

    def complete(self, system: str, user: str) -> str:
        types, errors = self._types, self._errors
        try:
            resp = self._client.models.generate_content(
                model=self.model, contents=user,
                config=types.GenerateContentConfig(system_instruction=system, response_mime_type="application/json",
                                                   max_output_tokens=self.max_tokens))
        except errors.APIError as exc:
            code = getattr(exc, "code", None)
            if code in (401, 403) or (code == 400 and "API key" in str(exc)):
                raise AIRequestError("The Gemini API key was rejected. Check GEMINI_API_KEY.", retryable=False)
            if code == 404:
                raise AIRequestError(f"Model '{self.model}' was not found. Check AI_MODEL.", retryable=False)
            if code == 429:
                raise AIRequestError("The Gemini rate limit or quota was reached. Wait and retry, or check your quota.")
            if code in (408, 504):
                raise AIRequestError("The AI request timed out. Retry, or raise AI_TIMEOUT_SECONDS.")
            raise AIRequestError(f"The Gemini API returned an error (HTTP {code}).")
        except Exception as exc:  # network / timeout errors surface as httpx exceptions
            name = type(exc).__name__.lower()
            if "timeout" in name:
                raise AIRequestError("The AI request timed out. Retry, or raise AI_TIMEOUT_SECONDS.")
            raise AIRequestError("Could not reach the Gemini API. Check your internet connection and retry.")
        try:
            text = resp.text or ""
        except Exception:  # blocked / empty candidates
            text = ""
        if not text.strip():
            raise AIResponseError("Gemini returned an empty or blocked response. Please retry.")
        return text
