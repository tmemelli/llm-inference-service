"""
Application settings and provider policy validation.
"""

from functools import lru_cache

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from llm_inference_service.core.provider_policy import ProviderPolicy
from llm_inference_service.domain.provider_catalog import (
    SUPPORTED_MODELS_BY_PROVIDER,
    SupportedModel,
    is_model_supported,
)


class Settings(BaseSettings):
    """
    Load application configuration and validate provider policies.

    Settings are loaded from environment variables and validated at startup
    to ensure that provider, model, and fallback configurations are internally
    consistent.
    """

    groq_api_key: SecretStr
    gemini_api_key: SecretStr
    cors_allowed_origins: list[str] = Field(default_factory=list)
    inference_rate_limit_per_minute: int = Field(default=5, ge=1)
    provider_policies: dict[str, ProviderPolicy]

    @model_validator(mode="after")
    def validate_provider_policies(self) -> "Settings":
        """
        Validate provider policies and fallback relationships.
        """

        expected_providers = set(SUPPORTED_MODELS_BY_PROVIDER)
        configured_providers = set(self.provider_policies)

        # Reject provider policies that are not present in the catalog.
        unsupported_providers = configured_providers - expected_providers

        if unsupported_providers:
            raise ValueError(
                "Unsupported providers defined in policies: "
                f"{', '.join(sorted(unsupported_providers))}."
            )

        # Require a policy for every provider defined in the catalog.
        missing_providers = expected_providers - configured_providers

        if missing_providers:
            raise ValueError(
                "Missing provider policies for: "
                f"{', '.join(sorted(missing_providers))}."
            )

        for provider, policy in self.provider_policies.items():
            for source_model, fallback_models in policy.model_fallbacks.items():
                # Validate the source model against the global model catalog.
                try:
                    source = SupportedModel(source_model)
                except ValueError as exc:
                    raise ValueError(
                        f"Invalid model entry in fallbacks for provider "
                        f"'{provider}': {exc}"
                    ) from exc

                # Ensure the source model belongs to the configured provider.
                if not is_model_supported(provider, source):
                    raise ValueError(
                        f"Fallback source model '{source_model}' is not supported "
                        f"by provider '{provider}'."
                    )

                # Reject duplicate fallback models for the same source model.
                if len(fallback_models) != len(set(fallback_models)):
                    raise ValueError(
                        f"Invalid fallback configuration for provider '{provider}': "
                        f"source model '{source_model}' contains duplicate "
                        "fallback targets."
                    )

                for fallback_model in fallback_models:
                    # Prevent a model from falling back to itself.
                    if source_model == fallback_model:
                        raise ValueError(
                            "Invalid fallback configuration for provider "
                            f"'{provider}': source model '{source_model}' cannot "
                            "map to itself."
                        )

                    # Validate the fallback model against the global model catalog.
                    try:
                        fallback = SupportedModel(fallback_model)
                    except ValueError as exc:
                        raise ValueError(
                            "Invalid model entry in fallbacks for "
                            f"provider '{provider}': {exc}"
                        ) from exc

                    # Ensure the fallback model belongs to the same provider.
                    if not is_model_supported(provider, fallback):
                        raise ValueError(
                            f"Fallback target model '{fallback_model}' is not "
                            f"supported by provider '{provider}'."
                        )

            target_providers = [
                fallback.target_provider for fallback in policy.provider_fallbacks
            ]

            # Reject duplicate provider fallback targets.
            if len(target_providers) != len(set(target_providers)):
                raise ValueError(
                    f"Provider '{provider}' contains duplicate provider "
                    "fallback targets."
                )

            for provider_fallback in policy.provider_fallbacks:
                # Ensure the fallback provider exists in the catalog.
                if provider_fallback.target_provider not in expected_providers:
                    raise ValueError(
                        f"Fallback target provider "
                        f"'{provider_fallback.target_provider}' is not "
                        "supported by the catalog."
                    )

                # Prevent a provider from falling back to itself.
                if provider_fallback.target_provider == provider:
                    raise ValueError(
                        f"Provider '{provider}' cannot define itself as a "
                        "provider fallback."
                    )

                # Ensure the selected model belongs to the fallback provider.
                if not is_model_supported(
                    provider_fallback.target_provider,
                    provider_fallback.target_model,
                ):
                    raise ValueError(
                        f"Fallback target model "
                        f"'{provider_fallback.target_model}' is not "
                        f"supported by provider "
                        f"'{provider_fallback.target_provider}'."
                    )

        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """
    Return the cached application settings instance.
    """

    return Settings()  # pyright: ignore[reportCallIssue]
