"""
Tests for ordered model fallback behavior within a provider.
"""

import asyncio

import pytest

from llm_inference_service.core.provider_policy import ProviderPolicy
from llm_inference_service.domain.exceptions import ProviderConnectionError
from llm_inference_service.domain.models import InferenceRequest, ModelResponse
from llm_inference_service.services.inference_service import InferenceService
from llm_inference_service.services.provider_registry import ProviderRegistry


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class AlwaysFailingProviderClient:
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


class EventuallySuccessfulProviderClient:
    def __init__(self) -> None:
        self.attempts = 0
        self.models_called: list[str] = []

    async def execute(
        self,
        request: InferenceRequest,
    ) -> ModelResponse:
        self.attempts += 1
        self.models_called.append(request.model)

        if self.attempts < 3:
            raise ProviderConnectionError(
                provider=request.provider,
                error_type="APIConnectionError",
                message="Temporary connection failure.",
            )

        return ModelResponse(
            provider=request.provider,
            model=request.model,
            content="ok",
            prompt_tokens=1,
            completion_tokens=1,
            latency_ms=10.0,
            request_id=request.request_id,
        )


def _create_policy(
    model_fallbacks: dict[str, list[str]],
) -> ProviderPolicy:
    return ProviderPolicy(
        max_concurrent_requests=5,
        timeout_seconds=15.0,
        max_inference_retries=0,
        retry_base_delay_seconds=0.01,
        retry_max_exponential_delay_seconds=0.01,
        retry_max_jitter_seconds=0.0,
        model_fallbacks=model_fallbacks,
        provider_fallbacks=[],
    )


@pytest.mark.anyio
async def test_model_fallback_raises_when_all_models_fail() -> None:
    client = AlwaysFailingProviderClient()

    registry = ProviderRegistry(
        providers={"groq": client},
    )

    policy = _create_policy(
        {
            "model-a": ["model-b", "model-c"],
        }
    )

    service = InferenceService(
        registry=registry,
        semaphores={"groq": asyncio.Semaphore(5)},
        provider_policies={"groq": policy},
    )

    request = InferenceRequest(
        provider="groq",
        model="model-a",
        prompt="Test model fallback failure",
        temperature=0.7,
        max_tokens=500,
    )

    with pytest.raises(ProviderConnectionError) as exc_info:
        await service.execute(request)

    assert client.attempts == 3
    assert client.models_called == [
        "model-a",
        "model-b",
        "model-c",
    ]

    assert exc_info.value.provider == "groq"
    assert exc_info.value.error_type == "APIConnectionError"
    assert exc_info.value.message == "Temporary connection failure."


@pytest.mark.anyio
async def test_model_fallback_succeeds() -> None:
    client = EventuallySuccessfulProviderClient()

    registry = ProviderRegistry(
        providers={"groq": client},
    )

    policy = _create_policy(
        {
            "model-a": ["model-b", "model-c", "model-d"],
        }
    )

    service = InferenceService(
        registry=registry,
        semaphores={"groq": asyncio.Semaphore(5)},
        provider_policies={"groq": policy},
    )

    request = InferenceRequest(
        provider="groq",
        model="model-a",
        prompt="Test model fallback success",
        temperature=0.7,
        max_tokens=500,
    )

    response = await service.execute(request)

    assert client.attempts == 3
    assert client.models_called == [
        "model-a",
        "model-b",
        "model-c",
    ]

    assert response.content == "ok"
    assert response.model == "model-c"
    assert response.request_id == request.request_id
    assert request.model == "model-a"
