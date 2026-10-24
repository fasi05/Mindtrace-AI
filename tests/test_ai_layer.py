import pytest
from pydantic import ValidationError

from models.schemas import DiagnosisAI
from services.ai_client import StructuredAI, extract_json
from services.ai_providers.base import AIConfigError, AIRequestError, AIResponseError
from services.ai_providers.factory import build_provider
from services.config import Settings
from tests.conftest import DIAGNOSIS, FakeProvider, ai_with


def settings(**kw):
    base = dict(provider="anthropic", model="m", api_key=None, database_url="sqlite://", timeout=5, max_tokens=100)
    base.update(kw)
    return Settings(**base)


def test_missing_credentials_raise_config_error_with_instructions():
    with pytest.raises(AIConfigError) as e:
        build_provider(settings())
    assert "ANTHROPIC_API_KEY" in str(e.value) and not e.value.retryable


def test_openai_missing_key():
    with pytest.raises(AIConfigError) as e:
        build_provider(settings(provider="openai"))
    assert "OPENAI_API_KEY" in str(e.value)


def test_unknown_provider():
    with pytest.raises(AIConfigError):
        build_provider(settings(provider="nope", api_key="k"))


def test_builds_real_provider_objects_with_key():
    assert build_provider(settings(api_key="placeholder")).name == "anthropic"
    assert build_provider(settings(provider="openai", api_key="placeholder")).name == "openai"


def test_valid_json_in_code_fence():
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_valid_response_parses():
    assert ai_with(DIAGNOSIS).generate(DiagnosisAI, "s", "u").concept_id == "two_step_equations"


def test_invalid_then_valid_retries_once():
    p = FakeProvider(["not json", DIAGNOSIS])
    assert StructuredAI(p).generate(DiagnosisAI, "s", "u").can_diagnose and p.calls == 2


def test_two_invalid_responses_raise_not_fabricate():
    p = FakeProvider(["nope", {"can_diagnose": True}])
    with pytest.raises(AIResponseError):
        StructuredAI(p).generate(DiagnosisAI, "s", "u")


def test_request_errors_propagate():
    with pytest.raises(AIRequestError):
        ai_with(AIRequestError("rate limit")).generate(DiagnosisAI, "s", "u")


def test_schema_rejects_unknown_concept_and_missing_evidence():
    with pytest.raises(ValidationError):
        DiagnosisAI.model_validate({**DIAGNOSIS, "concept_id": "astrology"})
    with pytest.raises(ValidationError):
        DiagnosisAI.model_validate({**DIAGNOSIS, "evidence": []})


def test_cannot_diagnose_requires_follow_up():
    with pytest.raises(ValidationError):
        DiagnosisAI.model_validate({"can_diagnose": False})
