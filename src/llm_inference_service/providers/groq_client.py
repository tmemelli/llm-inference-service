"""
Groq provider adapter and error translation.
"""

import time

from groq import (
    APIConnectionError,
    APIError,
    APIResponseValidationError,
    APIStatusError,
    APITimeoutError,
    AsyncGroq,
    AuthenticationError,
    BadRequestError,
    ConflictError,
    InternalServerError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    UnprocessableEntityError,
)

from llm_inference_service.domain.exceptions import (
    ProviderAccessError,
    ProviderConnectionError,
    ProviderError,
    ProviderRateLimitError,
    ProviderRequestRejectedError,
    ProviderResponseError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from llm_inference_service.domain.models import InferenceRequest, ModelResponse


def _map_groq_error(exc: APIError) -> ProviderError:
    """
    Map Groq SDK errors to domain provider errors.
    """

    if isinstance(exc, APITimeoutError):
        return ProviderTimeoutError(
            provider="groq",
            error_type=type(exc).__name__,
            message=(
                "The upstream provider took too long to respond. " "Request timed out."
            ),
        )

    if isinstance(exc, APIConnectionError):
        return ProviderConnectionError(
            provider="groq",
            error_type=type(exc).__name__,
            message=(
                "Failed to establish a connection with the upstream " "Groq provider."
            ),
        )

    if isinstance(exc, (AuthenticationError, PermissionDeniedError)):
        return ProviderAccessError(
            provider="groq",
            error_type=type(exc).__name__,
            message=(
                "Authentication failed or insufficient permissions "
                "with the upstream Groq provider."
            ),
        )

    if isinstance(
        exc,
        (
            BadRequestError,
            NotFoundError,
            ConflictError,
            UnprocessableEntityError,
        ),
    ):
        return ProviderRequestRejectedError(
            provider="groq",
            error_type=type(exc).__name__,
            message="The upstream Groq provider rejected the request.",
        )

    if isinstance(exc, RateLimitError):
        return ProviderRateLimitError(
            provider="groq",
            error_type=type(exc).__name__,
            message=(
                "The upstream provider rate limit was exceeded. "
                "Please try again later."
            ),
        )

    if isinstance(exc, APIStatusError) and exc.status_code in (408, 504):
        return ProviderTimeoutError(
            provider="groq",
            error_type=type(exc).__name__,
            message=(
                "The upstream Groq provider took too long "
                "to respond. Request timed out."
            ),
        )

    if isinstance(exc, InternalServerError):
        return ProviderUnavailableError(
            provider="groq",
            error_type=type(exc).__name__,
            message=(
                "The upstream Groq provider encountered an internal server "
                "error. Service is temporarily unavailable."
            ),
        )

    if isinstance(exc, APIResponseValidationError):
        return ProviderResponseError(
            provider="groq",
            error_type=type(exc).__name__,
            message=(
                "The response received from the upstream Groq provider "
                "failed schema validation."
            ),
        )

    if isinstance(exc, APIStatusError):
        return ProviderError(
            provider="groq",
            error_type=type(exc).__name__,
            message=f"Groq API failed with status code {exc.status_code}.",
        )

    return ProviderError(
        provider="groq",
        error_type=type(exc).__name__,
        message=(
            "An unexpected error occurred while communicating "
            "with the upstream Groq provider."
        ),
    )


class GroqClient:
    """
    Adapt the Groq SDK to the provider client domain contract.
    """

    def __init__(self, client: AsyncGroq) -> None:
        """
        Initialize the adapter with a configured Groq SDK client.
        """

        self._client = client

    async def execute(
        self,
        request: InferenceRequest,
    ) -> ModelResponse:
        """
        Execute an inference request through Groq.

        The provider response is validated and normalized into the common
        domain response model used by the inference service.
        """

        system_instruction = (
            request.system_prompt or "You are a helpful and direct assistant."
        )

        start_inference = time.perf_counter()

        try:
            response = await self._client.chat.completions.create(
                model=request.model,
                messages=[
                    {
                        "role": "system",
                        "content": system_instruction,
                    },
                    {
                        "role": "user",
                        "content": request.prompt,
                    },
                ],
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            )

        except APIError as error:
            raise _map_groq_error(error) from error

        latency_ms = (time.perf_counter() - start_inference) * 1000

        if not response.choices:
            raise ProviderResponseError(
                provider="groq",
                error_type="InvalidResponse",
                message="Provider response did not include any choices.",
            )

        content = response.choices[0].message.content

        if not content:
            raise ProviderResponseError(
                provider="groq",
                error_type="InvalidResponse",
                message="Provider response did not include content.",
            )

        if response.usage is None:
            raise ProviderResponseError(
                provider="groq",
                error_type="InvalidResponse",
                message="Provider response did not include usage data.",
            )

        usage = response.usage

        return ModelResponse(
            provider="groq",
            model=response.model,
            content=content,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            latency_ms=latency_ms,
            request_id=request.request_id,
        )
