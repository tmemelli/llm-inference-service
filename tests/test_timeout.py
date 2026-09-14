"""
Tests for inference timeout handling.
"""

import asyncio

import pytest

from llm_inference_service.core.provider_policy import ProviderPolicy
from llm_inference_service.domain.exceptions import ProviderTimeoutError
from llm_inference_service.domain.models import InferenceRequest, ModelResponse
from llm_inference_service.services.inference_service import InferenceService
from llm_inference_service.services.provider_registry import ProviderRegistry


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class HangingProviderClient:
    async def execute(
        self,
        request: InferenceRequest,
    ) -> ModelResponse:
        await asyncio.Event().wait()

        raise AssertionError("Provider execution should have timed out.")


@pytest.mark.anyio
async def test_inference_timeout_raises_provider_timeout_error() -> None:
    client = HangingProviderClient()

    registry = ProviderRegistry(
        providers={"groq": client},
    )

    policy = ProviderPolicy(
        max_concurrent_requests=1,
        timeout_seconds=0.01,
        max_inference_retries=0,
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
        prompt="Test inference timeout",
        temperature=0.7,
        max_tokens=500,
    )

    with pytest.raises(ProviderTimeoutError) as exc_info:
        await service.execute(request)

    assert exc_info.value.provider == "groq"
    assert exc_info.value.error_type == "TimeoutError"
    assert exc_info.value.message == (
        "The inference request exceeded the configured timeout " "of 0.01 seconds."
    )
