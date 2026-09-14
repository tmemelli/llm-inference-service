"""
Pydantic schemas for inference API requests and responses.
"""

from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from llm_inference_service.domain.provider_catalog import (
    SupportedModel,
    is_model_supported,
)

PromptString = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=2000,
    ),
]

SystemPromptString = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=2000,
    ),
]


class InferenceRequestSchema(BaseModel):
    """
    Validate and normalize incoming inference requests.
    """

    provider: Literal["groq", "gemini"]
    model: SupportedModel
    prompt: PromptString
    system_prompt: SystemPromptString | None = None
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=500, ge=1, le=500)

    @field_validator("provider", mode="before")
    @classmethod
    def normalize_provider(cls, value: object) -> object:
        """
        Normalize provider names before validation.
        """

        if isinstance(value, str):
            return value.strip().lower()

        return value

    @model_validator(mode="after")
    def validate_provider_and_model_compatibility(
        self,
    ) -> "InferenceRequestSchema":
        """
        Ensure the selected model is supported by the requested provider.
        """

        if not is_model_supported(self.provider, self.model):
            raise ValueError(
                f"Model '{self.model}' is not supported by provider '{self.provider}'."
            )

        return self


class InferenceResponseSchema(BaseModel):
    """
    Represent the public API response returned after an inference.
    """

    model_config = ConfigDict(from_attributes=True)

    request_id: str
    provider: str
    model: str
    content: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float
