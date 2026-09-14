"""
Application entry point for the LLM Inference Service API.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from llm_inference_service.api.exception_handlers import (
    register_exception_handlers,
)
from llm_inference_service.api.routes import api_router
from llm_inference_service.core.lifespan import lifespan
from llm_inference_service.core.settings import get_settings

settings = get_settings()

app = FastAPI(
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

app.include_router(api_router)
register_exception_handlers(app)
