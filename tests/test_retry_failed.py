"""
Tests for retry exhaustion after transient provider failures.
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

    async def execute(
        self,
        request: InferenceRequest,
    ) -> ModelResponse:
        self.attempts += 1

        raise ProviderConnectionError(
            provider=request.provider,
            error_type="APIConnectionError",
            message="Temporary connection failure.",
        )


@pytest.mark.anyio
async def test_retry_raises_after_max_retries_exhausted() -> None:
    client = AlwaysFailingProviderClient()

    registry = ProviderRegistry(
        providers={"groq": client},
    )

    policy = ProviderPolicy(
        max_concurrent_requests=1,
        timeout_seconds=15.0,
        max_inference_retries=2,
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
        model="openai/gpt-oss-20b",
        prompt="Test retry exhaustion",
        temperature=0.7,
        max_tokens=500,
    )

    with pytest.raises(ProviderConnectionError) as exc_info:
        await service.execute(request)

    assert client.attempts == 3

    assert exc_info.value.provider == "groq"
    assert exc_info.value.error_type == "APIConnectionError"
    assert exc_info.value.message == "Temporary connection failure."
