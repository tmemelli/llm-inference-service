"""
Batch inference service module for concurrent execution and
isolation of LLM requests.
"""

import asyncio
import time
from typing import Final

from llm_inference_service.domain.exceptions import (
    BatchSizeExceededError,
    ProviderError,
)
from llm_inference_service.domain.models import (
    BatchInferenceResult,
    BatchItemResult,
    InferenceRequest,
)
from llm_inference_service.services.inference_service import InferenceService


class BatchInferenceService:
    """Orchestrates batch execution of multiple inference requests concurrently,
    ensuring isolated failure handling and structured result aggregation.
    """

    def __init__(
        self,
        inference_service: InferenceService,
        max_batch_size: int,
    ) -> None:
        """Initializes the batch inference service with the underlying inference orchestrator.

        Args:
            inference_service: The core service handling single inference requests.
        """

        self._inference_service: Final[InferenceService] = inference_service
        self._max_batch_size = max_batch_size

    async def execute(
        self,
        requests: list[InferenceRequest],
    ) -> BatchInferenceResult:
        """Executes a batch of inference requests concurrently using a fan-out/fan-in pattern.

        Maintains input-to-output item ordering while isolating individual failures.

        Args:
            requests: A list of inference requests to be processed.

        Returns:
            A consolidated BatchInferenceResult containing individual outcomes and aggregate metrics.
        """

        if len(requests) > self._max_batch_size:
            raise BatchSizeExceededError(
                f"Batch size {len(requests)} exceeds configured limit "
                f"of {self._max_batch_size}."
            )

        start_time: float = time.perf_counter()

        tasks = [self._execute_item(request) for request in requests]

        temporary_results = await asyncio.gather(*tasks)

        success_count: int = sum(1 for r in temporary_results if r.success)
        failure_count: int = len(temporary_results) - success_count

        elapsed_ms: float = (time.perf_counter() - start_time) * 1000.0

        return BatchInferenceResult(
            results=tuple(temporary_results),
            total=len(requests),
            success_count=success_count,
            failure_count=failure_count,
            elapsed_ms=elapsed_ms,
        )

    async def _execute_item(
        self,
        request: InferenceRequest,
    ) -> BatchItemResult:
        """Executes an individual inference request with defensive exception handling.

        Captures provider errors defensively to prevent batch aborts on single-item failures.

        Args:
            request: The individual inference request to process.

        Returns:
            A BatchItemResult capturing either the successful model response or the isolated error metadata.
        """

        try:

            result = await self._inference_service.execute(request)

            return BatchItemResult(
                request_id=request.request_id,
                success=True,
                response=result,
                error_type=None,
                error_message=None,
            )

        except ProviderError as error:
            error_type_str: str = type(error).__name__
            error_msg_str: str = str(error)

            return BatchItemResult(
                request_id=request.request_id,
                success=False,
                response=None,
                error_type=error_type_str,
                error_message=error_msg_str,
            )
