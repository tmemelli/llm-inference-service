"""
Immutable domain models used throughout the inference workflow.
"""

from dataclasses import dataclass, field
from uuid import uuid4


@dataclass(frozen=True)
class InferenceRequest:
    """
    Represent an immutable inference request inside the domain layer.

    The request carries provider selection, model configuration, prompt data,
    and a unique identifier that is preserved across retries and fallbacks.
    """

    provider: str
    model: str
    prompt: str
    temperature: float
    max_tokens: int
    system_prompt: str | None = None
    request_id: str = field(default_factory=lambda: str(uuid4()))


@dataclass(frozen=True)
class ModelResponse:
    """
    Represent an immutable inference response returned by a provider.

    The response contains the generated content, provider metadata, token
    usage, execution latency, and the original request identifier.
    """

    provider: str
    model: str
    content: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float
    request_id: str
