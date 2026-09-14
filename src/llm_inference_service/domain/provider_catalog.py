"""
Provider and model catalog used by the inference domain.
"""

from enum import StrEnum


class SupportedModel(StrEnum):
    """
    Enumerate all models supported by the inference service.
    """

    GPT_OSS_20B = "openai/gpt-oss-20b"
    GPT_OSS_120B = "openai/gpt-oss-120b"
    GEMINI_3_1_FLASH_LITE = "gemini-3.1-flash-lite"


SUPPORTED_MODELS_BY_PROVIDER: dict[str, frozenset[SupportedModel]] = {
    "groq": frozenset(
        {
            SupportedModel.GPT_OSS_20B,
            SupportedModel.GPT_OSS_120B,
        }
    ),
    "gemini": frozenset(
        {
            SupportedModel.GEMINI_3_1_FLASH_LITE,
        }
    ),
}


def is_model_supported(
    provider: str,
    model: SupportedModel,
) -> bool:
    """
    Return whether a model is supported by the requested provider.
    """

    standardized_provider = provider.strip().lower()

    models: frozenset[SupportedModel] = SUPPORTED_MODELS_BY_PROVIDER.get(
        standardized_provider,
        frozenset(),
    )

    return model in models
