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


@dataclass(frozen=True)
class BatchItemResult:
    """
    Represent the isolated outcome of a single item execution within a batch.
    Enforces strict consistency: success items cannot carry errors, and
    failed items cannot carry a model response.
    """

    request_id: str
    success: bool
    response: ModelResponse | None
    error_type: str | None
    error_message: str | None

    def __post_init__(self) -> None:
        if self.success:
            if self.response is None:
                raise ValueError(
                    "BatchItemResult marked as success=True requires a valid ModelResponse."
                )

            if self.error_type is not None or self.error_message is not None:
                raise ValueError(
                    "BatchItemResult marked as success=True cannot contain error details."
                )
        else:
            if self.response is not None:
                raise ValueError(
                    "BatchItemResult marked as success=False cannot have a ModelResponse."
                )

            if not self.error_type or not self.error_type.strip():
                raise ValueError(
                    "BatchItemResult marked as success=False requires a non-empty error_type."
                )

            if not self.error_message or not self.error_message.strip():
                raise ValueError(
                    "BatchItemResult marked as success=False requires a non-empty error_message."
                )


@dataclass(frozen=True)
class BatchInferenceResult:
    """
    Represent the consolidated outcome of an entire batch execution.
    Uses tuples for immutability and validates metric consistency by construction.
    """

    results: tuple[BatchItemResult, ...]
    total: int
    success_count: int
    failure_count: int
    elapsed_ms: float

    def __post_init__(self) -> None:
        if self.total != len(self.results):
            raise ValueError(
                "Field 'total' does not match the actual length of the results tuple."
            )

        actual_success = sum(1 for r in self.results if r.success)
        actual_failure = len(self.results) - actual_success

        if self.success_count != actual_success:
            raise ValueError(
                "Field 'success_count' does not match actual successful items."
            )

        if self.failure_count != actual_failure:
            raise ValueError(
                "Field 'failure_count' does not match actual failed items."
            )

        if isinstance(self.elapsed_ms, bool) or not isinstance(
            self.elapsed_ms, (int, float)
        ):
            raise TypeError("'elapsed_ms' must be an int or float.")

        if self.elapsed_ms < 0:
            raise ValueError("'elapsed_ms' cannot be negative.")
