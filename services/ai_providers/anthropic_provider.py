from __future__ import annotations

from services.ai_providers.base import AIRequestError, AIResponseError, LLMProvider


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, api_key: str, model: str, timeout: int = 60, max_tokens: int = 3000):
        import anthropic

        self._sdk = anthropic
        self.model = model
        self.max_tokens = max_tokens
        self._client = anthropic.Anthropic(api_key=api_key, timeout=timeout, max_retries=0)

    def complete(self, system: str, user: str) -> str:
        sdk = self._sdk
        try:
            resp = self._client.messages.create(
                model=self.model, max_tokens=self.max_tokens, system=system,
                messages=[{"role": "user", "content": user}],
            )
        except sdk.AuthenticationError:
            raise AIRequestError("The Anthropic API key was rejected. Check ANTHROPIC_API_KEY.", retryable=False)
        except sdk.RateLimitError:
            raise AIRequestError("The AI provider rate limit was reached. Wait a moment and retry.")
        except sdk.APITimeoutError:
            raise AIRequestError("The AI request timed out. Retry, or raise AI_TIMEOUT_SECONDS.")
        except sdk.APIConnectionError:
            raise AIRequestError("Could not reach the AI provider. Check your internet connection and retry.")
        except sdk.NotFoundError:
            raise AIRequestError(f"Model '{self.model}' was not found. Check AI_MODEL.", retryable=False)
        except sdk.APIStatusError as exc:
            raise AIRequestError(f"The AI provider returned an error (HTTP {exc.status_code}).")
        text = "".join(getattr(b, "text", "") for b in resp.content if getattr(b, "type", "") == "text")
        if not text.strip():
            raise AIResponseError("The AI provider returned an empty response.")
        return text
