"""Provider interface and error types. UI code only ever sees AIError subclasses."""
from __future__ import annotations

from abc import ABC, abstractmethod


class AIError(Exception):
    """Base class; `str(error)` is safe to show to learners."""

    retryable: bool = True


class AIConfigError(AIError):
    retryable = False


class AIRequestError(AIError):
    def __init__(self, message: str, retryable: bool = True):
        super().__init__(message)
        self.retryable = retryable


class AIResponseError(AIError):
    """The model answered but the output was empty or failed schema validation."""


class LLMProvider(ABC):
    name: str = "base"
    model: str = ""

    @abstractmethod
    def complete(self, system: str, user: str) -> str:
        """Return the raw text of the model's reply (JSON expected by the caller)."""
