"""
Tests for in-memory inference rate limiting.
"""

import pytest

from llm_inference_service.api.rate_limiter import InMemoryRateLimiter


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_rate_limiter_blocks_requests_after_limit_is_reached() -> None:
    rate_limiter = InMemoryRateLimiter(limit_per_minute=2)

    assert await rate_limiter.allow("192.0.2.1") is True
    assert await rate_limiter.allow("192.0.2.1") is True
    assert await rate_limiter.allow("192.0.2.1") is False
