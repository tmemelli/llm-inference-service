"""
Inference orchestration, resilience, fallback, and concurrency control.
"""

import asyncio
import random
from asyncio import Semaphore
from collections.abc import Mapping
from dataclasses import replace

from llm_inference_service.core.provider_policy import ProviderPolicy
from llm_inference_service.domain.exceptions import (
    ProviderConnectionError,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from llm_inference_service.domain.models import InferenceRequest, ModelResponse
from llm_inference_service.domain.protocols import ProviderClient
from llm_inference_service.services.provider_registry import ProviderRegistry

_RETRYABLE_PROVIDER_ERRORS = (
    ProviderTimeoutError,
    ProviderConnectionError,
    ProviderRateLimitError,
    ProviderUnavailableError,
)


class InferenceService:
    """
    Orchestrate inference execution across configured AI providers.

    The service applies provider-specific concurrency limits, timeouts,
    retries with exponential backoff and jitter, model fallbacks, and
    provider fallbacks while preserving the original request identifier.
    """

    def __init__(
        self,
        registry: ProviderRegistry,
        semaphores: Mapping[str, Semaphore],
        provider_policies: Mapping[str, ProviderPolicy],
    ) -> None:
        """
        Initialize the inference service with providers and runtime policies.
        """

        self._registry = registry
        self._semaphores = semaphores
        self._provider_policies = provider_policies

    def _get_policy_for_provider(
        self,
        provider: str,
    ) -> ProviderPolicy:
        """
        Return the operational policy configured for a provider.
        """

        if provider not in self._provider_policies:
            raise ValueError(f"Provider '{provider}' is not configured in settings.")

        return self._provider_policies[provider]

    def _calculate_backoff(
        self,
        policy: ProviderPolicy,
        attempt: int,
    ) -> float:
        """
        Calculate retry delay using exponential backoff and jitter.
        """

        exponential_delay = min(
            policy.retry_max_exponential_delay_seconds,
            policy.retry_base_delay_seconds * (2**attempt),
        )

        # Non-cryptographic randomness is sufficient for retry jitter.
        jitter = random.uniform(  # nosec B311
            0,
            policy.retry_max_jitter_seconds,
        )

        return exponential_delay + jitter

    async def execute(
        self,
        request: InferenceRequest,
    ) -> ModelResponse:
        """
        Execute an inference request with provider fallback support.

        The original provider completes its full retry and model fallback
        flow before any configured fallback provider is attempted.
        """

        try:
            return await self._execute_provider_flow(request)

        except ProviderError:
            policy = self._get_policy_for_provider(request.provider)

            if not policy.provider_fallbacks:
                raise

            for index, provider_fallback in enumerate(
                policy.provider_fallbacks,
                start=1,
            ):
                fallback_request = replace(
                    request,
                    provider=provider_fallback.target_provider,
                    model=provider_fallback.target_model,
                )

                try:
                    return await self._execute_provider_flow(fallback_request)

                except _RETRYABLE_PROVIDER_ERRORS:
                    if index == len(policy.provider_fallbacks):
                        raise

            raise RuntimeError("Unreachable code.")

    async def _execute_provider_flow(
        self,
        request: InferenceRequest,
    ) -> ModelResponse:
        """
        Execute the complete inference flow for a single provider.

        The requested model is attempted first. If a retryable failure
        persists after retries are exhausted, configured model fallbacks
        are attempted in order using the same provider.
        """

        client = self._registry.get(request.provider)
        policy = self._get_policy_for_provider(request.provider)

        try:
            return await self._execute_with_retries(
                client=client,
                request=request,
                policy=policy,
            )

        except _RETRYABLE_PROVIDER_ERRORS:
            fallback_models = policy.model_fallbacks.get(
                request.model,
                [],
            )

            if not fallback_models:
                raise

            for index, fallback_model in enumerate(
                fallback_models,
                start=1,
            ):
                fallback_request = replace(
                    request,
                    model=fallback_model,
                )

                try:
                    return await self._execute_with_retries(
                        client=client,
                        request=fallback_request,
                        policy=policy,
                    )

                except _RETRYABLE_PROVIDER_ERRORS:
                    if index == len(fallback_models):
                        raise

            raise RuntimeError("Unreachable code.")

    async def _execute_with_retries(
        self,
        client: ProviderClient,
        request: InferenceRequest,
        policy: ProviderPolicy,
    ) -> ModelResponse:
        """
        Execute an inference request using the provider retry policy.
        """

        for attempt in range(policy.max_inference_retries + 1):
            try:
                return await self._execute_once(
                    client=client,
                    request=request,
                    policy=policy,
                )

            except _RETRYABLE_PROVIDER_ERRORS:
                if attempt == policy.max_inference_retries:
                    raise

                delay = self._calculate_backoff(
                    policy,
                    attempt,
                )

                await asyncio.sleep(delay)

        raise RuntimeError("Unreachable code.")

    async def _execute_once(
        self,
        client: ProviderClient,
        request: InferenceRequest,
        policy: ProviderPolicy,
    ) -> ModelResponse:
        """
        Execute one provider attempt under concurrency and timeout controls.
        """

        async with self._semaphores[request.provider]:
            try:
                return await asyncio.wait_for(
                    client.execute(request),
                    timeout=policy.timeout_seconds,
                )

            except TimeoutError as error:
                raise ProviderTimeoutError(
                    provider=request.provider,
                    error_type=type(error).__name__,
                    message=(
                        "The inference request exceeded the configured "
                        f"timeout of {policy.timeout_seconds} seconds."
                    ),
                ) from error
