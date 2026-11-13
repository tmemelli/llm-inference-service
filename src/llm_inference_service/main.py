"""
Application entry point for the LLM Inference Service API.
"""

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

from llm_inference_service.api.exception_handlers import (
    register_exception_handlers,
)
from llm_inference_service.api.routes import api_router
from llm_inference_service.core.lifespan import lifespan
from llm_inference_service.core.settings import get_settings

settings = get_settings()

app = FastAPI(
    title="LLM Inference Service",
    description=(
        "Resilient multi-provider LLM inference API with asynchronous execution, "
        "concurrent batch processing, retries, model fallback, provider fallback, "
        "rate limiting, and execution observability."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    """Return basic service information."""
    return {
        "service": "llm-inference-service",
        "status": "ok",
    }


@app.head("/", include_in_schema=False)
async def root_head() -> Response:
    """Respond to infrastructure probes against the application root."""
    return Response(status_code=204)


app.include_router(api_router)
register_exception_handlers(app)
