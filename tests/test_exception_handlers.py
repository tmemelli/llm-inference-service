"""
Tests for API exception handlers and public error responses.
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from llm_inference_service.api.exception_handlers import register_exception_handlers
from llm_inference_service.domain.exceptions import (
    ProviderError,
    ProviderNotFoundError,
    ProviderTimeoutError,
)


def _create_test_app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/test-not-found")
    async def raise_not_found() -> None:
        raise ProviderNotFoundError("The requested model or resource was not found.")

    @app.get("/test-timeout")
    async def raise_timeout() -> None:
        raise ProviderTimeoutError(
            provider="groq",
            error_type="APITimeoutError",
            message=(
                "The upstream provider took too long to respond. " "Request timed out."
            ),
        )

    @app.get("/test-error")
    async def raise_error() -> None:
        raise ProviderError(
            provider="groq",
            error_type="APIError",
            message=(
                "An unexpected error occurred while communicating "
                "with the upstream Groq provider."
            ),
        )

    return app


client = TestClient(_create_test_app())


def test_provider_not_found_handler() -> None:
    response = client.get("/test-not-found")

    assert response.status_code == 400
    assert response.json() == {
        "detail": "The requested model or resource was not found."
    }


def test_provider_timeout_handler() -> None:
    response = client.get("/test-timeout")

    assert response.status_code == 504
    assert response.json() == {
        "detail": (
            "The upstream provider took too long to respond. " "Request timed out."
        )
    }

    # Ensure internal provider details are not exposed.
    response_text = response.text

    assert "APITimeoutError" not in response_text
    assert "[GROQ]" not in response_text


def test_provider_error_handler() -> None:
    response = client.get("/test-error")

    assert response.status_code == 502
    assert response.json() == {
        "detail": (
            "An unexpected error occurred while communicating "
            "with the upstream Groq provider."
        )
    }
