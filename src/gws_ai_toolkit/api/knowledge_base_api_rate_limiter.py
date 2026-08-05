"""The per-token request cap the public chat API enforces before it will run a chat.

Every call to ``/chat/ask`` costs an embedding plus an LLM completion, and the publish token is the
only thing standing between a leaked credential and an unbounded bill (see
``docs/todo/knowledge_base_public_api_plan.md`` § Rate limiting). This is deliberately
unsophisticated: a fixed window, counted in memory.

**In-memory, single-process.** The lab runs one uvicorn worker, so a process-local counter is the
cheap option rather than the careful one. A multi-worker deployment would need a shared store
(Redis, a database row) instead — not needed to ship V1.
"""

import threading
import time

from fastapi import status
from gws_core import BaseHTTPException

# Generous enough for a real conversation (a question every few seconds), tight enough that a
# leaked token cannot run up an unbounded bill before someone notices.
DEFAULT_MAX_REQUESTS_PER_WINDOW = 30
DEFAULT_WINDOW_SECONDS = 60.0

RATE_LIMIT_MESSAGE = "Too many requests for this token. Try again later."


class KnowledgeBaseApiRateLimiter:
    """A fixed-window request cap, counted per publish token."""

    def __init__(
        self,
        max_requests_per_window: int = DEFAULT_MAX_REQUESTS_PER_WINDOW,
        window_seconds: float = DEFAULT_WINDOW_SECONDS,
    ) -> None:
        self._max_requests_per_window = max_requests_per_window
        self._window_seconds = window_seconds
        self._lock = threading.Lock()
        # token -> timestamps (monotonic) of requests still inside the current window.
        self._hits: dict[str, list[float]] = {}

    def check(self, token: str) -> None:
        """Count this call against the token's window, raising once the cap is exceeded.

        :param token: the publish token the call is authenticating with
        :raises BaseHTTPException: with a 429 status, if the token has already made
                ``max_requests_per_window`` calls within ``window_seconds``
        """
        now = time.monotonic()
        with self._lock:
            still_in_window = [
                hit for hit in self._hits.get(token, []) if now - hit < self._window_seconds
            ]
            if len(still_in_window) >= self._max_requests_per_window:
                raise BaseHTTPException(status.HTTP_429_TOO_MANY_REQUESTS, RATE_LIMIT_MESSAGE)

            still_in_window.append(now)
            self._hits[token] = still_in_window
