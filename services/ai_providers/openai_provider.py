from __future__ import annotations

from services.ai_providers.base import AIRequestError, AIResponseError, LLMProvider


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, api_key: str, model: str, timeout: int = 60, max_tokens: int = 3000):
        import openai

        self._sdk = openai
        self.model = model
        self.max_tokens = max_tokens
        self._client = openai.OpenAI(api_key=api_key, timeout=timeout, max_retries=0)

    def complete(self, system: str, user: str) -> str:
        sdk = self._sdk
        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                response_format={"type": "json_object"},
                max_completion_tokens=self.max_tokens,
            )
        except sdk.AuthenticationError:
            raise AIRequestError("The OpenAI API key was rejected. Check OPENAI_API_KEY.", retryable=False)
        except sdk.RateLimitError:
            raise AIRequestError("The AI provider rate limit or quota was reached. Wait and retry, or check billing.")
        except sdk.APITimeoutError:
            raise AIRequestError("The AI request timed out. Retry, or raise AI_TIMEOUT_SECONDS.")
        except sdk.APIConnectionError:
            raise AIRequestError("Could not reach the AI provider. Check your internet connection and retry.")
        except sdk.NotFoundError:
            raise AIRequestError(f"Model '{self.model}' was not found. Check AI_MODEL.", retryable=False)
        except sdk.APIStatusError as exc:
            raise AIRequestError(f"The AI provider returned an error (HTTP {exc.status_code}).")
        text = (resp.choices[0].message.content or "") if resp.choices else ""
        if not text.strip():
            raise AIResponseError("The AI provider returned an empty response.")
        return text
