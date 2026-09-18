from typing import Any
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from llm_inference_service.api.dependencies import (
    enforce_inference_rate_limit,
    get_batch_inference_service,
)
from llm_inference_service.api.exception_handlers import (
    register_exception_handlers,
)
from llm_inference_service.api.routes import api_router
from llm_inference_service.domain.exceptions import (
    BatchSizeExceededError,
)
from llm_inference_service.domain.models import (
    BatchInferenceResult,
    BatchItemResult,
    InferenceRequest,
    ModelResponse,
)
from llm_inference_service.services.batch_inference_service import (
    BatchInferenceService,
)


def _create_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(api_router)
    register_exception_handlers(app)

    return app


def test_batch_endpoint_returns_successful_response() -> None:
    app = _create_test_app()

    service = MagicMock(spec=BatchInferenceService)

    async def execute(
        requests: list[InferenceRequest],
    ) -> BatchInferenceResult:
        request = requests[0]

        model_response = ModelResponse(
            provider=request.provider,
            model=request.model,
            content="Resposta de teste",
            prompt_tokens=10,
            completion_tokens=5,
            latency_ms=20.0,
            request_id=request.request_id,
        )

        item_result = BatchItemResult(
            request_id=request.request_id,
            success=True,
            response=model_response,
            error_type=None,
            error_message=None,
        )

        return BatchInferenceResult(
            results=(item_result,),
            total=1,
            success_count=1,
            failure_count=0,
            elapsed_ms=25.0,
        )

    service.execute = AsyncMock(side_effect=execute)

    app.dependency_overrides[get_batch_inference_service] = lambda: service
    app.dependency_overrides[enforce_inference_rate_limit] = lambda: None

    client = TestClient(app)

    payload = {
        "requests": [
            {
                "provider": "groq",
                "model": "openai/gpt-oss-20b",
                "prompt": "Qual o tamanho da terra?",
                "temperature": 0.5,
                "max_tokens": 100,
            }
        ]
    }

    response = client.post(
        "/v1/inference/batch",
        json=payload,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total"] == 1
    assert data["success_count"] == 1
    assert data["failure_count"] == 0
    assert data["elapsed_ms"] == 25.0

    assert len(data["results"]) == 1

    item = data["results"][0]

    assert item["success"] is True
    assert item["response"]["provider"] == "groq"
    assert item["response"]["model"] == "openai/gpt-oss-20b"
    assert item["response"]["content"] == "Resposta de teste"
    assert item["error_type"] is None
    assert item["error_message"] is None

    assert item["request_id"] == item["response"]["request_id"]

    service.execute.assert_awaited_once()


def test_batch_endpoint_rejects_invalid_payload() -> None:
    app = _create_test_app()

    service = MagicMock(spec=BatchInferenceService)
    service.execute = AsyncMock()

    app.dependency_overrides[get_batch_inference_service] = lambda: service
    app.dependency_overrides[enforce_inference_rate_limit] = lambda: None

    client = TestClient(app)

    payload: dict[str, list[Any]] = {"requests": []}

    response = client.post(
        "/v1/inference/batch",
        json=payload,
    )

    assert response.status_code == 422

    detail = response.json()["detail"][0]
    assert detail["type"] == "too_short"
    assert detail["loc"] == ["body", "requests"]
    assert detail["ctx"]["min_length"] == 1

    service.execute.assert_not_awaited()


def test_batch_endpoint_returns_400_when_configured_limit_is_exceeded() -> None:
    app = _create_test_app()

    service = MagicMock(spec=BatchInferenceService)

    service.execute = AsyncMock(
        side_effect=BatchSizeExceededError(
            "Batch size 3 exceeds configured limit of 2."
        )
    )

    app.dependency_overrides[get_batch_inference_service] = lambda: service
    app.dependency_overrides[enforce_inference_rate_limit] = lambda: None

    client = TestClient(app)

    payload = {
        "requests": [
            {
                "provider": "groq",
                "model": "openai/gpt-oss-20b",
                "prompt": "Pergunta 1",
                "temperature": 0.5,
                "max_tokens": 100,
            },
            {
                "provider": "gemini",
                "model": "gemini-3.1-flash-lite",
                "prompt": "Pergunta 2",
                "temperature": 0.5,
                "max_tokens": 100,
            },
            {
                "provider": "groq",
                "model": "openai/gpt-oss-120b",
                "prompt": "Pergunta 3",
                "temperature": 0.5,
                "max_tokens": 100,
            },
        ]
    }

    response = client.post(
        "/v1/inference/batch",
        json=payload,
    )

    assert response.status_code == 400

    assert response.json() == {"detail": "Batch size 3 exceeds configured limit of 2."}

    service.execute.assert_awaited_once()


def test_batch_endpoint_rejects_more_than_50_requests() -> None:
    app = _create_test_app()

    service = MagicMock(spec=BatchInferenceService)
    service.execute = AsyncMock()

    app.dependency_overrides[get_batch_inference_service] = lambda: service
    app.dependency_overrides[enforce_inference_rate_limit] = lambda: None

    client = TestClient(app)

    item = {
        "provider": "groq",
        "model": "openai/gpt-oss-20b",
        "prompt": "Teste",
        "temperature": 0.5,
        "max_tokens": 100,
    }

    response = client.post(
        "/v1/inference/batch",
        json={"requests": [item] * 51},
    )

    assert response.status_code == 422
    service.execute.assert_not_awaited()
