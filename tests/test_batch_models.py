import asyncio

import pytest

from llm_inference_service.api.schemas import BatchInferenceRequestSchema
from llm_inference_service.core.provider_policy import (
    ProviderFallback,
    ProviderPolicy,
)
from llm_inference_service.domain.exceptions import (
    BatchSizeExceededError,
    ProviderRequestRejectedError,
)
from llm_inference_service.domain.models import (
    BatchInferenceResult,
    BatchItemResult,
    InferenceRequest,
    ModelResponse,
)
from llm_inference_service.services.batch_inference_service import BatchInferenceService
from llm_inference_service.services.inference_service import InferenceService
from llm_inference_service.services.provider_registry import ProviderRegistry


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
            content="ok async",
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


@pytest.mark.asyncio
async def test_batch_inference_executes_multiple_requests() -> None:
    groq_client = SuccessfulProviderClient()
    gemini_client = SuccessfulProviderClient()

    registry = ProviderRegistry(
        providers={
            "groq": groq_client,
            "gemini": gemini_client,
        },
    )

    inference_service = InferenceService(
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

    service = BatchInferenceService(
        inference_service=inference_service,
        max_batch_size=5,
    )

    json_input = {
        "requests": [
            {
                "provider": "groq",
                "model": "openai/gpt-oss-20b",
                "prompt": "Qual o tamanho da terra?",
                "temperature": 0.5,
                "max_tokens": 100,
            },
            {
                "provider": "gemini",
                "model": "gemini-3.1-flash-lite",
                "prompt": "Qual o tamanho da Lua?",
                "temperature": 0.7,
                "max_tokens": 100,
            },
            {
                "provider": "groq",
                "model": "openai/gpt-oss-120b",
                "prompt": "Qual o tamanho de Marte?",
                "temperature": 0.9,
                "max_tokens": 100,
            },
        ]
    }

    validated_payload = BatchInferenceRequestSchema.model_validate(json_input)

    requests = [
        InferenceRequest(
            provider=item.provider,
            model=item.model,
            prompt=item.prompt,
            system_prompt=item.system_prompt,
            temperature=item.temperature,
            max_tokens=item.max_tokens,
        )
        for item in validated_payload.requests
    ]

    result = await service.execute(requests)

    assert result.total == 3
    assert len(result.results) == 3

    assert result.results[0].request_id == requests[0].request_id
    assert result.results[0].success is True
    assert result.results[0].response is not None
    assert result.results[0].error_type is None
    assert result.results[0].error_message is None

    assert result.results[1].request_id == requests[1].request_id
    assert result.results[1].success is True
    assert result.results[1].response is not None
    assert result.results[1].error_type is None
    assert result.results[1].error_message is None

    assert result.results[2].request_id == requests[2].request_id
    assert result.results[2].success is True
    assert result.results[2].response is not None
    assert result.results[2].error_type is None
    assert result.results[2].error_message is None


@pytest.mark.asyncio
async def test_batch_inference_isolates_provider_failure() -> None:
    groq_client = SuccessfulProviderClient()
    gemini_client = NonRetryableFailureProviderClient()

    registry = ProviderRegistry(
        providers={
            "groq": groq_client,
            "gemini": gemini_client,
        },
    )

    inference_service = InferenceService(
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

    service = BatchInferenceService(
        inference_service=inference_service,
        max_batch_size=5,
    )

    json_input = {
        "requests": [
            {
                "provider": "groq",
                "model": "openai/gpt-oss-20b",
                "prompt": "Qual o tamanho da terra?",
                "temperature": 0.5,
                "max_tokens": 100,
            },
            {
                "provider": "gemini",
                "model": "gemini-3.1-flash-lite",
                "prompt": "Qual o tamanho da Lua?",
                "temperature": 0.7,
                "max_tokens": 100,
            },
            {
                "provider": "groq",
                "model": "openai/gpt-oss-120b",
                "prompt": "Qual o tamanho de Marte?",
                "temperature": 0.9,
                "max_tokens": 100,
            },
        ]
    }

    validated_payload = BatchInferenceRequestSchema.model_validate(json_input)

    requests = [
        InferenceRequest(
            provider=item.provider,
            model=item.model,
            prompt=item.prompt,
            system_prompt=item.system_prompt,
            temperature=item.temperature,
            max_tokens=item.max_tokens,
        )
        for item in validated_payload.requests
    ]

    result = await service.execute(requests)

    assert result.total == 3
    assert len(result.results) == 3

    assert result.results[0].request_id == requests[0].request_id
    assert result.results[0].success is True
    assert result.results[0].response is not None
    assert result.results[0].error_type is None
    assert result.results[0].error_message is None

    assert result.results[1].request_id == requests[1].request_id
    assert result.results[1].success is False
    assert result.results[1].response is None
    assert result.results[1].error_type == "ProviderRequestRejectedError"
    assert (
        result.results[1].error_message
        == "[GEMINI] BadRequestError: The upstream provider rejected the request."
    )

    assert result.results[2].request_id == requests[2].request_id
    assert result.results[2].success is True
    assert result.results[2].response is not None
    assert result.results[2].error_type is None
    assert result.results[2].error_message is None


@pytest.mark.asyncio
async def test_batch_inference_rejects_batch_above_configured_limit() -> None:
    groq_client = SuccessfulProviderClient()
    gemini_client = SuccessfulProviderClient()

    registry = ProviderRegistry(
        providers={
            "groq": groq_client,
            "gemini": gemini_client,
        },
    )

    inference_service = InferenceService(
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

    service = BatchInferenceService(
        inference_service=inference_service,
        max_batch_size=2,
    )

    json_input = {
        "requests": [
            {
                "provider": "groq",
                "model": "openai/gpt-oss-20b",
                "prompt": "Qual o tamanho da terra?",
                "temperature": 0.5,
                "max_tokens": 100,
            },
            {
                "provider": "gemini",
                "model": "gemini-3.1-flash-lite",
                "prompt": "Qual o tamanho da Lua?",
                "temperature": 0.7,
                "max_tokens": 100,
            },
            {
                "provider": "groq",
                "model": "openai/gpt-oss-120b",
                "prompt": "Qual o tamanho de Marte?",
                "temperature": 0.9,
                "max_tokens": 100,
            },
        ]
    }

    validated_payload = BatchInferenceRequestSchema.model_validate(json_input)

    requests = [
        InferenceRequest(
            provider=item.provider,
            model=item.model,
            prompt=item.prompt,
            system_prompt=item.system_prompt,
            temperature=item.temperature,
            max_tokens=item.max_tokens,
        )
        for item in validated_payload.requests
    ]

    with pytest.raises(BatchSizeExceededError) as exc_info:
        await service.execute(requests)

    assert "Batch size 3 exceeds configured limit of 2." in str(exc_info.value)


def _dummy_response() -> ModelResponse:
    return ModelResponse(
        provider="groq",
        model="openai/gpt-oss-20b",
        content="ok",
        prompt_tokens=1,
        completion_tokens=1,
        latency_ms=10.0,
        request_id="req-123",
    )


@pytest.mark.parametrize(
    "success, response, error_type, error_message",
    [
        # 1. success=True but no response (inconsistent)
        (True, None, None, None),
        # 2. success=True but with an error populated (inconsistent)
        (
            True,
            _dummy_response(),
            "ProviderRequestRejectedError",
            "The upstream provider rejected the request.",
        ),
        # 3. success=False but response is populated (inconsistent)
        (
            False,
            _dummy_response(),
            "ProviderRequestRejectedError",
            "The upstream provider rejected the request.",
        ),
        # 4. success=False without error_type (inconsistent)
        (False, None, None, "The upstream provider rejected the request."),
        # 5. success=False without error_message (inconsistent)
        (False, None, "ProviderRequestRejectedError", None),
    ],
)
def test_batch_item_result_rejects_inconsistent_state(
    success: bool,
    response: ModelResponse | None,
    error_type: str | None,
    error_message: str | None,
) -> None:
    """
    Proves that BatchItemResult blocks the creation of logically invalid
    or contradictory states.
    """

    with pytest.raises(ValueError) as exc_info:
        BatchItemResult(
            request_id="req-123",
            success=success,
            response=response,
            error_type=error_type,
            error_message=error_message,
        )

    assert str(exc_info.value).strip() != ""


def _dummy_success_item() -> BatchItemResult:
    """Generates a valid successful batch item result for testing purposes."""
    return BatchItemResult(
        request_id="req-1",
        success=True,
        response=ModelResponse(
            provider="groq",
            model="openai/gpt-oss-20b",
            content="ok",
            prompt_tokens=1,
            completion_tokens=1,
            latency_ms=10.0,
            request_id="req-1",
        ),
        error_type=None,
        error_message=None,
    )


def _dummy_failed_item() -> BatchItemResult:
    """Generates a valid successful batch item result for testing purposes."""
    return BatchItemResult(
        request_id="req-2",
        success=False,
        response=None,
        error_type="ProviderRequestRejectedError",
        error_message="The upstream provider rejected the request.",
    )


@pytest.mark.parametrize(
    "results, total, success_count, failure_count, elapsed_ms, expected_exception",
    [
        # 1. Invalid total (1 real item, but total reports 99)
        ((_dummy_success_item(),), 99, 1, 0, 50.0, ValueError),
        # 2. Invalid success_count (1 real success, but success_count reports 2)
        ((_dummy_success_item(), _dummy_failed_item()), 2, 2, 1, 50.0, ValueError),
        # 3. Invalid failure_count (0 real failures, but failure_count reports 1)
        ((_dummy_success_item(),), 1, 1, 1, 50.0, ValueError),
        # 4. Invalid elapsed_ms type (boolean is a subclass of int in Python, must be blocked)
        ((_dummy_success_item(),), 1, 1, 0, True, TypeError),
        # 5. Invalid elapsed_ms type (string instead of int/float)
        ((_dummy_success_item(),), 1, 1, 0, "50.0", TypeError),
        # 6. Invalid negative elapsed_ms value
        ((_dummy_success_item(),), 1, 1, 0, -10.5, ValueError),
    ],
)
def test_batch_inference_result_validates_metrics_and_negative_elapsed_ms(
    results: tuple[BatchItemResult, ...],
    total: int,
    success_count: int,
    failure_count: int,
    elapsed_ms: float,
    expected_exception: type[Exception],
) -> None:
    """
    Proves that BatchInferenceResult blocks the creation of logically invalid
    or contradictory states.
    """

    with pytest.raises(expected_exception) as exc_info:
        BatchInferenceResult(
            results=results,
            total=total,
            success_count=success_count,
            failure_count=failure_count,
            elapsed_ms=elapsed_ms,
        )

    assert str(exc_info.value).strip() != ""
