"""
Tests for successful retry recovery after a transient provider failure.
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


class EventuallySuccessfulProviderClient:
    def __init__(self) -> None:
        self.attempts = 0

    async def execute(
        self,
        request: InferenceRequest,
    ) -> ModelResponse:
        self.attempts += 1

        if self.attempts == 1:
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


@pytest.mark.anyio
async def test_retry_succeeds_after_transient_failure() -> None:
    client = EventuallySuccessfulProviderClient()

    registry = ProviderRegistry(
        providers={"groq": client},
    )

    policy = ProviderPolicy(
        max_concurrent_requests=1,
        timeout_seconds=15.0,
        max_inference_retries=1,
        retry_base_delay_seconds=0.01,
        retry_max_exponential_delay_seconds=0.01,
        retry_max_jitter_seconds=0.0,
        model_fallbacks={},
        provider_fallbacks=[],
    )

    service = InferenceService(
        registry=registry,
        semaphores={"groq": asyncio.Semaphore(1)},
        provider_policies={"groq": policy},
    )

    request = InferenceRequest(
        provider="groq",
        model="openai/gpt-oss-120b",
        prompt="Test retry recovery",
        temperature=0.7,
        max_tokens=500,
    )

    response = await service.execute(request)

    assert client.attempts == 2
    assert response.content == "ok"
    assert response.provider == "groq"
    assert response.model == request.model
    assert response.request_id == request.request_id
