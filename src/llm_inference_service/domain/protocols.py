"""
Protocols that define contracts for external inference providers.
"""

from typing import Protocol

from llm_inference_service.domain.models import InferenceRequest, ModelResponse


class ProviderClient(Protocol):
    """
    Define the contract required from an inference provider client.
    """

    async def execute(
        self,
        request: InferenceRequest,
    ) -> ModelResponse:
        """
        Execute an inference request and return a normalized model response.
        """
        ...
