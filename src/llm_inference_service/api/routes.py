"""
HTTP routes exposed by the inference API.
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from llm_inference_service.api.dependencies import (
    enforce_inference_rate_limit,
    get_batch_inference_service,
    get_inference_service,
)
from llm_inference_service.api.schemas import (
    BatchInferenceRequestSchema,
    BatchInferenceResponseSchema,
    InferenceRequestSchema,
    InferenceResponseSchema,
)
from llm_inference_service.domain.models import InferenceRequest
from llm_inference_service.services.batch_inference_service import BatchInferenceService
from llm_inference_service.services.inference_service import InferenceService

api_router = APIRouter()


@api_router.get("/health")
async def health_check() -> dict[str, str]:
    """
    Return the current health status of the API.
    """

    return {"status": "ok"}


@api_router.post(
    "/v1/inference",
    dependencies=[Depends(enforce_inference_rate_limit)],
)
async def run_inference(
    request: InferenceRequestSchema,
    service: Annotated[
        InferenceService,
        Depends(get_inference_service),
    ],
) -> InferenceResponseSchema:
    """
    Execute an inference request through the configured provider.

    The validated API payload is converted into a domain request, processed
    by the inference service, and converted back into the public API response
    schema.
    """

    domain_request = InferenceRequest(**request.model_dump())
    domain_response = await service.execute(domain_request)

    return InferenceResponseSchema.model_validate(domain_response)


@api_router.post(
    "/v1/inference/batch",
    dependencies=[Depends(enforce_inference_rate_limit)],
)
async def run_batch_inference(
    request: BatchInferenceRequestSchema,
    service: Annotated[
        BatchInferenceService,
        Depends(get_batch_inference_service),
    ],
) -> BatchInferenceResponseSchema:
    """
    Execute multiple inference requests concurrently.
    """

    domain_requests = [
        InferenceRequest(**item.model_dump()) for item in request.requests
    ]

    domain_response = await service.execute(domain_requests)

    return BatchInferenceResponseSchema.model_validate(domain_response)
