"""
Tests for inference request schema validation and normalization.
"""

import pytest
from pydantic import ValidationError

from llm_inference_service.api.schemas import InferenceRequestSchema
from llm_inference_service.domain.provider_catalog import SupportedModel


@pytest.mark.parametrize(
    "provider, model",
    [
        ("groq", SupportedModel.GPT_OSS_120B),
        ("groq", SupportedModel.GPT_OSS_20B),
        ("gemini", SupportedModel.GEMINI_3_1_FLASH_LITE),
        (" GROQ ", SupportedModel.GPT_OSS_20B),
        (" GeminI", SupportedModel.GEMINI_3_1_FLASH_LITE),
    ],
)
def test_inference_request_accepts_valid_provider_model_combinations(
    provider: str,
    model: SupportedModel,
) -> None:
    schema = InferenceRequestSchema(
        provider=provider,  # type: ignore[arg-type]
        model=model,
        prompt="What is the capital of France?",
    )

    assert schema.provider == provider.strip().lower()
    assert schema.model == model


@pytest.mark.parametrize(
    "provider, model",
    [
        ("groq", SupportedModel.GEMINI_3_1_FLASH_LITE),
        ("gemini", SupportedModel.GPT_OSS_120B),
        ("gemini", SupportedModel.GPT_OSS_20B),
    ],
)
def test_inference_request_rejects_invalid_provider_model_combinations(
    provider: str,
    model: SupportedModel,
) -> None:
    with pytest.raises(ValidationError) as exc_info:
        InferenceRequestSchema(
            provider=provider,  # type: ignore[arg-type]
            model=model,
            prompt="What is the capital of France?",
        )

    errors = exc_info.value.errors()

    assert len(errors) == 1
    assert (
        f"Model '{model}' is not supported by provider '{provider}'."
        in errors[0]["msg"]
    )


def test_inference_request_rejects_unknown_provider() -> None:
    with pytest.raises(ValidationError):
        InferenceRequestSchema(
            provider="unsupported_provider",  # type: ignore[arg-type]
            model=SupportedModel.GPT_OSS_20B,
            prompt="Hello",
        )


def test_inference_request_rejects_system_prompt_above_max_length() -> None:
    with pytest.raises(ValidationError):
        InferenceRequestSchema(
            provider="groq",
            model=SupportedModel.GPT_OSS_20B,
            prompt="Hello",
            system_prompt="x" * 2001,
        )
