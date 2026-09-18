"""
Gemini provider adapter and error translation.
"""

import time

import httpx
from google import genai
from google.genai import errors, types

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


def _map_gemini_error(exc: Exception) -> ProviderError:
    """
    Map Gemini SDK and transport errors to domain provider errors.
    """

    if isinstance(exc, errors.APIError):
        code = getattr(exc, "code", None)

        # Authentication and authorization failures.
        if code in (401, 403):
            return ProviderAccessError(
                provider="gemini",
                error_type=type(exc).__name__,
                message=(
                    "Authentication failed or insufficient permissions "
                    "with the upstream Gemini provider."
                ),
            )

        # Rate limit and quota failures.
        if code == 429:
            return ProviderRateLimitError(
                provider="gemini",
                error_type=type(exc).__name__,
                message=(
                    "The upstream provider rate limit was exceeded. "
                    "Please try again later."
                ),
            )

        # Request and resource validation failures.
        if code in (400, 404, 409, 422):
            return ProviderRequestRejectedError(
                provider="gemini",
                error_type=type(exc).__name__,
                message="The upstream Gemini provider rejected the request.",
            )

        # Upstream timeout failures.
        if code in (408, 504):
            return ProviderTimeoutError(
                provider="gemini",
                error_type=type(exc).__name__,
                message=(
                    "The upstream Gemini provider took too long "
                    "to respond. Request timed out."
                ),
            )

        # Remaining server-side failures.
        if code and 500 <= code < 600:
            return ProviderUnavailableError(
                provider="gemini",
                error_type=type(exc).__name__,
                message=(
                    "The upstream Gemini provider encountered an "
                    "internal server error. Service is temporarily unavailable."
                ),
            )

        return ProviderError(
            provider="gemini",
            error_type=type(exc).__name__,
            message=(
                "The upstream Gemini provider returned an unexpected "
                f"status code ({code})."
            ),
        )

    if isinstance(exc, errors.UnknownApiResponseError):
        return ProviderResponseError(
            provider="gemini",
            error_type=type(exc).__name__,
            message=(
                "The response received from the upstream Gemini provider "
                "could not be parsed."
            ),
        )

    if isinstance(exc, httpx.TimeoutException):
        return ProviderTimeoutError(
            provider="gemini",
            error_type=type(exc).__name__,
            message=(
                "The upstream Gemini provider took too long "
                "to respond. Request timed out."
            ),
        )

    if isinstance(exc, httpx.RequestError):
        return ProviderConnectionError(
            provider="gemini",
            error_type=type(exc).__name__,
            message=(
                "Failed to establish a connection with the upstream Gemini provider."
            ),
        )

    return ProviderError(
        provider="gemini",
        error_type=type(exc).__name__,
        message=(
            "An unexpected error occurred while communicating "
            "with the upstream Gemini provider."
        ),
    )


class GeminiClient:
    """
    Adapt the Google GenAI SDK to the provider client domain contract.
    """

    def __init__(self, client: genai.Client) -> None:
        """
        Initialize the adapter with a configured Gemini SDK client.
        """

        self._client = client

    async def execute(
        self,
        request: InferenceRequest,
    ) -> ModelResponse:
        """
        Execute an inference request through Gemini.

        The provider response is validated and normalized into the common
        domain response model used by the inference service.
        """

        system_instruction = (
            request.system_prompt or "You are a helpful and direct assistant."
        )

        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=request.prompt),
                ],
            )
        ]

        start_inference = time.perf_counter()

        try:
            response = await self._client.aio.models.generate_content(
                model=request.model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=request.temperature,
                    max_output_tokens=request.max_tokens,
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(
                        disable=True,
                    ),
                ),
            )

        except (
            errors.APIError,
            errors.UnknownApiResponseError,
            httpx.RequestError,
        ) as error:
            raise _map_gemini_error(error) from error

        latency_ms = (time.perf_counter() - start_inference) * 1000

        if not response.candidates:
            raise ProviderResponseError(
                provider="gemini",
                error_type="InvalidResponse",
                message="Provider response did not include any candidates.",
            )

        content = response.text

        if not content:
            raise ProviderResponseError(
                provider="gemini",
                error_type="InvalidResponse",
                message="Provider response did not include content.",
            )

        if response.usage_metadata is None:
            raise ProviderResponseError(
                provider="gemini",
                error_type="InvalidResponse",
                message="Provider response did not include usage data.",
            )

        resolved_model = getattr(response, "model_version", None) or request.model
        usage = response.usage_metadata

        prompt_tokens = (
            usage.prompt_token_count if usage.prompt_token_count is not None else 0
        )

        completion_tokens = (
            usage.candidates_token_count
            if usage.candidates_token_count is not None
            else 0
        )

        return ModelResponse(
            provider="gemini",
            model=resolved_model,
            content=content,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
            request_id=request.request_id,
        )
