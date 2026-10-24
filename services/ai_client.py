"""Structured-output wrapper: prompt -> raw text -> JSON -> Pydantic model (with one repair retry)."""
from __future__ import annotations

import json
import logging
import re
from typing import Type, TypeVar

from pydantic import BaseModel, ValidationError

from services.ai_providers.base import AIResponseError, LLMProvider

log = logging.getLogger("mindtrace.ai")
T = TypeVar("T", bound=BaseModel)


def extract_json(text: str) -> dict:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.I)
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object found")
    return json.loads(cleaned[start:end + 1])


class StructuredAI:
    def __init__(self, provider: LLMProvider):
        self.provider = provider

    @property
    def provider_name(self) -> str:
        return self.provider.name

    @property
    def model(self) -> str:
        return self.provider.model

    def generate(self, schema: Type[T], system: str, user: str) -> T:
        schema_text = json.dumps(schema.model_json_schema())
        system_full = (f"{system}\n\nRespond with ONE JSON object only (no markdown, no prose) "
                       f"that validates against this JSON Schema:\n{schema_text}")
        prompt, last_error = user, ""
        for attempt in range(2):
            raw = self.provider.complete(system_full, prompt)  # AIRequestError propagates
            try:
                return schema.model_validate(extract_json(raw))
            except (ValueError, ValidationError) as exc:
                last_error = str(exc)[:600]
                # Log the failure category only, never learner content or keys.
                log.warning("AI output failed validation (attempt %d): %s", attempt + 1, type(exc).__name__)
                prompt = (f"{user}\n\nYour previous reply was invalid: {last_error}\n"
                          "Return a corrected JSON object that satisfies the schema exactly.")
        raise AIResponseError("The AI returned an answer that did not pass validation. Please retry.")
