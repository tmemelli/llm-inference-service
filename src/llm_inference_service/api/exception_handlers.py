"""
FastAPI exception handlers for provider and gateway errors.
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from llm_inference_service.domain.exceptions import (
    ProviderAccessError,
    ProviderConnectionError,
    ProviderError,
    ProviderNotFoundError,
    ProviderRateLimitError,
    ProviderRequestRejectedError,
    ProviderResponseError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)


def _handle_provider_exception(
    exc: Exception,
    expected_type: type[Exception],
    status_code: int,
) -> JSONResponse:
    """
    Convert a provider exception into a standardized HTTP JSON response.

    The exception is validated against the expected type before its message
    is exposed through the API response.
    """

    if not isinstance(exc, expected_type):
        raise exc

    detail = exc.message if isinstance(exc, ProviderError) else str(exc)

    return JSONResponse(
        status_code=status_code,
        content={
            "detail": detail,
        },
    )


async def provider_not_found_handler(
    _request: Request,
    exc: Exception,
) -> JSONResponse:
    """
    Handle requests targeting an unknown provider.
    """

    return _handle_provider_exception(
        exc,
        ProviderNotFoundError,
        status.HTTP_400_BAD_REQUEST,
    )


async def provider_access_handler(
    _request: Request,
    exc: Exception,
) -> JSONResponse:
    """
    Handle provider authentication and authorization failures.
    """

    return _handle_provider_exception(
        exc,
        ProviderAccessError,
        status.HTTP_502_BAD_GATEWAY,
    )


async def provider_request_rejected_handler(
    _request: Request,
    exc: Exception,
) -> JSONResponse:
    """
    Handle requests rejected by an upstream provider.
    """

    return _handle_provider_exception(
        exc,
        ProviderRequestRejectedError,
        status.HTTP_502_BAD_GATEWAY,
    )


async def provider_rate_limit_handler(
    _request: Request,
    exc: Exception,
) -> JSONResponse:
    """
    Handle upstream provider rate-limit failures.
    """

    return _handle_provider_exception(
        exc,
        ProviderRateLimitError,
        status.HTTP_503_SERVICE_UNAVAILABLE,
    )


async def provider_connection_handler(
    _request: Request,
    exc: Exception,
) -> JSONResponse:
    """
    Handle connectivity failures with an upstream provider.
    """

    return _handle_provider_exception(
        exc,
        ProviderConnectionError,
        status.HTTP_502_BAD_GATEWAY,
    )


async def provider_timeout_handler(
    _request: Request,
    exc: Exception,
) -> JSONResponse:
    """
    Handle provider inference timeouts.
    """

    return _handle_provider_exception(
        exc,
        ProviderTimeoutError,
        status.HTTP_504_GATEWAY_TIMEOUT,
    )


async def provider_unavailable_handler(
    _request: Request,
    exc: Exception,
) -> JSONResponse:
    """
    Handle temporary upstream provider unavailability.
    """

    return _handle_provider_exception(
        exc,
        ProviderUnavailableError,
        status.HTTP_503_SERVICE_UNAVAILABLE,
    )


async def provider_response_handler(
    _request: Request,
    exc: Exception,
) -> JSONResponse:
    """
    Handle invalid or malformed responses returned by a provider.
    """

    return _handle_provider_exception(
        exc,
        ProviderResponseError,
        status.HTTP_502_BAD_GATEWAY,
    )


async def provider_error_handler(
    _request: Request,
    exc: Exception,
) -> JSONResponse:
    """
    Handle generic provider failures not covered by a specific handler.
    """

    return _handle_provider_exception(
        exc,
        ProviderError,
        status.HTTP_502_BAD_GATEWAY,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """
    Register all gateway exception handlers with the FastAPI application.
    """

    app.add_exception_handler(
        ProviderNotFoundError,
        provider_not_found_handler,
    )
    app.add_exception_handler(
        ProviderAccessError,
        provider_access_handler,
    )
    app.add_exception_handler(
        ProviderRequestRejectedError,
        provider_request_rejected_handler,
    )
    app.add_exception_handler(
        ProviderRateLimitError,
        provider_rate_limit_handler,
    )
    app.add_exception_handler(
        ProviderConnectionError,
        provider_connection_handler,
    )
    app.add_exception_handler(
        ProviderTimeoutError,
        provider_timeout_handler,
    )
    app.add_exception_handler(
        ProviderUnavailableError,
        provider_unavailable_handler,
    )
    app.add_exception_handler(
        ProviderResponseError,
        provider_response_handler,
    )
    app.add_exception_handler(
        ProviderError,
        provider_error_handler,
    )
