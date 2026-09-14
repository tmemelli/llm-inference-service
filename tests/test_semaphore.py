"""
Tests for provider-specific concurrency limits.
"""

import asyncio

import pytest

from llm_inference_service.core.provider_policy import ProviderPolicy
from llm_inference_service.domain.models import InferenceRequest, ModelResponse
from llm_inference_service.services.inference_service import InferenceService
from llm_inference_service.services.provider_registry import ProviderRegistry


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class ConcurrentTrackingProviderClient:
    def __init__(self) -> None:
        self.active_requests = 0
        self.max_active_requests = 0

    async def execute(
        self,
        request: InferenceRequest,
    ) -> ModelResponse:
        self.active_requests += 1
        self.max_active_requests = max(
            self.max_active_requests,
            self.active_requests,
        )

        try:
            await asyncio.sleep(0.05)

            return ModelResponse(
                provider=request.provider,
                model=request.model,
                content="ok",
                prompt_tokens=1,
                completion_tokens=1,
                latency_ms=50.0,
                request_id=request.request_id,
            )
        finally:
            self.active_requests -= 1


@pytest.mark.anyio
async def test_semaphore_limits_concurrent_inferences() -> None:
    client = ConcurrentTrackingProviderClient()

    registry = ProviderRegistry(
        providers={"groq": client},
    )

    policy = ProviderPolicy(
        max_concurrent_requests=2,
        timeout_seconds=1.0,
        max_inference_retries=0,
        retry_base_delay_seconds=0.01,
        retry_max_exponential_delay_seconds=0.01,
        retry_max_jitter_seconds=0.0,
        model_fallbacks={},
        provider_fallbacks=[],
    )

    service = InferenceService(
        registry=registry,
        semaphores={
            "groq": asyncio.Semaphore(2),
        },
        provider_policies={
            "groq": policy,
        },
    )

    requests = [
        InferenceRequest(
            provider="groq",
            model="openai/gpt-oss-20b",
            prompt=f"Prompt {index}",
            temperature=0.7,
            max_tokens=500,
        )
        for index in range(5)
    ]

    await asyncio.gather(*(service.execute(request) for request in requests))

    assert client.max_active_requests == 2
    assert client.active_requests == 0
