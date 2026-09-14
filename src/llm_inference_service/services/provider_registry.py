"""
Provider registry used to resolve configured inference clients.
"""

from collections.abc import Mapping

from llm_inference_service.domain.exceptions import ProviderNotFoundError
from llm_inference_service.domain.protocols import ProviderClient


class ProviderRegistry:
    """
    Store and resolve provider clients by provider name.
    """

    def __init__(
        self,
        providers: Mapping[str, ProviderClient],
    ) -> None:
        """
        Initialize the registry with the configured provider clients.
        """

        self._providers = providers

    def get(
        self,
        provider: str,
    ) -> ProviderClient:
        """
        Return the provider client registered for the requested provider.
        """

        if provider not in self._providers:
            raise ProviderNotFoundError(f"Provider '{provider}' is not registered.")

        return self._providers[provider]
