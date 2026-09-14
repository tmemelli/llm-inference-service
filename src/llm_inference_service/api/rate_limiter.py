"""
In-memory rate limiting for public API requests.
"""

import asyncio
from collections import deque
from time import monotonic

_WINDOW_SECONDS = 60.0


class InMemoryRateLimiter:
    """
    Limit requests per client within a rolling one-minute window.
    """

    def __init__(self, limit_per_minute: int) -> None:
        self._limit_per_minute = limit_per_minute
        self._requests: dict[str, deque[float]] = {}
        self._lock = asyncio.Lock()
        self._last_cleanup = monotonic()

    async def allow(self, client_id: str) -> bool:
        """
        Return whether the client may perform another request.
        """

        now = monotonic()
        cutoff = now - _WINDOW_SECONDS

        async with self._lock:
            if now - self._last_cleanup >= _WINDOW_SECONDS:
                self._cleanup(cutoff)
                self._last_cleanup = now

            timestamps = self._requests.setdefault(client_id, deque())

            while timestamps and timestamps[0] <= cutoff:
                timestamps.popleft()

            if len(timestamps) >= self._limit_per_minute:
                return False

            timestamps.append(now)
            return True

    def _cleanup(self, cutoff: float) -> None:
        """
        Remove expired request records from inactive clients.
        """

        expired_clients: list[str] = []

        for client_id, timestamps in self._requests.items():
            while timestamps and timestamps[0] <= cutoff:
                timestamps.popleft()

            if not timestamps:
                expired_clients.append(client_id)

        for client_id in expired_clients:
            del self._requests[client_id]
