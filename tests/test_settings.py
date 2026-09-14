"""
Tests for application settings and provider policy validation.
"""

import json
from typing import Any

import pytest
from pydantic import ValidationError

from llm_inference_service.core.provider_policy import (
    ProviderFallback,
    ProviderPolicy,
)
from llm_inference_service.core.settings import Settings
from llm_inference_service.domain.provider_catalog import SupportedModel

PolicyConfig = dict[str, Any]
PoliciesConfig = dict[str, PolicyConfig]


@pytest.fixture
def base_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "gsk_dummy_key")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini_dummy_key")


def _valid_provider_policies() -> PoliciesConfig:
    return {
        "groq": {
            "max_concurrent_requests": 5,
            "timeout_seconds": 15.0,
            "max_inference_retries": 1,
            "retry_base_delay_seconds": 0.5,
            "retry_max_exponential_delay_seconds": 2.0,
            "retry_max_jitter_seconds": 0.05,
            "model_fallbacks": {
                "openai/gpt-oss-20b": ["openai/gpt-oss-120b"],
                "openai/gpt-oss-120b": ["openai/gpt-oss-20b"],
            },
            "provider_fallbacks": [
                {
                    "target_provider": "gemini",
                    "target_model": "gemini-3.1-flash-lite",
                }
            ],
        },
        "gemini": {
            "max_concurrent_requests": 2,
            "timeout_seconds": 15.0,
            "max_inference_retries": 0,
            "retry_base_delay_seconds": 0.5,
            "retry_max_exponential_delay_seconds": 2.0,
            "retry_max_jitter_seconds": 0.05,
            "model_fallbacks": {},
            "provider_fallbacks": [],
        },
    }


def _set_provider_policies(
    monkeypatch: pytest.MonkeyPatch,
    policies: PoliciesConfig,
) -> None:
    monkeypatch.setenv(
        "PROVIDER_POLICIES",
        json.dumps(policies),
    )


def test_settings_load_from_environment_success(
    base_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_provider_policies(
        monkeypatch,
        _valid_provider_policies(),
    )

    settings = Settings(_env_file=None)  # pyright: ignore[reportCallIssue]

    assert settings.groq_api_key.get_secret_value() == "gsk_dummy_key"
    assert settings.gemini_api_key.get_secret_value() == "gemini_dummy_key"
    assert set(settings.provider_policies) == {"groq", "gemini"}

    groq_policy = settings.provider_policies["groq"]

    assert isinstance(groq_policy, ProviderPolicy)
    assert groq_policy.max_concurrent_requests == 5
    assert groq_policy.timeout_seconds == 15.0
    assert groq_policy.max_inference_retries == 1
    assert groq_policy.retry_base_delay_seconds == 0.5
    assert groq_policy.retry_max_exponential_delay_seconds == 2.0
    assert groq_policy.retry_max_jitter_seconds == 0.05
    assert groq_policy.model_fallbacks == {
        "openai/gpt-oss-20b": ["openai/gpt-oss-120b"],
        "openai/gpt-oss-120b": ["openai/gpt-oss-20b"],
    }
    assert groq_policy.provider_fallbacks == [
        ProviderFallback(
            target_provider="gemini",
            target_model=SupportedModel.GEMINI_3_1_FLASH_LITE,
        )
    ]

    gemini_policy = settings.provider_policies["gemini"]

    assert isinstance(gemini_policy, ProviderPolicy)
    assert gemini_policy.max_concurrent_requests == 2
    assert gemini_policy.timeout_seconds == 15.0
    assert gemini_policy.max_inference_retries == 0
    assert gemini_policy.retry_base_delay_seconds == 0.5
    assert gemini_policy.retry_max_exponential_delay_seconds == 2.0
    assert gemini_policy.retry_max_jitter_seconds == 0.05
    assert gemini_policy.model_fallbacks == {}
    assert gemini_policy.provider_fallbacks == []


def test_settings_rejects_invalid_provider_policy(
    base_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policies = _valid_provider_policies()
    policies["groq"]["timeout_seconds"] = -1.0

    _set_provider_policies(monkeypatch, policies)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # pyright: ignore[reportCallIssue]


def test_settings_rejects_unsupported_provider(
    base_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policies = _valid_provider_policies()
    policies["fake"] = {
        "max_concurrent_requests": 1,
        "timeout_seconds": 15.0,
        "max_inference_retries": 0,
        "retry_base_delay_seconds": 0.5,
        "retry_max_exponential_delay_seconds": 2.0,
        "retry_max_jitter_seconds": 0.05,
        "model_fallbacks": {},
        "provider_fallbacks": [],
    }

    _set_provider_policies(monkeypatch, policies)

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)  # pyright: ignore[reportCallIssue]

    assert "Unsupported providers defined in policies: fake." in str(exc_info.value)


def test_settings_rejects_missing_provider_policy(
    base_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policies = _valid_provider_policies()
    del policies["gemini"]

    _set_provider_policies(monkeypatch, policies)

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)  # pyright: ignore[reportCallIssue]

    assert "Missing provider policies for: gemini." in str(exc_info.value)


def test_settings_rejects_invalid_source_model(
    base_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policies = _valid_provider_policies()
    policies["groq"]["model_fallbacks"] = {
        "non-existent-model": ["openai/gpt-oss-20b"],
    }

    _set_provider_policies(monkeypatch, policies)

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)  # pyright: ignore[reportCallIssue]

    error = str(exc_info.value)

    assert "Invalid model entry in fallbacks for provider 'groq':" in error
    assert "non-existent-model" in error


def test_settings_rejects_duplicate_model_fallback_targets(
    base_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policies = _valid_provider_policies()
    policies["groq"]["model_fallbacks"] = {
        "openai/gpt-oss-120b": [
            "openai/gpt-oss-20b",
            "openai/gpt-oss-20b",
        ],
    }

    _set_provider_policies(monkeypatch, policies)

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)  # pyright: ignore[reportCallIssue]

    assert (
        "source model 'openai/gpt-oss-120b' contains duplicate "
        "fallback targets." in str(exc_info.value)
    )


def test_settings_rejects_self_referencing_model_fallback(
    base_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policies = _valid_provider_policies()
    policies["groq"]["model_fallbacks"] = {
        "openai/gpt-oss-120b": ["openai/gpt-oss-120b"],
    }

    _set_provider_policies(monkeypatch, policies)

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)  # pyright: ignore[reportCallIssue]

    assert "source model 'openai/gpt-oss-120b' cannot map to itself." in str(
        exc_info.value
    )


def test_settings_rejects_invalid_fallback_model(
    base_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policies = _valid_provider_policies()
    policies["groq"]["model_fallbacks"] = {
        "openai/gpt-oss-120b": ["non-existent-model"],
    }

    _set_provider_policies(monkeypatch, policies)

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)  # pyright: ignore[reportCallIssue]

    error = str(exc_info.value)

    assert "Invalid model entry in fallbacks for provider 'groq':" in error
    assert "non-existent-model" in error


def test_settings_rejects_fallback_model_from_another_provider(
    base_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policies = _valid_provider_policies()
    policies["groq"]["model_fallbacks"] = {
        "openai/gpt-oss-120b": ["gemini-3.1-flash-lite"],
    }

    _set_provider_policies(monkeypatch, policies)

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)  # pyright: ignore[reportCallIssue]

    assert (
        "Fallback target model 'gemini-3.1-flash-lite' is not "
        "supported by provider 'groq'." in str(exc_info.value)
    )


def test_settings_rejects_source_model_from_another_provider(
    base_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policies = _valid_provider_policies()
    policies["groq"]["model_fallbacks"] = {
        "gemini-3.1-flash-lite": ["openai/gpt-oss-20b"],
    }

    _set_provider_policies(monkeypatch, policies)

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)  # pyright: ignore[reportCallIssue]

    assert (
        "Fallback source model 'gemini-3.1-flash-lite' is not "
        "supported by provider 'groq'." in str(exc_info.value)
    )


def test_settings_rejects_provider_policy_with_missing_fields(
    base_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policies = _valid_provider_policies()
    policies["gemini"] = {}

    _set_provider_policies(monkeypatch, policies)

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)  # pyright: ignore[reportCallIssue]

    errors = exc_info.value.errors()

    assert any(
        error["type"] == "missing"
        and "provider_policies" in error["loc"]
        and "gemini" in error["loc"]
        for error in errors
    )


def test_settings_rejects_duplicate_provider_fallback_targets(
    base_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policies = _valid_provider_policies()
    policies["groq"]["provider_fallbacks"] = [
        {
            "target_provider": "gemini",
            "target_model": "gemini-3.1-flash-lite",
        },
        {
            "target_provider": "gemini",
            "target_model": "gemini-3.1-flash-lite",
        },
    ]

    _set_provider_policies(monkeypatch, policies)

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)  # pyright: ignore[reportCallIssue]

    assert "Provider 'groq' contains duplicate provider fallback targets." in str(
        exc_info.value
    )


def test_settings_rejects_unsupported_provider_fallback_target(
    base_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policies = _valid_provider_policies()
    policies["groq"]["provider_fallbacks"] = [
        {
            "target_provider": "openai",
            "target_model": "gemini-3.1-flash-lite",
        }
    ]

    _set_provider_policies(monkeypatch, policies)

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)  # pyright: ignore[reportCallIssue]

    assert "Fallback target provider 'openai' is not supported by the catalog." in str(
        exc_info.value
    )


def test_settings_rejects_self_referencing_provider_fallback(
    base_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policies = _valid_provider_policies()
    policies["groq"]["provider_fallbacks"] = [
        {
            "target_provider": "groq",
            "target_model": "openai/gpt-oss-120b",
        }
    ]

    _set_provider_policies(monkeypatch, policies)

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)  # pyright: ignore[reportCallIssue]

    assert "Provider 'groq' cannot define itself as a provider fallback." in str(
        exc_info.value
    )


def test_settings_rejects_provider_fallback_model_from_wrong_provider(
    base_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policies = _valid_provider_policies()
    policies["groq"]["provider_fallbacks"] = [
        {
            "target_provider": "gemini",
            "target_model": "openai/gpt-oss-120b",
        }
    ]

    _set_provider_policies(monkeypatch, policies)

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)  # pyright: ignore[reportCallIssue]

    assert (
        "Fallback target model 'openai/gpt-oss-120b' is not "
        "supported by provider 'gemini'." in str(exc_info.value)
    )
