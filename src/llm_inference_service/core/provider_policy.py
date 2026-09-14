"""
Provider-specific operational policies for inference execution.
"""

from pydantic import BaseModel, ConfigDict, Field

from llm_inference_service.domain.provider_catalog import SupportedModel


class ProviderFallback(BaseModel):
    """
    Define an ordered fallback target for a failed provider.

    A fallback specifies the provider and model that should receive the
    inference request after the original provider exhausts its retry and
    model fallback strategies.
    """

    target_provider: str
    target_model: SupportedModel

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )


class ProviderPolicy(BaseModel):
    """
    Define resilience and concurrency policies for an inference provider.

    Each provider owns its concurrency limit, timeout, retry strategy,
    model fallback configuration, and provider fallback sequence.
    """

    max_concurrent_requests: int = Field(ge=1)
    timeout_seconds: float = Field(gt=0)
    max_inference_retries: int = Field(ge=0)
    retry_base_delay_seconds: float = Field(gt=0)
    retry_max_exponential_delay_seconds: float = Field(gt=0)
    retry_max_jitter_seconds: float = Field(ge=0)
    model_fallbacks: dict[str, list[str]]
    provider_fallbacks: list[ProviderFallback]

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )
