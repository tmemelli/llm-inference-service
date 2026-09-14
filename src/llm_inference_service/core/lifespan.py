"""
Application lifespan management and dependency initialization.
"""

from asyncio import Semaphore
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from google import genai
from google.genai import types
from groq import AsyncGroq

from llm_inference_service.api.rate_limiter import InMemoryRateLimiter
from llm_inference_service.core.settings import get_settings
from llm_inference_service.domain.protocols import ProviderClient
from llm_inference_service.providers.gemini_client import GeminiClient
from llm_inference_service.providers.groq_client import GroqClient
from llm_inference_service.services.inference_service import InferenceService
from llm_inference_service.services.provider_registry import ProviderRegistry


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Initialize and release application-scoped inference resources.

    Provider SDK clients, concurrency controls, the provider registry, and
    the inference service are created once during application startup and
    reused across incoming requests.
    """

    settings = get_settings()

    rate_limiter = InMemoryRateLimiter(
        limit_per_minute=settings.inference_rate_limit_per_minute,
    )

    groq_sdk = AsyncGroq(
        api_key=settings.groq_api_key.get_secret_value(),
        max_retries=0,
    )
    groq_client = GroqClient(client=groq_sdk)

    http_options = types.HttpOptions(
        retry_options=types.HttpRetryOptions(
            attempts=1,
        )
    )

    gemini_sdk = genai.Client(
        api_key=settings.gemini_api_key.get_secret_value(),
        http_options=http_options,
    )
    gemini_client = GeminiClient(client=gemini_sdk)

    providers: dict[str, ProviderClient] = {
        "groq": groq_client,
        "gemini": gemini_client,
    }

    inference_semaphores = {
        provider: Semaphore(
            settings.provider_policies[provider].max_concurrent_requests
        )
        for provider in providers
    }

    provider_registry = ProviderRegistry(providers=providers)

    inference_service = InferenceService(
        registry=provider_registry,
        semaphores=inference_semaphores,
        provider_policies=settings.provider_policies,
    )

    app.state.inference_service = inference_service
    app.state.rate_limiter = rate_limiter

    try:
        yield
    finally:
        await gemini_sdk.aio.aclose()
        await groq_sdk.close()
