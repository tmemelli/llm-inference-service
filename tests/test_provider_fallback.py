"""
Tests for provider fallback behavior between inference providers.
"""

import asyncio

import pytest

from llm_inference_service.core.provider_policy import (
    ProviderFallback,
    ProviderPolicy,
)
from llm_inference_service.domain.exceptions import (
    ProviderConnectionError,
    ProviderRequestRejectedError,
)
from llm_inference_service.domain.models import InferenceRequest, ModelResponse
from llm_inference_service.domain.provider_catalog import SupportedModel
from llm_inference_service.services.inference_service import InferenceService
from llm_inference_service.services.provider_registry import ProviderRegistry


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class RetryableFailureProviderClient:
    def __init__(self) -> None:
        self.attempts = 0
        self.models_called: list[str] = []

    async def execute(
        self,
        request: InferenceRequest,
    ) -> ModelResponse:
        self.attempts += 1
        self.models_called.append(request.model)

        raise ProviderConnectionError(
            provider=request.provider,
            error_type="APIConnectionError",
            message="Temporary connection failure.",
        )


class SuccessfulProviderClient:
    def __init__(self) -> None:
        self.attempts = 0
        self.models_called: list[str] = []

    async def execute(
        self,
        request: InferenceRequest,
    ) -> ModelResponse:
        self.attempts += 1
        self.models_called.append(request.model)

        return ModelResponse(
            provider=request.provider,
            model=request.model,
            content="ok",
            prompt_tokens=1,
            completion_tokens=1,
            latency_ms=10.0,
            request_id=request.request_id,
        )


class NonRetryableFailureProviderClient:
    def __init__(self) -> None:
        self.attempts = 0
        self.models_called: list[str] = []

    async def execute(
        self,
        request: InferenceRequest,
    ) -> ModelResponse:
        self.attempts += 1
        self.models_called.append(request.model)

        raise ProviderRequestRejectedError(
            provider=request.provider,
            error_type="BadRequestError",
            message="The upstream provider rejected the request.",
        )


def _create_policy(
    provider_fallbacks: list[ProviderFallback],
) -> ProviderPolicy:
    return ProviderPolicy(
        max_concurrent_requests=1,
        timeout_seconds=15.0,
        max_inference_retries=0,
        retry_base_delay_seconds=0.01,
        retry_max_exponential_delay_seconds=0.01,
        retry_max_jitter_seconds=0.0,
        model_fallbacks={},
        provider_fallbacks=provider_fallbacks,
    )


def _gemini_fallback() -> ProviderFallback:
    return ProviderFallback(
        target_provider="gemini",
        target_model=SupportedModel.GEMINI_3_1_FLASH_LITE,
    )


def _groq_fallback() -> ProviderFallback:
    return ProviderFallback(
        target_provider="groq",
        target_model=SupportedModel("openai/gpt-oss-120b"),
    )


@pytest.mark.anyio
async def test_provider_fallback_succeeds() -> None:
    groq_client = RetryableFailureProviderClient()
    gemini_client = SuccessfulProviderClient()

    registry = ProviderRegistry(
        providers={
            "groq": groq_client,
            "gemini": gemini_client,
        },
    )

    service = InferenceService(
        registry=registry,
        semaphores={
            "groq": asyncio.Semaphore(1),
            "gemini": asyncio.Semaphore(1),
        },
        provider_policies={
            "groq": _create_policy([_gemini_fallback()]),
            "gemini": _create_policy([]),
        },
    )

    request = InferenceRequest(
        provider="groq",
        model="openai/gpt-oss-20b",
        prompt="Test provider fallback success",
        temperature=0.7,
        max_tokens=500,
    )

    response = await service.execute(request)

    assert groq_client.attempts == 1
    assert gemini_client.attempts == 1
    assert gemini_client.models_called == ["gemini-3.1-flash-lite"]

    assert response.provider == "gemini"
    assert response.model == "gemini-3.1-flash-lite"
    assert response.content == "ok"
    assert response.request_id == request.request_id

    assert request.provider == "groq"
    assert request.model == "openai/gpt-oss-20b"


@pytest.mark.anyio
async def test_provider_fallback_raises_when_all_providers_fail() -> None:
    groq_client = RetryableFailureProviderClient()
    gemini_client = RetryableFailureProviderClient()

    registry = ProviderRegistry(
        providers={
            "groq": groq_client,
            "gemini": gemini_client,
        },
    )

    service = InferenceService(
        registry=registry,
        semaphores={
            "groq": asyncio.Semaphore(1),
            "gemini": asyncio.Semaphore(1),
        },
        provider_policies={
            "groq": _create_policy([_gemini_fallback()]),
            "gemini": _create_policy([]),
        },
    )

    request = InferenceRequest(
        provider="groq",
        model="openai/gpt-oss-20b",
        prompt="Test provider fallback failure",
        temperature=0.7,
        max_tokens=500,
    )

    with pytest.raises(ProviderConnectionError) as exc_info:
        await service.execute(request)

    assert groq_client.attempts == 1
    assert gemini_client.attempts == 1
    assert exc_info.value.provider == "gemini"
    assert exc_info.value.error_type == "APIConnectionError"
    assert exc_info.value.message == "Temporary connection failure."


@pytest.mark.anyio
async def test_provider_fallback_is_not_used_when_not_configured() -> None:
    groq_client = RetryableFailureProviderClient()
    gemini_client = SuccessfulProviderClient()

    registry = ProviderRegistry(
        providers={
            "groq": groq_client,
            "gemini": gemini_client,
        },
    )

    service = InferenceService(
        registry=registry,
        semaphores={
            "groq": asyncio.Semaphore(1),
            "gemini": asyncio.Semaphore(1),
        },
        provider_policies={
            "groq": _create_policy([]),
            "gemini": _create_policy([]),
        },
    )

    request = InferenceRequest(
        provider="groq",
        model="openai/gpt-oss-20b",
        prompt="Test provider fallback not configured",
        temperature=0.7,
        max_tokens=500,
    )

    with pytest.raises(ProviderConnectionError) as exc_info:
        await service.execute(request)

    assert groq_client.attempts == 1
    assert gemini_client.attempts == 0

    assert exc_info.value.provider == "groq"
    assert exc_info.value.error_type == "APIConnectionError"
    assert exc_info.value.message == "Temporary connection failure."


@pytest.mark.anyio
async def test_provider_fallback_is_used_for_non_retryable_provider_error() -> None:
    groq_client = NonRetryableFailureProviderClient()
    gemini_client = SuccessfulProviderClient()

    registry = ProviderRegistry(
        providers={
            "groq": groq_client,
            "gemini": gemini_client,
        },
    )

    service = InferenceService(
        registry=registry,
        semaphores={
            "groq": asyncio.Semaphore(1),
            "gemini": asyncio.Semaphore(1),
        },
        provider_policies={
            "groq": _create_policy([_gemini_fallback()]),
            "gemini": _create_policy([]),
        },
    )

    request = InferenceRequest(
        provider="groq",
        model="openai/gpt-oss-20b",
        prompt="Test non-retryable provider failure",
        temperature=0.7,
        max_tokens=500,
    )

    response = await service.execute(request)

    assert groq_client.attempts == 1
    assert gemini_client.attempts == 1

    assert response.provider == "gemini"
    assert response.model == "gemini-3.1-flash-lite"
    assert response.content == "ok"
    assert response.request_id == request.request_id


@pytest.mark.anyio
async def test_provider_fallback_does_not_loop_between_providers() -> None:
    groq_client = RetryableFailureProviderClient()
    gemini_client = RetryableFailureProviderClient()

    registry = ProviderRegistry(
        providers={
            "groq": groq_client,
            "gemini": gemini_client,
        },
    )

    service = InferenceService(
        registry=registry,
        semaphores={
            "groq": asyncio.Semaphore(1),
            "gemini": asyncio.Semaphore(1),
        },
        provider_policies={
            "groq": _create_policy([_gemini_fallback()]),
            "gemini": _create_policy([_groq_fallback()]),
        },
    )

    request = InferenceRequest(
        provider="groq",
        model="openai/gpt-oss-20b",
        prompt="Test provider fallback cycle protection",
        temperature=0.7,
        max_tokens=500,
    )

    with pytest.raises(ProviderConnectionError) as exc_info:
        await service.execute(request)

    assert groq_client.attempts == 1
    assert gemini_client.attempts == 1

    assert groq_client.models_called == ["openai/gpt-oss-20b"]
    assert gemini_client.models_called == ["gemini-3.1-flash-lite"]

    assert exc_info.value.provider == "gemini"


@pytest.mark.anyio
async def test_provider_fallback_does_not_loop_when_starting_with_gemini() -> None:
    groq_client = RetryableFailureProviderClient()
    gemini_client = RetryableFailureProviderClient()

    registry = ProviderRegistry(
        providers={
            "groq": groq_client,
            "gemini": gemini_client,
        },
    )

    service = InferenceService(
        registry=registry,
        semaphores={
            "groq": asyncio.Semaphore(1),
            "gemini": asyncio.Semaphore(1),
        },
        provider_policies={
            "groq": _create_policy([_gemini_fallback()]),
            "gemini": _create_policy([_groq_fallback()]),
        },
    )

    request = InferenceRequest(
        provider="gemini",
        model="gemini-3.1-flash-lite",
        prompt="Test provider fallback cycle protection from Gemini",
        temperature=0.7,
        max_tokens=500,
    )

    with pytest.raises(ProviderConnectionError) as exc_info:
        await service.execute(request)

    assert gemini_client.attempts == 1
    assert groq_client.attempts == 1

    assert gemini_client.models_called == ["gemini-3.1-flash-lite"]
    assert groq_client.models_called == ["openai/gpt-oss-120b"]

    assert exc_info.value.provider == "groq"
