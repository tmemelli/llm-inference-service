"""
FastAPI dependency providers for application services.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from llm_inference_service.api.rate_limiter import InMemoryRateLimiter
from llm_inference_service.services.batch_inference_service import (
    BatchInferenceService,
)
from llm_inference_service.services.inference_service import InferenceService


def get_inference_service(
    request: Request,
) -> InferenceService:
    """
    Return the application-scoped inference service.

    The service is created during the FastAPI lifespan and stored in
    app.state so the same initialized instance can be reused across
    incoming requests.
    """

    return request.app.state.inference_service


def get_batch_inference_service(
    request: Request,
) -> BatchInferenceService:
    """
    Return the application-scoped batch inference service.
    """

    return request.app.state.batch_inference_service


def get_rate_limiter(request: Request) -> InMemoryRateLimiter:
    """
    Return the application-scoped rate limiter.
    """

    return request.app.state.rate_limiter


def _get_client_ip(request: Request) -> str | None:
    """
    Return the original client IP address.

    When the application runs behind a trusted reverse proxy, the original
    client address is taken from the first entry in X-Forwarded-For.
    """

    forwarded_for = request.headers.get("x-forwarded-for")

    if forwarded_for:
        return forwarded_for.split(",", maxsplit=1)[0].strip()

    if request.client is not None:
        return request.client.host

    return None


async def enforce_inference_rate_limit(
    request: Request,
    rate_limiter: Annotated[
        InMemoryRateLimiter,
        Depends(get_rate_limiter),
    ],
) -> None:
    """
    Reject inference requests that exceed the configured client rate limit.
    """

    client_ip = _get_client_ip(request)

    if client_ip is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to identify the request client.",
        )

    allowed = await rate_limiter.allow(client_ip)

    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Inference rate limit exceeded. Please try again later.",
        )
